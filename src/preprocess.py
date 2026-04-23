"""전처리 파이프라인 모듈.

정규화, 클리닝, 불용어 제거, 토크나이저 적용,
Train/Val/Test 분할, PyTorch DataLoader 구성을 담당한다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from loguru import logger
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, PreTrainedTokenizerBase

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
MODEL_NAME = "klue/roberta-base"
MAX_LENGTH = 128
BATCH_SIZE = 32
RANDOM_SEED = 42

# 한국어 불용어 목록 (기본)
STOPWORDS: set[str] = {
    "이", "가", "을", "를", "은", "는", "의", "에", "에서", "로", "으로",
    "와", "과", "도", "만", "에게", "한테", "께", "부터", "까지",
}


# ──────────────────────────────────────────────
# 텍스트 클리닝
# ──────────────────────────────────────────────

def clean_text(text: str, remove_stopwords: bool = False) -> str:
    """텍스트 정규화 및 클리닝.

    1. HTML 태그 제거
    2. 특수문자 제거 (한글·영문·숫자·공백만 유지)
    3. 연속 공백 단일화
    4. (선택) 불용어 제거
    """
    if not isinstance(text, str):
        return ""

    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", " ", text)

    # 특수문자 제거: 한글, 영문, 숫자, 공백만 유지
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)

    # 연속 공백 단일화
    text = re.sub(r"\s+", " ", text).strip()

    if remove_stopwords:
        tokens = text.split()
        tokens = [t for t in tokens if t not in STOPWORDS]
        text = " ".join(tokens)

    return text


# ──────────────────────────────────────────────
# PyTorch Dataset
# ──────────────────────────────────────────────

class NSMCDataset(Dataset):
    """NSMC 감성 분류용 PyTorch Dataset."""

    def __init__(
        self,
        texts: list[str],
        labels: list[int],
        tokenizer: PreTrainedTokenizerBase,
        max_length: int = MAX_LENGTH,
    ) -> None:
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels": self.labels[idx],
        }


# ──────────────────────────────────────────────
# 분할 + DataLoader 생성
# ──────────────────────────────────────────────

def split_dataframe(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    val_ratio: float = 0.1,
    random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Train DataFrame을 train/val로 stratified 분할하고 test_df 반환.

    Args:
        train_df: 원본 train DataFrame.
        test_df: 원본 test DataFrame.
        val_ratio: 전체 데이터 대비 val 비율 (기본 10%).
        random_seed: 재현성 시드.

    Returns:
        (train_split, val_split, test_split) 튜플.
    """
    total = len(train_df) + len(test_df)
    # val 크기: 전체의 val_ratio
    val_size = val_ratio / (1 - (len(test_df) / total))
    logger.info(f"train/val 분할 시작 — val_size={val_size:.4f}")

    train_split, val_split = train_test_split(
        train_df,
        test_size=val_size,
        random_state=random_seed,
        stratify=train_df["label"],
    )
    train_split = train_split.reset_index(drop=True)
    val_split = val_split.reset_index(drop=True)
    test_split = test_df.reset_index(drop=True)

    logger.info(
        f"분할 결과 — train: {len(train_split)}, val: {len(val_split)}, test: {len(test_split)}"
    )
    return train_split, val_split, test_split


def build_dataloaders(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    tokenizer: PreTrainedTokenizerBase | None = None,
    model_name: str = MODEL_NAME,
    max_length: int = MAX_LENGTH,
    batch_size: int = BATCH_SIZE,
    val_ratio: float = 0.1,
    random_seed: int = RANDOM_SEED,
    remove_stopwords: bool = False,
) -> tuple[DataLoader[Any], DataLoader[Any], DataLoader[Any]]:
    """전처리 파이프라인 전체를 실행하고 DataLoader 3개를 반환한다.

    Args:
        train_df: load_nsmc() 반환 train DataFrame.
        test_df: load_nsmc() 반환 test DataFrame.
        tokenizer: 미리 로드된 tokenizer. None이면 model_name으로 로드.
        model_name: HuggingFace 모델 이름.
        max_length: 최대 토큰 길이.
        batch_size: DataLoader batch 크기.
        val_ratio: 전체 대비 val 비율.
        random_seed: 재현성 시드.
        remove_stopwords: 불용어 제거 여부.

    Returns:
        (train_loader, val_loader, test_loader) 튜플.
    """
    if tokenizer is None:
        logger.info(f"토크나이저 로드: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)

    # 1. 텍스트 클리닝
    logger.info("텍스트 클리닝 시작")
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df["document"] = train_df["document"].apply(
        lambda x: clean_text(x, remove_stopwords=remove_stopwords)
    )
    test_df["document"] = test_df["document"].apply(
        lambda x: clean_text(x, remove_stopwords=remove_stopwords)
    )

    # 클리닝 후 빈 문자열 제거
    train_before = len(train_df)
    test_before = len(test_df)
    train_df = train_df[train_df["document"].str.strip() != ""].reset_index(drop=True)
    test_df = test_df[test_df["document"].str.strip() != ""].reset_index(drop=True)
    logger.info(
        f"클리닝 후 제거 — train: {train_before - len(train_df)}, test: {test_before - len(test_df)}"
    )

    # 2. Train/Val/Test 분할
    train_split, val_split, test_split = split_dataframe(
        train_df, test_df, val_ratio=val_ratio, random_seed=random_seed
    )

    # 3. Dataset 생성
    logger.info("Dataset 및 DataLoader 생성")
    train_texts = train_split["document"].tolist()
    val_texts = val_split["document"].tolist()
    test_texts = test_split["document"].tolist()

    train_labels = train_split["label"].tolist()
    val_labels = val_split["label"].tolist()
    test_labels = test_split["label"].tolist()

    train_dataset = NSMCDataset(train_texts, train_labels, tokenizer, max_length)
    val_dataset = NSMCDataset(val_texts, val_labels, tokenizer, max_length)
    test_dataset = NSMCDataset(test_texts, test_labels, tokenizer, max_length)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    logger.info(
        f"DataLoader 완성 — "
        f"train_batches={len(train_loader)}, "
        f"val_batches={len(val_loader)}, "
        f"test_batches={len(test_loader)}"
    )
    return train_loader, val_loader, test_loader


def compute_token_length_stats(
    texts: list[str],
    tokenizer: PreTrainedTokenizerBase,
    max_length: int = MAX_LENGTH,
) -> dict[str, float]:
    """토큰 길이 통계를 계산한다.

    Returns:
        mean, median, max, over_ratio (max_length 초과 비율) 포함 딕셔너리.
    """
    lengths = []
    for text in texts:
        enc = tokenizer(text, truncation=False, padding=False)
        lengths.append(len(enc["input_ids"]))

    import numpy as np

    arr = np.array(lengths)
    over_count = int((arr > max_length).sum())
    over_ratio = over_count / len(arr) if len(arr) > 0 else 0.0

    stats = {
        "mean": float(arr.mean()),
        "median": float(float(pd.Series(arr).median())),
        "max": int(arr.max()),
        "over_ratio": over_ratio,
        "over_count": over_count,
        "total": len(arr),
    }
    logger.info(
        f"토큰 길이 통계 — mean={stats['mean']:.1f}, "
        f"max={stats['max']}, over({max_length})={over_ratio:.2%}"
    )
    return stats
