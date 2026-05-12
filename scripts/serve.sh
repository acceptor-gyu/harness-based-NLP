#!/usr/bin/env bash
# serve.sh — Gradio UI 로컬 실행 스크립트 (sprint-06)
#
# 사용법:
#   bash scripts/serve.sh               # 기본 (localhost:7860)
#   bash scripts/serve.sh --port 7861   # 포트 변경
#   bash scripts/serve.sh --share       # Gradio 공개 링크 생성
#
# 요구사항: uv 설치 필요 (https://github.com/astral-sh/uv)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== 한국어 감성 분석기 — Gradio 서버 시작 ==="
echo "프로젝트 루트: $PROJECT_ROOT"

# 의존성 확인
echo "의존성 확인 중..."
uv sync

# 서버 실행
echo "Gradio 서버를 http://localhost:7860 에서 시작합니다..."
uv run python -m src.serve "$@"
