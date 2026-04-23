"""sprint-02 전처리 파이프라인 테스트.

AC-02-01: 토큰 길이 128 초과 샘플 비율 < 5%
AC-02-02: Val 세트 크기가 전체의 10% ± 1% 범위 내
AC-02-03: 레이블 분포가 train/val/test 간 편차 < 2%p
AC-02-04: DataLoader가 (input_ids, attention_mask, labels) 딕셔너리 배치 반환
"""
from __future__ import annotations

import pandas as pd
import pytest
import torch

from src.preprocess import (
    NSMCDataset,
    clean_text,
    build_dataloaders,
    compute_token_length_stats,
    split_dataframe,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("klue/roberta-base")


@pytest.fixture(scope="module")
def nsmc_data():
    from src.data_loader import load_nsmc
    return load_nsmc()


@pytest.fixture(scope="module")
def small_df():
    """소규모 더미 DataFrame (빠른 단위 테스트용)."""
    import random
    random.seed(42)
    n = 2000
    docs = [f"영화 리뷰 샘플 텍스트 번호 {i} 정말 재미있어요" for i in range(n)]
    labels = [i % 2 for i in range(n)]
    return pd.DataFrame({"id": range(n), "document": docs, "label": labels})


# ──────────────────────────────────────────────
# clean_text 단위 테스트
# ──────────────────────────────────────────────

class TestCleanText:
    def test_removes_html_tags(self):
        result = clean_text("<b>좋은</b> 영화")
        assert "<b>" not in result
        assert "좋은" in result

    def test_removes_special_chars(self):
        result = clean_text("영화@#$%가 좋아요!!!")
        assert "@" not in result
        assert "#" not in result

    def test_normalizes_whitespace(self):
        result = clean_text("영화   가   좋아요")
        assert "  " not in result

    def test_empty_string(self):
        result = clean_text("")
        assert result == ""

    def test_non_string_returns_empty(self):
        result = clean_text(None)  # type: ignore[arg-type]
        assert result == ""

    def test_preserves_korean_english_digits(self):
        result = clean_text("한글 English 123")
        assert "한글" in result
        assert "English" in result
        assert "123" in result


# ──────────────────────────────────────────────
# split_dataframe 단위 테스트
# ──────────────────────────────────────────────

class TestSplitDataframe:
    def test_val_ratio_within_bounds(self, small_df):
        """AC-02-02: Val 크기가 전체의 10% ± 1% 범위."""
        n_test = 400
        test_df = small_df.iloc[:n_test].copy()
        train_df = small_df.iloc[n_test:].copy().reset_index(drop=True)

        total = len(small_df)
        train_split, val_split, test_split = split_dataframe(train_df, test_df)

        val_ratio = len(val_split) / total
        assert 0.09 <= val_ratio <= 0.11, f"val ratio {val_ratio:.3f} is outside [0.09, 0.11]"

    def test_label_distribution_stratified(self, small_df):
        """AC-02-03: 레이블 분포 편차 < 2%p."""
        n_test = 400
        test_df = small_df.iloc[:n_test].copy()
        train_df = small_df.iloc[n_test:].copy().reset_index(drop=True)

        train_split, val_split, test_split = split_dataframe(train_df, test_df)

        def pos_ratio(df: pd.DataFrame) -> float:
            return (df["label"] == 1).mean()

        ratios = [
            pos_ratio(train_split),
            pos_ratio(val_split),
            pos_ratio(test_split),
        ]
        max_diff = max(ratios) - min(ratios)
        assert max_diff < 0.02, f"label distribution diff {max_diff:.4f} >= 0.02"


# ──────────────────────────────────────────────
# NSMCDataset 단위 테스트
# ──────────────────────────────────────────────

class TestNSMCDataset:
    def test_returns_correct_keys(self, tokenizer):
        """AC-02-04: 배치가 input_ids, attention_mask, labels 포함."""
        texts = ["영화가 재미있어요", "정말 별로예요"]
        labels = [1, 0]
        dataset = NSMCDataset(texts, labels, tokenizer, max_length=128)

        item = dataset[0]
        assert "input_ids" in item
        assert "attention_mask" in item
        assert "labels" in item

    def test_tensor_shapes(self, tokenizer):
        texts = ["테스트 문장"] * 4
        labels = [0, 1, 0, 1]
        dataset = NSMCDataset(texts, labels, tokenizer, max_length=64)

        assert len(dataset) == 4
        item = dataset[0]
        assert item["input_ids"].shape == torch.Size([64])
        assert item["attention_mask"].shape == torch.Size([64])
        assert item["labels"].dtype == torch.long

    def test_dataloader_batch_format(self, tokenizer):
        """DataLoader가 딕셔너리 배치를 올바르게 반환하는지 확인."""
        from torch.utils.data import DataLoader
        texts = [f"리뷰 텍스트 {i}" for i in range(10)]
        labels = [i % 2 for i in range(10)]
        dataset = NSMCDataset(texts, labels, tokenizer, max_length=64)
        loader = DataLoader(dataset, batch_size=4)

        batch = next(iter(loader))
        assert isinstance(batch, dict)
        assert set(batch.keys()) == {"input_ids", "attention_mask", "labels"}
        assert batch["input_ids"].shape == torch.Size([4, 64])
        assert batch["attention_mask"].shape == torch.Size([4, 64])
        assert batch["labels"].shape == torch.Size([4])


# ──────────────────────────────────────────────
# 전체 파이프라인 통합 테스트 (실제 데이터)
# ──────────────────────────────────────────────

class TestFullPipeline:
    def test_ac_02_01_token_length_over_ratio(self, nsmc_data, tokenizer):
        """AC-02-01: 토큰 길이 128 초과 비율 < 5%."""
        train_df, test_df = nsmc_data
        # 샘플링으로 속도 개선 (전체의 5%)
        sample = train_df.sample(n=5000, random_state=42)
        from src.preprocess import clean_text
        texts = sample["document"].apply(lambda x: clean_text(x)).tolist()
        stats = compute_token_length_stats(texts, tokenizer, max_length=128)
        assert stats["over_ratio"] < 0.05, (
            f"토큰 초과 비율 {stats['over_ratio']:.2%} >= 5% "
            f"(over_count={stats['over_count']}, total={stats['total']})"
        )

    def test_ac_02_02_val_size(self, nsmc_data, tokenizer):
        """AC-02-02: Val 크기가 전체의 10% ± 1%."""
        train_df, test_df = nsmc_data
        total = len(train_df) + len(test_df)
        train_split, val_split, _ = split_dataframe(train_df, test_df)
        val_ratio = len(val_split) / total
        assert 0.09 <= val_ratio <= 0.11, (
            f"val ratio {val_ratio:.4f} is outside [0.09, 0.11] "
            f"(val={len(val_split)}, total={total})"
        )

    def test_ac_02_03_label_distribution(self, nsmc_data):
        """AC-02-03: 레이블 분포 편차 < 2%p."""
        train_df, test_df = nsmc_data
        train_split, val_split, test_split = split_dataframe(train_df, test_df)

        def pos_ratio(df: pd.DataFrame) -> float:
            return float((df["label"] == 1).mean())

        r_train = pos_ratio(train_split)
        r_val = pos_ratio(val_split)
        r_test = pos_ratio(test_split)
        max_diff = max(r_train, r_val, r_test) - min(r_train, r_val, r_test)
        assert max_diff < 0.02, (
            f"label 분포 편차 {max_diff:.4f} >= 0.02 "
            f"(train={r_train:.4f}, val={r_val:.4f}, test={r_test:.4f})"
        )

    def test_ac_02_04_dataloader_batch_format(self, nsmc_data, tokenizer):
        """AC-02-04: DataLoader 배치가 (input_ids, attention_mask, labels) 딕셔너리 반환."""
        train_df, test_df = nsmc_data
        # 소규모 샘플로 빠르게 테스트
        train_sample = train_df.sample(n=200, random_state=42).reset_index(drop=True)
        test_sample = test_df.sample(n=40, random_state=42).reset_index(drop=True)

        train_loader, val_loader, test_loader = build_dataloaders(
            train_sample,
            test_sample,
            tokenizer=tokenizer,
            batch_size=16,
        )

        for loader_name, loader in [("train", train_loader), ("val", val_loader), ("test", test_loader)]:
            batch = next(iter(loader))
            assert isinstance(batch, dict), f"{loader_name} batch is not dict"
            assert "input_ids" in batch, f"{loader_name} missing input_ids"
            assert "attention_mask" in batch, f"{loader_name} missing attention_mask"
            assert "labels" in batch, f"{loader_name} missing labels"
            assert isinstance(batch["input_ids"], torch.Tensor), "input_ids must be Tensor"
            assert isinstance(batch["attention_mask"], torch.Tensor), "attention_mask must be Tensor"
            assert isinstance(batch["labels"], torch.Tensor), "labels must be Tensor"
