# Sprint-03: 베이스라인 모델 (TF-IDF + Logistic Regression)

## 개요

| 항목 | 내용 |
|---|---|
| 스프린트 | sprint-03 |
| 브랜치 | `sprint-03/baseline-model` |
| 판정 | PASS |
| 완료일 | 2026-04-25 |

---

## 구현 내용

### 1. `src/baseline.py` — TF-IDF + LogisticRegression 파이프라인

**설명**

5개의 공개 함수로 구성된 단일 모듈이다.

- `clean_text_for_tfidf(text)`: TF-IDF 전용 경량 텍스트 클리닝 함수. HTML 태그 제거 → 한글·영문·숫자·공백 및 일부 구두점(`!`, `?`, `~`, `.`, `,`) 이외 문자 제거 → 연속 공백 단일화 순으로 처리한다. 비문자열 입력은 빈 문자열로 변환한다.
- `build_pipeline()`: `FeatureUnion`으로 word TF-IDF(`analyzer="word"`, `ngram_range=(1,2)`, `max_features=20000`)와 char TF-IDF(`analyzer="char_wb"`, `ngram_range=(2,4)`, `max_features=20000`)를 결합한 특성 추출기에 `LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs")`을 연결한 `sklearn.pipeline.Pipeline`을 반환한다.
- `train_and_evaluate(train_texts, train_labels, test_texts, test_labels, pipeline)`: 파이프라인을 학습하고 테스트셋에서 accuracy, precision, recall, f1(macro) 4개 메트릭을 반환한다. `pipeline` 인자가 `None`이면 `build_pipeline()`을 내부에서 호출한다.
- `save_metrics(metrics, path)`: 메트릭 딕셔너리를 `artifacts/baseline_metrics.json`에 JSON으로 저장한다. 저장 디렉터리가 없으면 자동 생성한다.
- `run_baseline(save, metrics_path)`: 데이터 로드 → 텍스트 클리닝 → 학습/평가 → 메트릭 저장의 전체 흐름을 단일 호출로 실행한다. evaluator.py가 참조하는 `artifacts/sprint-03_metrics.json`에도 동일 내용을 자동으로 이중 저장한다.

**근거**

- `clean_text_for_tfidf`를 `src/preprocess.py`의 `clean_text`와 별도로 정의한 이유: BERT용 전처리는 `[UNK]` 최소화가 목적이라 특수문자를 엄격히 제거하지만, TF-IDF는 `!`, `?`, `~` 같은 감성 신호 문자를 보존해야 분류 성능이 높아지기 때문이다. 동일 함수를 재사용하면 TF-IDF의 특성 활용 기회가 줄어든다.
- `FeatureUnion`으로 word + char TF-IDF를 결합한 이유: 한국어는 형태소 분석기 없이 공백 기반 토크나이징만으로는 어근 정보가 손실된다. 문자 단위 n-gram(`char_wb`, `(2,4)`)을 추가하면 형태소 경계를 넘어 부분 어형을 학습할 수 있어, 형태소 분석기 없이도 한국어 어휘 변형에 어느 정도 강인해진다.
- `sublinear_tf=True`를 적용한 이유: TF 값에 로그 스케일(`1 + log(tf)`)을 적용하면 고빈도 단어의 과도한 가중치를 억제해 희소 단어의 신호도 살릴 수 있어 감성 분류 성능이 개선된다.
- `solver="lbfgs"`를 명시한 이유: scikit-learn 기본 solver가 버전에 따라 다를 수 있어 재현성 보장을 위해 명시했다. lbfgs는 다중 클래스 및 대규모 특성에도 안정적이다.
- `run_baseline`이 `sprint-03_metrics.json`을 이중 저장하는 이유: evaluator.py는 `artifacts/sprint-03_metrics.json`을 기준으로 metric_threshold AC를 판정하고, 사용자는 `artifacts/baseline_metrics.json`을 관례적으로 참조한다. 두 경로를 모두 충족하기 위해 동일 내용을 두 파일에 저장한다.

---

### 2. `tests/test_baseline.py` — 베이스라인 테스트 스위트

**설명**

6개의 단위 테스트와 3개의 통합 테스트로 구성된다.

단위 테스트:
- `test_build_pipeline_returns_pipeline`: `build_pipeline()`이 `Pipeline` 인스턴스를 반환하고 `features`, `lr` 두 스텝이 존재하는지 확인한다.
- `test_build_pipeline_tfidf_params`: `FeatureUnion` 내 word TF-IDF의 `ngram_range=(1,2)`, `max_features=20000`이 계약서 스펙과 일치하는지 확인한다.
- `test_build_pipeline_lr_params`: `LogisticRegression`의 `C=1.0`, `max_iter=1000`이 스펙과 일치하는지 확인한다.
- `test_train_and_evaluate_small`: 소규모 더미 데이터 6건으로 `train_and_evaluate`가 accuracy, precision, recall, f1 키를 포함한 딕셔너리를 반환하고 값이 `[0, 1]` 범위인지 확인한다.
- `test_save_metrics_creates_file`: `tmp_path` 픽스처를 사용해 `save_metrics`가 JSON 파일을 생성하고 값이 정확히 저장되는지 확인한다.
- `test_save_metrics_required_keys`: 저장된 JSON에 필수 4개 키가 모두 있는지 확인한다.

통합 테스트 (`@pytest.mark.slow`):
- `test_run_baseline_accuracy`: AC-03-01 — 전체 NSMC 데이터로 `run_baseline()`을 실행해 accuracy ≥ 0.85를 검증한다.
- `test_run_baseline_f1`: AC-03-02 — 동일 실행으로 macro F1 ≥ 0.83을 검증한다.
- `test_run_baseline_metrics_file_schema`: AC-03-03 — 저장된 JSON에 필수 4개 키가 있고 값이 `[0, 1]` 범위인지 검증한다.

**근거**

- 단위 테스트가 파라미터 일치를 검사하는 이유: 파이프라인 설정 오류는 학습 후에야 성능 저하로 드러나 원인 추적이 어렵다. 빌드 시점에 스펙 준수를 확인하면 회귀를 빠르게 감지할 수 있다.
- 통합 테스트에 `@pytest.mark.slow` 마크를 붙인 이유: NSMC 전체 학습은 약 50초가 소요된다. CI에서는 단위 테스트만 빠르게 실행하고 전체 통합 테스트는 별도 단계에서 `--slow` 플래그로 실행할 수 있도록 분리한다.
- 통합 테스트가 `tmp_path`를 사용하는 이유: 테스트 간 아티팩트 파일 충돌을 방지하고, `artifacts/` 디렉터리를 오염시키지 않기 위해 pytest의 임시 경로 픽스처를 활용한다.

---

### 3. `artifacts/baseline_metrics.json` — 평가 메트릭 결과 파일

**설명**

`run_baseline()` 실행 결과로 생성되는 JSON 파일이다. 4개 키(`accuracy`, `precision`, `recall`, `f1`)를 포함하며, 모두 macro 평균 기준 float 값이다. 실측값은 다음과 같다:

```json
{
  "accuracy": 0.861231673900434,
  "precision": 0.8612558719463237,
  "recall": 0.8612650927416401,
  "f1": 0.8612315059704052
}
```

**근거**

- precision, recall, f1을 모두 macro 평균으로 기록한 이유: NSMC 레이블 분포는 긍정/부정이 대략 균등하지만, 이후 스프린트에서 BERT와 성능을 비교할 때 클래스별 불균형 영향 없이 일관된 기준으로 비교하기 위해 macro를 채택했다.
- `artifacts/`에 저장하는 이유: `data/raw/`는 원본 보존 원칙으로 수정이 금지되고, `src/`는 코드 전용 디렉터리이다. 모델 결과물은 `artifacts/`에 분리 저장해 코드와 산출물을 명확히 구분한다.

---

### 4. `pyproject.toml` — `slow` 마크 등록 추가

**설명**

`[tool.pytest.ini_options]` 섹션의 `markers` 항목에 `"slow: 전체 데이터셋으로 실행하는 통합 테스트 (학습 포함)"` 마크를 추가했다. 이로써 `pytest --markers` 실행 시 알 수 없는 마크 경고 없이 `@pytest.mark.slow` 데코레이터를 사용할 수 있다.

**근거**

- pytest는 등록되지 않은 마크에 경고를 발생시키며, `--strict-markers` 옵션 사용 시 오류로 처리된다. 사전에 마크를 등록하면 마크 기반 테스트 필터링(`pytest -m "not slow"`)을 안전하게 활용할 수 있다.

---

## 파일 구조

```
NLP/
├── src/
│   └── baseline.py              # 신규: TF-IDF + LogReg 베이스라인 구현
├── tests/
│   └── test_baseline.py         # 신규: 단위 6개 + 통합 3개 테스트
├── artifacts/
│   └── baseline_metrics.json    # 신규: 평가 메트릭 결과
└── pyproject.toml               # 수정: slow 마크 등록 추가
```

---

## AC 결과

| AC | 설명 | 판정 | 실측값 |
|---|---|---|---|
| AC-03-01 | Test Accuracy ≥ 0.85 | PASS | 0.8612 |
| AC-03-02 | Test Macro F1 ≥ 0.83 | PASS | 0.8612 |
| AC-03-03 | baseline_metrics.json에 accuracy, precision, recall, f1 저장 | PASS | 4개 키 모두 존재 |
| AC-03-04 | pytest tests/test_baseline.py 전체 통과 | PASS | 9/9 통과 (50.28s) |

---

## 다음 스프린트 (sprint-04)

**BERT 파인튜닝**: `klue/roberta-base` 기반 `AutoModelForSequenceClassification`을 사용해 전이 학습을 수행한다. AdamW 옵티마이저와 Linear Warmup 스케줄러(warmup_ratio=0.1)를 적용하고, epoch=3, lr=2e-5, weight_decay=0.01로 학습한다. Val loss 기반 Early Stopping(patience=1)을 구현하고, 최적 체크포인트를 `artifacts/checkpoints/best_<timestamp>.pt`로 저장한다. 목표 Val Accuracy ≥ 0.90.
