"""BERT 파인튜닝 모듈 (sprint-04).

klue/roberta-base 기반 AutoModelForSequenceClassification으로
NSMC 감성 분류를 파인튜닝한다.

주요 사항:
- AdamW + Linear Warmup 스케줄러 (warmup_ratio=0.1)
- epoch=3, lr=2e-5, weight_decay=0.01
- Val loss 기반 Early Stopping (patience=1)
- Best 체크포인트: artifacts/checkpoints/best_<timestamp>.pt
- epoch별 train_loss / val_loss / val_acc 로그 기록
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from loguru import logger
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from src.data_loader import load_nsmc
from src.preprocess import build_dataloaders

# ──────────────────────────────────────────────
# 상수 & 경로
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
CHECKPOINTS_DIR = ARTIFACTS_DIR / "checkpoints"
LOGS_DIR = PROJECT_ROOT / "logs"

MODEL_NAME = "klue/roberta-base"
NUM_LABELS = 2
RANDOM_SEED = 42

# 하이퍼파라미터 (sprint-contract 스펙)
NUM_EPOCHS = 3
LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
EARLY_STOP_PATIENCE = 1
BATCH_SIZE = 32
MAX_LENGTH = 128


# ──────────────────────────────────────────────
# 재현성
# ──────────────────────────────────────────────

def set_seed(seed: int = RANDOM_SEED) -> None:
    """전역 랜덤 시드 고정."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    # CUDA 환경에서 CUBLAS_WORKSPACE_CONFIG=:4096:8 설정 필요할 수 있음
    torch.use_deterministic_algorithms(True, warn_only=True)
    logger.debug(f"랜덤 시드 설정: {seed}")


# ──────────────────────────────────────────────
# 디바이스 선택
# ──────────────────────────────────────────────

def get_device() -> torch.device:
    """cuda → mps → cpu 우선순위로 디바이스를 선택한다."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    logger.info(f"사용 디바이스: {device}")
    return device


# ──────────────────────────────────────────────
# 학습 / 평가 스텝
# ──────────────────────────────────────────────

def train_epoch(
    model: nn.Module,
    loader: DataLoader[Any],
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    device: torch.device,
    log_interval: int = 200,
) -> float:
    """1 에폭 학습 후 평균 train loss 반환."""
    model.train()
    total_loss = 0.0
    for step, batch in enumerate(loader, 1):
        input_ids = batch["input_ids"].to(device, non_blocking=True)
        attention_mask = batch["attention_mask"].to(device, non_blocking=True)
        labels = batch["labels"].to(device, non_blocking=True)

        optimizer.zero_grad()
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )
        loss = outputs.loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()
        total_loss += loss.item()

        if step % log_interval == 0:
            avg = total_loss / step
            logger.info(f"  step {step}/{len(loader)} — avg_loss={avg:.4f}")

    return total_loss / len(loader) if len(loader) > 0 else 0.0


def eval_epoch(
    model: nn.Module,
    loader: DataLoader[Any],
    device: torch.device,
) -> tuple[float, float]:
    """평가 실행 후 (val_loss, val_acc) 반환."""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)
            labels = batch["labels"].to(device, non_blocking=True)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            total_loss += outputs.loss.item()
            preds = outputs.logits.argmax(dim=-1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

    val_loss = total_loss / len(loader) if len(loader) > 0 else 0.0
    val_acc = correct / total if total > 0 else 0.0
    return val_loss, val_acc


# ──────────────────────────────────────────────
# 체크포인트 저장 / 로드
# ──────────────────────────────────────────────

def save_checkpoint(
    model: nn.Module,
    metrics: dict[str, Any],
    timestamp: str,
) -> Path:
    """Best 모델 체크포인트를 artifacts/checkpoints/best_<timestamp>.pt로 저장."""
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = CHECKPOINTS_DIR / f"best_{timestamp}.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "metrics": metrics,
            "model_name": MODEL_NAME,
            "num_labels": NUM_LABELS,
            "timestamp": timestamp,
        },
        ckpt_path,
    )
    logger.info(f"체크포인트 저장: {ckpt_path}")
    return ckpt_path


def load_checkpoint(ckpt_path: Path, device: torch.device) -> nn.Module:
    """저장된 체크포인트에서 모델을 로드한다.

    Args:
        ckpt_path: .pt 파일 경로.
        device: 로드할 디바이스.

    Returns:
        로드된 AutoModelForSequenceClassification 모델.
    """
    if not ckpt_path.exists():
        raise FileNotFoundError(f"체크포인트 없음: {ckpt_path}")
    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=True)
    if "model_state_dict" not in checkpoint:
        raise KeyError(f"유효하지 않은 체크포인트 — 'model_state_dict' 키 없음: {ckpt_path}")
    model_name = checkpoint.get("model_name", MODEL_NAME)
    num_labels = checkpoint.get("num_labels", NUM_LABELS)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=num_labels
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)  # 모델 전체 이전 — non_blocking 불필요
    logger.info(f"체크포인트 로드 완료: {ckpt_path} (metrics={checkpoint.get('metrics')})")
    return model


# ──────────────────────────────────────────────
# 메트릭 저장
# ──────────────────────────────────────────────

def save_metrics(metrics: dict[str, Any], sprint_id: str = "sprint-04") -> Path:
    """평가 메트릭을 artifacts/{sprint_id}_metrics.json에 저장한다."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / f"{sprint_id}_metrics.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info(f"메트릭 저장: {path}")
    return path


# ──────────────────────────────────────────────
# 학습 로그 저장
# ──────────────────────────────────────────────

def save_training_log(epoch_logs: list[dict[str, Any]], timestamp: str) -> Path:
    """epoch별 학습 로그를 logs/training_<timestamp>.json에 저장한다."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"training_{timestamp}.json"
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(epoch_logs, f, ensure_ascii=False, indent=2)
    logger.info(f"학습 로그 저장: {log_path}")
    return log_path


# ──────────────────────────────────────────────
# 메인 학습 함수
# ──────────────────────────────────────────────

def train(
    num_epochs: int = NUM_EPOCHS,
    learning_rate: float = LEARNING_RATE,
    weight_decay: float = WEIGHT_DECAY,
    warmup_ratio: float = WARMUP_RATIO,
    patience: int = EARLY_STOP_PATIENCE,
    batch_size: int = BATCH_SIZE,
    max_length: int = MAX_LENGTH,
    random_seed: int = RANDOM_SEED,
    model_name: str = MODEL_NAME,
    max_train_samples: int | None = None,
) -> dict[str, Any]:
    """BERT 파인튜닝 전체 파이프라인을 실행한다.

    1. 시드 고정 및 디바이스 설정
    2. 데이터 로드 및 DataLoader 생성
    3. 모델 / 옵티마이저 / 스케줄러 초기화
    4. 에폭 학습 루프 (Early Stopping 포함)
    5. Best 체크포인트 저장
    6. 메트릭 저장

    Args:
        num_epochs: 최대 학습 에폭 수.
        learning_rate: AdamW 학습률.
        weight_decay: L2 정규화 계수.
        warmup_ratio: 전체 스텝 대비 warmup 비율.
        patience: Early Stopping 인내 에폭 수.
        batch_size: DataLoader 배치 크기.
        max_length: 최대 토큰 시퀀스 길이.
        random_seed: 재현성 시드.
        model_name: HuggingFace 모델 이름.

    Returns:
        최종 메트릭 딕셔너리 (best_val_accuracy, best_val_loss, checkpoint_path 포함).
    """
    set_seed(random_seed)
    device = get_device()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    logger.info("=== BERT 파인튜닝 시작 ===")
    logger.info(
        f"하이퍼파라미터 — epochs={num_epochs}, lr={learning_rate}, "
        f"weight_decay={weight_decay}, warmup_ratio={warmup_ratio}, "
        f"patience={patience}, batch_size={batch_size}"
    )

    # ── 1. 데이터 로드
    logger.info("데이터 로드 중...")
    train_df, test_df = load_nsmc()

    if max_train_samples and len(train_df) > max_train_samples:
        train_df = train_df.sample(n=max_train_samples, random_state=random_seed).reset_index(drop=True)
        logger.info(f"학습 데이터 샘플링: {max_train_samples}건 (전체 중 일부)")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    train_loader, val_loader, _ = build_dataloaders(
        train_df=train_df,
        test_df=test_df,
        tokenizer=tokenizer,
        model_name=model_name,
        max_length=max_length,
        batch_size=batch_size,
        random_seed=random_seed,
    )

    # ── 2. 모델 초기화
    logger.info(f"모델 로드: {model_name}")
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=NUM_LABELS
    )
    model.to(device)  # 모델 전체 이전 — non_blocking 불필요

    # ── 3. 옵티마이저 & 스케줄러
    total_steps = len(train_loader) * num_epochs
    warmup_steps = int(total_steps * warmup_ratio)
    optimizer = AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )
    logger.info(
        f"스케줄러 초기화 — total_steps={total_steps}, warmup_steps={warmup_steps}"
    )

    # ── 4. 학습 루프
    best_val_loss: float = float("inf")
    best_val_acc: float = 0.0
    best_epoch: int = -1
    patience_counter: int = 0
    best_ckpt_path: Path | None = None
    epoch_logs: list[dict[str, Any]] = []

    for epoch in range(1, num_epochs + 1):
        logger.info(f"--- Epoch {epoch}/{num_epochs} 시작 ---")

        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device, log_interval=200)
        val_loss, val_acc = eval_epoch(model, val_loader, device)

        epoch_log: dict[str, Any] = {
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "val_loss": round(val_loss, 6),
            "val_acc": round(val_acc, 6),
        }
        epoch_logs.append(epoch_log)

        logger.info(
            f"Epoch {epoch} — "
            f"train_loss={train_loss:.4f}, "
            f"val_loss={val_loss:.4f}, "
            f"val_acc={val_acc:.4f}"
        )

        # Best 체크포인트 업데이트 — val_loss 감소 기준 (sprint-contract AC-04-04)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            best_epoch = epoch
            patience_counter = 0
            best_ckpt_path = save_checkpoint(
                model=model,
                metrics={
                    "epoch": epoch,
                    "train_loss": train_loss,
                    "val_loss": val_loss,
                    "val_acc": val_acc,
                },
                timestamp=timestamp,
            )
            logger.info(f"Best 모델 갱신 — epoch={epoch}, val_loss={val_loss:.4f}, val_acc={val_acc:.4f}")
        else:
            patience_counter += 1
            logger.info(
                f"Val loss 미개선 — patience_counter={patience_counter}/{patience}"
            )
            if patience_counter >= patience:
                logger.info(
                    f"Early Stopping 발동 — epoch={epoch}, "
                    f"best_epoch={best_epoch}, "
                    f"best_val_loss={best_val_loss:.4f}"
                )
                break

    # ── 5. 최종 로그 저장
    log_path = save_training_log(epoch_logs, timestamp)

    # ── 6. 메트릭 저장
    final_metrics: dict[str, Any] = {
        "val_accuracy": best_val_acc,
        "best_val_loss": best_val_loss,
        "best_epoch": best_epoch,
        "total_epochs_run": len(epoch_logs),
        "checkpoint_path": str(best_ckpt_path) if best_ckpt_path else None,
        "log_path": str(log_path),
        "epoch_logs": epoch_logs,
    }
    save_metrics(final_metrics, sprint_id="sprint-04")

    logger.info(
        f"=== 학습 완료 === "
        f"best_epoch={best_epoch}, "
        f"best_val_acc={best_val_acc:.4f}, "
        f"checkpoint={best_ckpt_path}"
    )
    return final_metrics


# ──────────────────────────────────────────────
# 엔트리포인트
# ──────────────────────────────────────────────

if __name__ == "__main__":
    metrics = train(max_train_samples=80000, patience=1, batch_size=32)
    logger.info(f"최종 Val Accuracy: {metrics['val_accuracy']:.4f}")
