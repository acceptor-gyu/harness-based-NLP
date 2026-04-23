# Sprint-02: 전처리 파이프라인

## 개요

| 항목 | 내용 |
|---|---|
| 스프린트 | sprint-02 |
| 브랜치 | `sprint-02/preprocessing-pipeline` |
| 판정 | PASS |
| 완료일 | 2026-04-23 |

---

## 구현 내용

### 1. `src/preprocess.py` — 전처리 파이프라인 전체

**설명**

4개의 공개 함수와 1개의 Dataset 클래스로 구성된 단일 모듈이다.

- `clean_text(text, remove_stopwords)`: HTML 태그 제거 → 특수문자 제거(한글·영문·숫자·공백만 유지) → 연속 공백 단일화 → 선택적 불용어 제거 순으로 텍스트를 정제한다. 비문자열 입력은 빈 문자열로 변환한다.
- `NSMCDataset(texts, labels, tokenizer, max_length)`: PyTorch `Dataset` 서브클래스. 생성자에서 `tokenizer(..., truncation=True, padding="max_length", return_tensors="pt")`를 일괄 호출해 토큰화 결과를 메모리에 저장하고, `__getitem__`이 `{input_ids, attention_mask, labels}` 딕셔너리를 반환한다.
- `split_dataframe(train_df, test_df, val_ratio, random_seed)`: `sklearn.model_selection.train_test_split`을 사용해 원본 train DataFrame을 train/val로 stratified 분할한다. test_df는 그대로 사용한다. val 비율은 "전체(train + test) 대비"로 계산하므로, test의 비중을 역산해 `test_size`를 결정한다.
- `build_dataloaders(train_df, test_df, ...)`: 클리닝 → 빈 문자열 제거 → 분할 → Dataset 생성 → DataLoader 생성까지 파이프라인 전체를 단일 함수로 호출할 수 있도록 묶었다. `(train_loader, val_loader, test_loader)` 튜플을 반환한다.
- `compute_token_length_stats(texts, tokenizer, max_length)`: `truncation=False`로 실제 토큰 수를 측정해 mean, median, max, over_ratio(max_length 초과 비율) 통계를 반환한다. AC-02-01 검증에 사용된다.

**근거**

- `clean_text`에서 특수문자를 제거하고 한글·영문·숫자만 남기는 이유: NSMC 리뷰에는 이모지, 반복 특수문자가 다수 포함되어 있어 klue/roberta-base의 `[UNK]` 발생을 줄이고 최대 토큰 길이 128 내에 의미 있는 내용을 더 많이 담기 위함이다.
- `NSMCDataset` 생성자에서 일괄 토큰화를 수행하는 이유: `__getitem__` 호출 시마다 토큰화하면 DataLoader 워커 수만큼 중복 연산이 발생한다. 대신 생성 시 전체를 미리 인코딩해 텐서로 저장함으로써 학습 중 I/O 병목을 제거한다.
- `split_dataframe`에서 val 크기를 "전체 대비"로 계산하는 이유: AC-02-02가 val 크기를 "전체(train + test) 데이터의 10%"로 정의하기 때문이다. train DataFrame 내에서만 비율을 잡으면 실제 전체 대비 val이 8% 수준에 그쳐 AC를 위반한다.
- `build_dataloaders`에서 클리닝 후 빈 문자열을 제거하는 이유: 특수문자만으로 구성된 리뷰는 clean 후 공백만 남는다. 이런 샘플은 레이블 정보가 없는 노이즈이므로 DataLoader에 포함하지 않는다.
- `remove_stopwords=False`가 기본값인 이유: klue/roberta-base는 BPE 서브워드 기반 토크나이저로, 조사(`이`, `가`, `을` 등)가 앞 형태소와 결합해 인코딩된다. 공백 분리 후 불용어를 제거하면 형태소 경계가 달라져 토크나이저가 예상치 못한 분절을 생성할 수 있다. 따라서 기본적으로 비활성화하고 선택 옵션으로만 제공한다.

---

### 2. `tests/test_preprocess.py` — 단위 및 통합 테스트

**설명**

15개의 테스트가 4개의 테스트 클래스에 분산되어 있다.

- `TestCleanText` (6개): `clean_text`의 HTML 제거, 특수문자 제거, 공백 정규화, 빈 문자열, 비문자열 입력, 한글·영문·숫자 보존을 각각 검증한다.
- `TestSplitDataframe` (2개): 소규모 더미 DataFrame으로 val 비율(AC-02-02)과 레이블 분포 편차(AC-02-03)를 빠르게 검증한다.
- `TestNSMCDataset` (3개): `NSMCDataset`의 키 구성, 텐서 shape, DataLoader 배치 형식(AC-02-04)을 검증한다.
- `TestFullPipeline` (4개): 실제 NSMC 데이터로 AC-02-01~04를 순서대로 재검증한다. AC-02-01은 전체 train 대신 5000건 샘플로 속도를 단축한다.

`tokenizer`와 `nsmc_data` fixture는 `scope="module"`로 지정되어 테스트 실행 중 1회만 로드된다.

**근거**

- 단위 테스트(`TestCleanText`, `TestNSMCDataset`)와 통합 테스트(`TestFullPipeline`)를 분리한 이유: 단위 테스트는 더미 데이터로 빠르게 실행되어 코드 변경 시 즉각 피드백을 제공하고, 통합 테스트는 실제 데이터로 AC 수치를 보장한다.
- AC-02-01에서 5000건 샘플링을 사용하는 이유: 15만 건 전체를 토큰화하면 2분 이상 소요된다. 5000건 랜덤 샘플은 통계적으로 충분하며(신뢰 수준 99%, 오차 ±2%), 테스트 전체 실행 시간을 51초 이내로 유지한다.

---

## 파일 구조

```
NLP/
├── src/
│   └── preprocess.py          # 신규: 전처리 파이프라인
└── tests/
    └── test_preprocess.py     # 신규: 15개 테스트
```

---

## AC 결과

| AC | 설명 | 판정 | 실측값 |
|---|---|---|---|
| AC-02-01 | 토큰 길이 128 초과 샘플 비율 < 5% | PASS | over_ratio=0.00% (128 초과 0건) |
| AC-02-02 | Val 세트 크기가 전체의 10% ± 1% 범위 내 | PASS | val_ratio=10.00% (val=20,000 / total=199,992) |
| AC-02-03 | 레이블 분포가 train/val/test 간 편차 < 2%p | PASS | max_diff=0.46%p (train=49.88%, val=49.89%, test=50.35%) |
| AC-02-04 | DataLoader가 (input_ids, attention_mask, labels) 딕셔너리 배치 반환 | PASS | input_ids (32,128), attention_mask (32,128), labels (32,) |

---

## 다음 스프린트 (sprint-03)

**베이스라인 모델 (TF-IDF + Logistic Regression)**

- `src/baseline.py` 구현
- TF-IDF 벡터화 (`ngram=(1,2)`, `max_features=20000`)
- LogisticRegression 학습 (`C=1.0`, `max_iter=1000`)
- `artifacts/baseline_metrics.json` 저장 (accuracy, precision, recall, f1)
- Test Accuracy ≥ 0.85, Test Macro F1 ≥ 0.83 달성
