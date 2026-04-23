"""NSMC 데이터 로더 모듈.

ratings_train.txt / ratings_test.txt 를 로드하고,
결측값(NaN, 빈 문자열)을 제거한 DataFrame을 반환한다.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

DATA_RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
TRAIN_FILE = DATA_RAW_DIR / "ratings_train.txt"
TEST_FILE = DATA_RAW_DIR / "ratings_test.txt"


def _load_file(path: Path) -> pd.DataFrame:
    """TSV 파일을 읽어 결측값을 처리한 DataFrame을 반환한다."""
    if not path.exists():
        raise FileNotFoundError(
            f"데이터 파일을 찾을 수 없습니다: {path}\n"
            f"재현 방법: curl -L -o {path} https://raw.githubusercontent.com/e9t/nsmc/master/{path.name}"
        )

    df = pd.read_csv(path, sep="\t", encoding="utf-8")
    original_len = len(df)
    logger.debug(f"원본 로드: {path.name} → {original_len}건")

    # 결측값 처리: NaN 제거 후 빈 문자열도 제거
    df = df.dropna(subset=["document"])
    df = df[df["document"].str.strip() != ""]
    dropped = original_len - len(df)
    if dropped > 0:
        logger.info(f"결측값 {dropped}건 제거: {path.name} ({original_len} → {len(df)}건)")

    df = df.reset_index(drop=True)
    return df


def load_nsmc(
    train_path: Path | None = None,
    test_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """NSMC 데이터셋을 로드한다.

    Args:
        train_path: ratings_train.txt 경로. None이면 기본 경로 사용.
        test_path: ratings_test.txt 경로. None이면 기본 경로 사용.

    Returns:
        (train_df, test_df) 튜플.
        각 DataFrame 컬럼: id (int64), document (str), label (int64).

    Raises:
        FileNotFoundError: 데이터 파일이 없을 때.
    """
    train_path = train_path or TRAIN_FILE
    test_path = test_path or TEST_FILE

    logger.info("NSMC 데이터 로드 시작")
    train_df = _load_file(Path(train_path))
    test_df = _load_file(Path(test_path))

    logger.info(f"로드 완료 — train: {len(train_df)}건, test: {len(test_df)}건")

    # label 컬럼을 정수형으로 변환
    for df in (train_df, test_df):
        df["label"] = df["label"].astype("int64")
        df["id"] = df["id"].astype("int64")

    return train_df, test_df
