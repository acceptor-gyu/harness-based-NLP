"""src/data_loader.py 단위 테스트."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import load_nsmc


class TestLoadNsmc:
    def test_returns_tuple_of_dataframes(self) -> None:
        train_df, test_df = load_nsmc()
        assert isinstance(train_df, pd.DataFrame)
        assert isinstance(test_df, pd.DataFrame)

    def test_train_row_count(self) -> None:
        """결측값 제거 후 train은 최소 149990건 이상이어야 한다."""
        train_df, _ = load_nsmc()
        assert len(train_df) >= 149990, f"예상 >=149990건, 실제 {len(train_df)}건"

    def test_test_row_count(self) -> None:
        """결측값 제거 후 test는 최소 49990건 이상이어야 한다."""
        _, test_df = load_nsmc()
        assert len(test_df) >= 49990, f"예상 >=49990건, 실제 {len(test_df)}건"

    def test_required_columns(self) -> None:
        train_df, test_df = load_nsmc()
        for df in (train_df, test_df):
            assert "id" in df.columns
            assert "document" in df.columns
            assert "label" in df.columns

    def test_no_null_in_document(self) -> None:
        train_df, test_df = load_nsmc()
        assert train_df["document"].isnull().sum() == 0, "train document 컬럼에 null 존재"
        assert test_df["document"].isnull().sum() == 0, "test document 컬럼에 null 존재"

    def test_no_empty_string_in_document(self) -> None:
        train_df, test_df = load_nsmc()
        assert (train_df["document"].str.strip() == "").sum() == 0, "train document에 빈 문자열 존재"
        assert (test_df["document"].str.strip() == "").sum() == 0, "test document에 빈 문자열 존재"

    def test_label_values_are_binary(self) -> None:
        train_df, test_df = load_nsmc()
        for df in (train_df, test_df):
            assert set(df["label"].unique()).issubset({0, 1}), f"라벨 값 범위 오류: {df['label'].unique()}"

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_nsmc(train_path=tmp_path / "nonexistent.txt")

    def test_custom_paths(self, tmp_path: Path) -> None:
        """커스텀 경로로 로드 가능한지 확인."""
        tsv_content = "id\tdocument\tlabel\n1\t재미있다\t1\n2\t별로다\t0\n"
        train_file = tmp_path / "train.txt"
        test_file = tmp_path / "test.txt"
        train_file.write_text(tsv_content, encoding="utf-8")
        test_file.write_text(tsv_content, encoding="utf-8")

        train_df, test_df = load_nsmc(train_path=train_file, test_path=test_file)
        assert len(train_df) == 2
        assert len(test_df) == 2
