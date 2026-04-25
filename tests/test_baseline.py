"""베이스라인 모델 테스트.

AC-03-01: Test Accuracy >= 0.85
AC-03-02: Test Macro F1 >= 0.83
AC-03-03: artifacts/baseline_metrics.json 에 accuracy, precision, recall, f1 저장
AC-03-04: pytest tests/test_baseline.py 전체 통과 (이 파일 자체)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.baseline import (
    ARTIFACTS_DIR,
    METRICS_FILE,
    build_pipeline,
    run_baseline,
    save_metrics,
    train_and_evaluate,
)


# ──────────────────────────────────────────────
# 유닛 테스트 — 파이프라인 빌드
# ──────────────────────────────────────────────


def test_build_pipeline_returns_pipeline() -> None:
    """build_pipeline()이 올바른 sklearn Pipeline을 반환하는지 확인한다."""
    from sklearn.pipeline import Pipeline

    pipeline = build_pipeline()
    assert isinstance(pipeline, Pipeline), "Pipeline 객체가 반환되어야 한다"
    assert "features" in pipeline.named_steps, "features 스텝이 있어야 한다"
    assert "lr" in pipeline.named_steps, "lr 스텝이 있어야 한다"


def test_build_pipeline_tfidf_params() -> None:
    """TF-IDF word 파라미터가 계약서 스펙과 일치하는지 확인한다."""
    pipeline = build_pipeline()
    feature_union = pipeline.named_steps["features"]
    # FeatureUnion 내부에서 word TF-IDF 접근
    tfidf_word = dict(feature_union.transformer_list)["word"]
    assert tfidf_word.ngram_range == (1, 2), f"ngram_range 불일치: {tfidf_word.ngram_range}"
    assert tfidf_word.max_features == 20_000, f"max_features 불일치: {tfidf_word.max_features}"


def test_build_pipeline_lr_params() -> None:
    """LogisticRegression 파라미터가 계약서 스펙과 일치하는지 확인한다."""
    pipeline = build_pipeline()
    lr = pipeline.named_steps["lr"]
    assert lr.C == 1.0, f"C 불일치: {lr.C}"
    assert lr.max_iter == 1_000, f"max_iter 불일치: {lr.max_iter}"


# ──────────────────────────────────────────────
# 유닛 테스트 — train_and_evaluate 소규모
# ──────────────────────────────────────────────


def test_train_and_evaluate_small() -> None:
    """소규모 데이터로 train_and_evaluate가 정상 동작하는지 확인한다."""
    train_texts = [
        "정말 재미있는 영화였어요",
        "너무 좋았어요 최고",
        "별로였어요 실망",
        "최악이에요 정말 별로",
        "감동적이고 아름다운 영화",
        "시간 낭비 추천 안 함",
    ]
    train_labels = [1, 1, 0, 0, 1, 0]
    test_texts = ["좋아요", "별로에요"]
    test_labels = [1, 0]

    pipeline, metrics = train_and_evaluate(train_texts, train_labels, test_texts, test_labels)

    assert "accuracy" in metrics, "metrics에 accuracy가 없다"
    assert "precision" in metrics, "metrics에 precision이 없다"
    assert "recall" in metrics, "metrics에 recall이 없다"
    assert "f1" in metrics, "metrics에 f1이 없다"
    assert 0.0 <= metrics["accuracy"] <= 1.0, f"accuracy 범위 오류: {metrics['accuracy']}"
    assert 0.0 <= metrics["f1"] <= 1.0, f"f1 범위 오류: {metrics['f1']}"


# ──────────────────────────────────────────────
# 유닛 테스트 — save_metrics
# ──────────────────────────────────────────────


def test_save_metrics_creates_file(tmp_path: Path) -> None:
    """save_metrics가 올바른 JSON 파일을 생성하는지 확인한다."""
    metrics = {"accuracy": 0.88, "precision": 0.87, "recall": 0.86, "f1": 0.865}
    out_file = tmp_path / "metrics.json"
    save_metrics(metrics, path=out_file)

    assert out_file.exists(), f"파일이 생성되지 않았다: {out_file}"
    with out_file.open(encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["accuracy"] == pytest.approx(0.88, abs=1e-6)
    assert loaded["precision"] == pytest.approx(0.87, abs=1e-6)
    assert loaded["recall"] == pytest.approx(0.86, abs=1e-6)
    assert loaded["f1"] == pytest.approx(0.865, abs=1e-6)


def test_save_metrics_required_keys(tmp_path: Path) -> None:
    """저장된 JSON에 필수 키가 모두 존재하는지 확인한다."""
    metrics = {"accuracy": 0.90, "precision": 0.89, "recall": 0.91, "f1": 0.90}
    out_file = tmp_path / "test_metrics.json"
    save_metrics(metrics, path=out_file)

    with out_file.open(encoding="utf-8") as f:
        loaded = json.load(f)

    for key in ("accuracy", "precision", "recall", "f1"):
        assert key in loaded, f"필수 키 누락: {key}"


# ──────────────────────────────────────────────
# 통합 테스트 — 전체 파이프라인 (AC-03-01 ~ AC-03-03)
# ──────────────────────────────────────────────


@pytest.mark.slow
def test_run_baseline_accuracy(tmp_path: Path) -> None:
    """AC-03-01: Test Accuracy >= 0.85."""
    metrics_path = tmp_path / "baseline_metrics.json"
    metrics = run_baseline(save=True, metrics_path=metrics_path)

    accuracy = metrics["accuracy"]
    assert accuracy >= 0.85, (
        f"AC-03-01 FAIL: Test Accuracy={accuracy:.4f} < 0.85\n"
        f"재현: uv run python -c \"from src.baseline import run_baseline; run_baseline()\""
    )


@pytest.mark.slow
def test_run_baseline_f1(tmp_path: Path) -> None:
    """AC-03-02: Test Macro F1 >= 0.83."""
    metrics_path = tmp_path / "baseline_metrics.json"
    metrics = run_baseline(save=True, metrics_path=metrics_path)

    f1 = metrics["f1"]
    assert f1 >= 0.83, (
        f"AC-03-02 FAIL: Test Macro F1={f1:.4f} < 0.83\n"
        f"재현: uv run python -c \"from src.baseline import run_baseline; run_baseline()\""
    )


@pytest.mark.slow
def test_run_baseline_metrics_file_schema(tmp_path: Path) -> None:
    """AC-03-03: artifacts/baseline_metrics.json에 accuracy, precision, recall, f1 저장."""
    metrics_path = tmp_path / "baseline_metrics.json"
    run_baseline(save=True, metrics_path=metrics_path)

    assert metrics_path.exists(), (
        f"AC-03-03 FAIL: metrics 파일이 존재하지 않는다: {metrics_path}\n"
        "재현: uv run python -c \"from src.baseline import run_baseline; run_baseline()\""
    )

    with metrics_path.open(encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {"accuracy", "precision", "recall", "f1"}
    missing = required_keys - set(data.keys())
    assert not missing, (
        f"AC-03-03 FAIL: 필수 키 누락: {missing}\n"
        f"실제 키: {list(data.keys())}"
    )

    for key in required_keys:
        val = data[key]
        assert isinstance(val, (int, float)), f"{key} 값이 숫자가 아니다: {type(val)}"
        assert 0.0 <= val <= 1.0, f"{key} 값이 [0, 1] 범위를 벗어났다: {val}"
