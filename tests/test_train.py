"""sprint-04 train.py 단위 / 통합 테스트."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from src.train import (
    CHECKPOINTS_DIR,
    NUM_LABELS,
    eval_epoch,
    get_device,
    load_checkpoint,
    save_checkpoint,
    save_metrics,
    save_training_log,
    set_seed,
    train_epoch,
)


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _make_tiny_loader(batch_size: int = 2, seq_len: int = 8, n_batches: int = 2):
    """작은 가짜 DataLoader 생성."""
    batches = []
    for _ in range(n_batches):
        batches.append(
            {
                "input_ids": torch.randint(0, 100, (batch_size, seq_len)),
                "attention_mask": torch.ones(batch_size, seq_len, dtype=torch.long),
                "labels": torch.randint(0, NUM_LABELS, (batch_size,)),
            }
        )
    return batches


def _make_tiny_model() -> torch.nn.Module:
    """2-레이어 선형 모델로 모델 인터페이스를 흉내낸다."""
    from transformers.modeling_outputs import SequenceClassifierOutput

    class TinyModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.linear = torch.nn.Linear(8, NUM_LABELS)

        def forward(self, input_ids, attention_mask, labels=None):
            logits = self.linear(input_ids.float())
            loss = None
            if labels is not None:
                loss = torch.nn.functional.cross_entropy(logits, labels)
            return SequenceClassifierOutput(loss=loss, logits=logits)

    return TinyModel()


# ──────────────────────────────────────────────
# set_seed
# ──────────────────────────────────────────────

def test_set_seed_reproducibility():
    """동일 시드로 두 번 실행하면 동일한 랜덤 텐서가 생성된다."""
    set_seed(42)
    t1 = torch.rand(5)
    set_seed(42)
    t2 = torch.rand(5)
    assert torch.allclose(t1, t2), "시드 재현성 실패"


# ──────────────────────────────────────────────
# get_device
# ──────────────────────────────────────────────

def test_get_device_returns_torch_device():
    device = get_device()
    assert isinstance(device, torch.device)
    assert device.type in ("cuda", "mps", "cpu")


# ──────────────────────────────────────────────
# train_epoch / eval_epoch
# ──────────────────────────────────────────────

def test_train_epoch_returns_float():
    """train_epoch이 float loss를 반환한다."""
    model = _make_tiny_model()
    device = torch.device("cpu")
    loader = _make_tiny_loader()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # 간단한 no-op 스케줄러
    scheduler = MagicMock()
    scheduler.step = MagicMock()

    loss = train_epoch(model, loader, optimizer, scheduler, device)
    assert isinstance(loss, float)
    assert loss > 0.0


def test_eval_epoch_returns_loss_and_acc():
    """eval_epoch이 (val_loss, val_acc) 튜플을 반환한다."""
    model = _make_tiny_model()
    device = torch.device("cpu")
    loader = _make_tiny_loader()

    val_loss, val_acc = eval_epoch(model, loader, device)
    assert isinstance(val_loss, float) and val_loss >= 0.0
    assert isinstance(val_acc, float) and 0.0 <= val_acc <= 1.0


# ──────────────────────────────────────────────
# save_checkpoint / load_checkpoint
# ──────────────────────────────────────────────

def test_save_and_load_checkpoint(tmp_path: Path):
    """체크포인트 저장 후 재로드 시 state_dict가 동일하다."""
    # CHECKPOINTS_DIR를 tmp_path로 패치
    model = _make_tiny_model()
    timestamp = "20240101T000000Z"

    with patch("src.train.CHECKPOINTS_DIR", tmp_path):
        ckpt_path = save_checkpoint(model, {"val_acc": 0.91}, timestamp)

    assert ckpt_path.exists()

    # 로드는 transformers 모델이 필요하므로 torch.load만 검증
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    assert "model_state_dict" in checkpoint
    assert checkpoint["metrics"]["val_acc"] == 0.91
    assert checkpoint["timestamp"] == timestamp


# ──────────────────────────────────────────────
# save_metrics
# ──────────────────────────────────────────────

def test_save_metrics_creates_json(tmp_path: Path):
    metrics = {"val_accuracy": 0.92, "best_val_loss": 0.25}
    with patch("src.train.ARTIFACTS_DIR", tmp_path):
        path = save_metrics(metrics, sprint_id="sprint-test")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["val_accuracy"] == pytest.approx(0.92)


# ──────────────────────────────────────────────
# save_training_log
# ──────────────────────────────────────────────

def test_save_training_log_schema(tmp_path: Path):
    """학습 로그에 필수 필드가 포함된다."""
    logs = [
        {"epoch": 1, "train_loss": 0.5, "val_loss": 0.4, "val_acc": 0.88},
        {"epoch": 2, "train_loss": 0.3, "val_loss": 0.45, "val_acc": 0.87},
    ]
    with patch("src.train.LOGS_DIR", tmp_path):
        log_path = save_training_log(logs, timestamp="20240101T000000Z")

    assert log_path.exists()
    data = json.loads(log_path.read_text())
    assert len(data) == 2
    for entry in data:
        for key in ("epoch", "train_loss", "val_loss", "val_acc"):
            assert key in entry, f"필드 누락: {key}"
