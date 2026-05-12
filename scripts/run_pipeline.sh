#!/usr/bin/env bash
# 전체 파이프라인 실행 스크립트
# 실행: bash scripts/run_pipeline.sh [--skip-train] [--serve]
#
#   --skip-train   BERT 학습을 건너뜁니다 (기존 체크포인트 사용)
#   --serve        평가 완료 후 Gradio UI를 실행합니다
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# ── 옵션 파싱 ─────────────────────────────────────
SKIP_TRAIN=false
SERVE=false
for arg in "$@"; do
    case $arg in
        --skip-train) SKIP_TRAIN=true ;;
        --serve)      SERVE=true ;;
        *) echo "알 수 없는 옵션: $arg"; exit 1 ;;
    esac
done

# ── 유틸리티 ──────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*"; }
section() { echo ""; echo "══════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════"; }

# ── Step 1: 의존성 설치 ───────────────────────────
section "Step 1 / 5  의존성 설치 (uv sync)"
uv sync
log "완료"

# ── Step 2: 데이터 다운로드 ──────────────────────
section "Step 2 / 5  데이터 다운로드"
TRAIN_FILE="$PROJECT_ROOT/data/raw/ratings_train.txt"
TEST_FILE="$PROJECT_ROOT/data/raw/ratings_test.txt"

if [[ -f "$TRAIN_FILE" && -f "$TEST_FILE" ]]; then
    log "이미 존재합니다. 다운로드 건너뜁니다."
else
    bash "$SCRIPT_DIR/download_data.sh"
fi

TRAIN_LINES=$(wc -l < "$TRAIN_FILE")
TEST_LINES=$(wc -l < "$TEST_FILE")
log "train: $TRAIN_LINES 줄 / test: $TEST_LINES 줄"

# ── Step 3: 베이스라인 (TF-IDF + LogReg) ─────────
section "Step 3 / 5  베이스라인 학습 및 평가"
uv run python -m src.baseline
log "결과: artifacts/baseline_metrics.json"

# ── Step 4: BERT 파인튜닝 ─────────────────────────
section "Step 4 / 5  BERT 파인튜닝 (klue/roberta-base)"
if [[ "$SKIP_TRAIN" == "true" ]]; then
    CKPT_COUNT=$(ls "$PROJECT_ROOT/artifacts/checkpoints/best_"*.pt 2>/dev/null | wc -l || true)
    if [[ "$CKPT_COUNT" -eq 0 ]]; then
        log "체크포인트가 없습니다. --skip-train을 제거하고 다시 실행하세요."
        exit 1
    fi
    log "--skip-train: BERT 학습 건너뜁니다. 기존 체크포인트 사용."
else
    uv run python -m src.train
    log "결과: artifacts/checkpoints/best_*.pt, artifacts/sprint-04_metrics.json"
fi

# ── Step 5: 평가 ──────────────────────────────────
section "Step 5 / 5  Test 세트 평가"
uv run python -m src.evaluate
log "결과: artifacts/sprint-05_metrics.json, artifacts/confusion_matrix.png, artifacts/eval_report.md"

# ── 결과 요약 ─────────────────────────────────────
section "결과 요약"
if [[ -f "$PROJECT_ROOT/artifacts/baseline_metrics.json" ]]; then
    echo "[베이스라인]"
    uv run python -c "
import json
with open('artifacts/baseline_metrics.json') as f:
    m = json.load(f)
print(f'  Accuracy : {m[\"accuracy\"]:.4f}')
print(f'  Macro F1 : {m[\"f1\"]:.4f}')
"
fi
if [[ -f "$PROJECT_ROOT/artifacts/sprint-05_metrics.json" ]]; then
    echo "[BERT (klue/roberta-base)]"
    uv run python -c "
import json
with open('artifacts/sprint-05_metrics.json') as f:
    m = json.load(f)
print(f'  Accuracy : {m[\"test_accuracy\"]:.4f}')
print(f'  Macro F1 : {m[\"test_f1\"]:.4f}')
"
fi

echo ""
echo "산출물:"
echo "  artifacts/baseline_metrics.json   — 베이스라인 수치"
echo "  artifacts/sprint-04_metrics.json  — BERT 학습 로그"
echo "  artifacts/sprint-05_metrics.json  — BERT 테스트 수치"
echo "  artifacts/confusion_matrix.png    — Confusion Matrix"
echo "  artifacts/eval_report.md          — 비교 리포트"

# ── (선택) Gradio 서빙 ────────────────────────────
if [[ "$SERVE" == "true" ]]; then
    section "Gradio UI 시작 (http://localhost:7860)"
    bash "$SCRIPT_DIR/serve.sh"
fi
