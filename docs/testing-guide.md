# 테스트 & 시뮬레이션 가이드

이 문서는 프로젝트를 로컬에서 처음부터 끝까지 실행하고 검증하는 방법을 설명한다.

---

## 사전 요구사항

```bash
# uv 설치 여부 확인
uv --version   # >= 0.4.x

# 의존성 설치
uv sync
```

---

## 1. 데이터 준비

```bash
# NSMC 원본 데이터 다운로드 (data/raw/에 저장)
bash scripts/download_data.sh
```

완료 후 확인:

```bash
wc -l data/raw/ratings_train.txt   # 150001 (헤더 포함)
wc -l data/raw/ratings_test.txt    #  50001 (헤더 포함)
```

---

## 2. 단위 테스트 (pytest)

### 빠른 전체 실행 (slow 마커 제외)

```bash
uv run pytest -v
```

`slow` 마커가 붙은 테스트(전체 데이터셋 기반 통합 테스트)는 기본적으로 실행되지 않는다.

### 테스트 파일별 실행

| 파일 | 대상 모듈 | 소요 시간 |
|------|-----------|-----------|
| `tests/test_data_loader.py` | `src/data_loader.py` | ~10s |
| `tests/test_preprocess.py` | `src/preprocess.py` | ~30s |
| `tests/test_baseline.py` | `src/baseline.py` | ~5s (unit), ~60s (slow) |
| `tests/test_train.py` | `src/train.py` | ~10s |

```bash
# 특정 파일만
uv run pytest tests/test_data_loader.py -v
uv run pytest tests/test_preprocess.py -v
uv run pytest tests/test_baseline.py -v
uv run pytest tests/test_train.py -v
```

### slow 테스트 포함 전체 실행 (실제 데이터 기반 AC 검증)

```bash
uv run pytest -v -m slow
```

---

## 3. 스프린트 자동 평가 (evaluator.py)

`sprint-contract.yaml`에 정의된 AC를 자동으로 판정한다.

```bash
# 단일 스프린트 평가 (JSON 출력)
uv run python .harness/evaluator.py --sprint sprint-01 --json
uv run python .harness/evaluator.py --sprint sprint-02 --json
uv run python .harness/evaluator.py --sprint sprint-03 --json
uv run python .harness/evaluator.py --sprint sprint-04 --json
uv run python .harness/evaluator.py --sprint sprint-05 --json
uv run python .harness/evaluator.py --sprint sprint-06 --json

# 평가 보고서 확인
cat .harness/sprints/sprint-01/evaluation-report.md
```

반환 값:

- `PASS` — AC 충족
- `FAIL` — AC 미충족 (stderr에 구체적 원인 출력)
- `SKIP` — `semantic_eval` 타입 (수동 또는 evaluator-llm 서브에이전트로 위임)

---

## 4. 모듈별 수동 실행

### 데이터 로더

```bash
uv run python -c "
from src.data_loader import load_nsmc
train, test = load_nsmc()
print(f'train: {len(train)}건, test: {len(test)}건')
print(train.head(3))
"
```

### 전처리 파이프라인

```bash
uv run python -c "
from src.data_loader import load_nsmc
from src.preprocess import build_dataloaders, split_dataframe
from transformers import AutoTokenizer
train_df, test_df = load_nsmc()
tokenizer = AutoTokenizer.from_pretrained('klue/roberta-base')
train_loader, val_loader, test_loader = build_dataloaders(
    train_df.sample(200, random_state=42).reset_index(drop=True),
    test_df.sample(40, random_state=42).reset_index(drop=True),
    tokenizer=tokenizer,
    batch_size=16,
)
batch = next(iter(train_loader))
print({k: v.shape for k, v in batch.items()})
"
```

### 베이스라인 모델 학습 + 평가

```bash
uv run python -c "
from src.baseline import run_baseline
metrics = run_baseline(save=True)
print(metrics)
"
# 결과물: artifacts/baseline_metrics.json
```

### BERT 파인튜닝

```bash
# 전체 학습 (GPU/MPS 권장, CPU에서는 수 시간 소요)
uv run python -m src.train
# 결과물: artifacts/checkpoints/best_<timestamp>.pt
#         artifacts/sprint-04_metrics.json
#         logs/training_<timestamp>.json
```

### 모델 평가

```bash
uv run python -m src.evaluate
# 결과물: artifacts/confusion_matrix.png
#         artifacts/eval_report.md
#         artifacts/sprint-05_metrics.json
```

---

## 5. Gradio UI 실행

```bash
# 기본 (http://localhost:7860)
bash scripts/serve.sh

# 포트 변경
bash scripts/serve.sh --port 7861

# Gradio 공개 링크 생성 (인터넷 필요)
bash scripts/serve.sh --share
```

UI 동작 확인:

```bash
uv run python -c "
from src.serve import predict, _CACHE
_CACHE.load()
label, conf, elapsed = predict('이 영화 정말 재미있어요!')
print(f'label={label}, conf={conf:.4f}, elapsed={elapsed:.3f}s')
"
```

---

## 6. 전체 파이프라인 검증 순서

처음부터 끝까지 순서대로 실행할 때는 아래 순서를 따른다.

```bash
# 1) 데이터
bash scripts/download_data.sh
uv run python .harness/evaluator.py --sprint sprint-01 --json

# 2) 전처리
uv run pytest tests/test_preprocess.py -v
uv run python .harness/evaluator.py --sprint sprint-02 --json

# 3) 베이스라인
uv run python -c "from src.baseline import run_baseline; run_baseline(save=True)"
uv run python .harness/evaluator.py --sprint sprint-03 --json

# 4) BERT 학습
uv run python -m src.train
uv run python .harness/evaluator.py --sprint sprint-04 --json

# 5) 평가
uv run python -m src.evaluate
uv run python .harness/evaluator.py --sprint sprint-05 --json

# 6) 서빙
bash scripts/serve.sh
```

---

## 7. 기대 지표 요약

| 단계 | 지표 | 목표값 |
|------|------|--------|
| sprint-03 베이스라인 | Accuracy | ≥ 0.85 |
| sprint-03 베이스라인 | Macro F1 | ≥ 0.83 |
| sprint-04 BERT Val | Accuracy | ≥ 0.90 |
| sprint-05 BERT Test | Accuracy | ≥ 0.90 |
| sprint-05 BERT Test | Macro F1 | ≥ 0.88 |
| sprint-06 서빙 | 응답 시간 | < 1.0s (CPU) |
| sprint-06 서빙 | 긍정 예시 신뢰도 | > 0.90 |

---

## 8. 트러블슈팅

### `FileNotFoundError: data/raw/ratings_train.txt`

```bash
bash scripts/download_data.sh
```

### `No checkpoint found`

sprint-04 학습이 완료되지 않은 상태. `uv run python -m src.train`을 먼저 실행한다.

### MPS/CUDA 미검출 경고

CPU로 자동 폴백되므로 기능 검증은 가능하나 학습 시간이 길어진다. `get_device()` 반환값을 확인한다.

```bash
uv run python -c "from src.train import get_device; print(get_device())"
```

### `uv sync` 실패

`uv.lock`을 수동으로 편집하지 않았는지 확인한다. 문제가 지속되면 `uv lock --upgrade`를 실행한다.
