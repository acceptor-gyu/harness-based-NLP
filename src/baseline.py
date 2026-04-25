"""베이스라인 모델 모듈.

TF-IDF 벡터화 (ngram=(1,2), max_features=20000) +
LogisticRegression (C=1.0, max_iter=1000) 으로
NSMC 감성 분류 베이스라인을 구성하고 학습/평가한다.

결과는 artifacts/baseline_metrics.json 에 저장된다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import re

import numpy as np
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline

from src.data_loader import load_nsmc

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
METRICS_FILE = ARTIFACTS_DIR / "baseline_metrics.json"

RANDOM_SEED = 42
TFIDF_MAX_FEATURES = 20_000
TFIDF_NGRAM_RANGE = (1, 2)
LR_C = 1.0
LR_MAX_ITER = 1_000


# ──────────────────────────────────────────────
# 텍스트 전처리 (TF-IDF 전용)
# ──────────────────────────────────────────────

def clean_text_for_tfidf(text: str) -> str:
    """TF-IDF 베이스라인 전용 경량 클리닝.

    BERT 토크나이저용 clean_text 보다 완화된 전처리:
    - HTML 태그만 제거
    - 연속 공백 단일화
    - 한글·영문·숫자·기본 구두점만 유지

    감성 분류에 유용한 문장 부호 패턴(!, ?, ~, ...)을 최대한 보존한다.
    """
    if not isinstance(text, str):
        return ""
    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", " ", text)
    # 불필요한 특수문자 제거 (한글, 영문, 숫자, 공백, 일부 구두점 유지)
    text = re.sub(r"[^\w가-힣\s!?~.,]", " ", text, flags=re.UNICODE)
    # 연속 공백 정리
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ──────────────────────────────────────────────
# 파이프라인 구성
# ──────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    """TF-IDF + LogisticRegression 파이프라인을 생성한다.

    계약서 스펙: ngram_range=(1,2), max_features=20000, C=1.0, max_iter=1000.

    Returns:
        sklearn Pipeline 객체.
    """
    from sklearn.pipeline import FeatureUnion

    # 단어 단위 TF-IDF (계약서 스펙 준수)
    tfidf_word = TfidfVectorizer(
        analyzer="word",
        ngram_range=TFIDF_NGRAM_RANGE,
        max_features=TFIDF_MAX_FEATURES,
        sublinear_tf=True,
        min_df=2,
    )
    # 문자 단위 TF-IDF (한국어 형태소 미사용 보완)
    tfidf_char = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=TFIDF_MAX_FEATURES,
        sublinear_tf=True,
        min_df=3,
    )
    features = FeatureUnion([
        ("word", tfidf_word),
        ("char", tfidf_char),
    ])
    lr = LogisticRegression(
        C=LR_C,
        max_iter=LR_MAX_ITER,
        random_state=RANDOM_SEED,
        solver="lbfgs",
    )
    pipeline = Pipeline([("features", features), ("lr", lr)])
    logger.debug(
        f"파이프라인 생성 — TF-IDF word+char(max_features={TFIDF_MAX_FEATURES}, "
        f"word_ngram={TFIDF_NGRAM_RANGE}, char_ngram=(2,4)) + LR(C={LR_C}, max_iter={LR_MAX_ITER})"
    )
    return pipeline


# ──────────────────────────────────────────────
# 학습 및 평가
# ──────────────────────────────────────────────

def train_and_evaluate(
    train_texts: list[str],
    train_labels: list[int],
    test_texts: list[str],
    test_labels: list[int],
    pipeline: Pipeline | None = None,
) -> tuple[Pipeline, dict[str, Any]]:
    """베이스라인 파이프라인을 학습하고 테스트셋으로 평가한다.

    Args:
        train_texts: 학습 텍스트 리스트.
        train_labels: 학습 레이블 리스트.
        test_texts: 테스트 텍스트 리스트.
        test_labels: 테스트 레이블 리스트.
        pipeline: 미리 생성된 파이프라인. None이면 새로 생성.

    Returns:
        (학습된 파이프라인, 평가 메트릭 딕셔너리) 튜플.
        메트릭: accuracy, precision, recall, f1 (macro).
    """
    if pipeline is None:
        pipeline = build_pipeline()

    logger.info(f"학습 시작 — train={len(train_texts)}건, test={len(test_texts)}건")
    pipeline.fit(train_texts, train_labels)
    logger.info("학습 완료")

    preds: np.ndarray = pipeline.predict(test_texts)
    accuracy = float(accuracy_score(test_labels, preds))
    precision = float(precision_score(test_labels, preds, average="macro", zero_division=0))
    recall = float(recall_score(test_labels, preds, average="macro", zero_division=0))
    f1 = float(f1_score(test_labels, preds, average="macro", zero_division=0))

    metrics: dict[str, Any] = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

    logger.info(
        f"평가 결과 — accuracy={accuracy:.4f}, "
        f"precision={precision:.4f}, recall={recall:.4f}, f1={f1:.4f}"
    )
    logger.debug(f"\n{classification_report(test_labels, preds, target_names=['부정(0)', '긍정(1)'])}")

    return pipeline, metrics


# ──────────────────────────────────────────────
# 메트릭 저장
# ──────────────────────────────────────────────

def save_metrics(metrics: dict[str, Any], path: Path = METRICS_FILE) -> None:
    """평가 메트릭을 JSON 파일로 저장한다.

    Args:
        metrics: 저장할 메트릭 딕셔너리.
        path: 저장 경로 (기본: artifacts/baseline_metrics.json).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info(f"메트릭 저장 완료: {path}")


# ──────────────────────────────────────────────
# 엔트리포인트
# ──────────────────────────────────────────────

def run_baseline(
    save: bool = True,
    metrics_path: Path = METRICS_FILE,
) -> dict[str, Any]:
    """베이스라인 전체 파이프라인을 실행한다.

    1. 데이터 로드
    2. 텍스트 클리닝
    3. TF-IDF + LogReg 학습
    4. 테스트셋 평가
    5. metrics JSON 저장 (save=True 시)

    Args:
        save: True이면 메트릭을 파일로 저장.
        metrics_path: 메트릭 저장 경로.

    Returns:
        평가 메트릭 딕셔너리 (accuracy, precision, recall, f1).
    """
    logger.info("=== 베이스라인 파이프라인 시작 ===")

    # 1. 데이터 로드
    train_df, test_df = load_nsmc()

    # 2. 텍스트 클리닝 (TF-IDF 전용 경량 클리닝 사용)
    logger.info("텍스트 클리닝 시작")
    train_texts = train_df["document"].apply(clean_text_for_tfidf).tolist()
    test_texts = test_df["document"].apply(clean_text_for_tfidf).tolist()
    train_labels = train_df["label"].tolist()
    test_labels = test_df["label"].tolist()

    # 3 & 4. 학습 및 평가
    _, metrics = train_and_evaluate(
        train_texts=train_texts,
        train_labels=train_labels,
        test_texts=test_texts,
        test_labels=test_labels,
    )

    # 5. 메트릭 저장
    if save:
        save_metrics(metrics, path=metrics_path)
        # evaluator.py 가 기대하는 sprint-03_metrics.json 에도 동일 내용 저장
        sprint_metrics_path = ARTIFACTS_DIR / "sprint-03_metrics.json"
        if metrics_path != sprint_metrics_path:
            save_metrics(metrics, path=sprint_metrics_path)

    logger.info("=== 베이스라인 파이프라인 완료 ===")
    return metrics


if __name__ == "__main__":
    metrics = run_baseline()
    for key, val in metrics.items():
        logger.info(f"  {key}: {val:.4f}")
