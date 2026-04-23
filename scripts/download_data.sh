#!/usr/bin/env bash
# NSMC 데이터셋 다운로드 스크립트
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_RAW="$PROJECT_ROOT/data/raw"

mkdir -p "$DATA_RAW"

echo "ratings_train.txt 다운로드 중..."
curl -L -o "$DATA_RAW/ratings_train.txt" \
    "https://raw.githubusercontent.com/e9t/nsmc/master/ratings_train.txt"

echo "ratings_test.txt 다운로드 중..."
curl -L -o "$DATA_RAW/ratings_test.txt" \
    "https://raw.githubusercontent.com/e9t/nsmc/master/ratings_test.txt"

echo "완료: $(wc -l < "$DATA_RAW/ratings_train.txt") 줄 (train), $(wc -l < "$DATA_RAW/ratings_test.txt") 줄 (test)"
