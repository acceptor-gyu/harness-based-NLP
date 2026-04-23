# Sprint-01: 환경 세팅 및 데이터 로드

## 개요

| 항목 | 내용 |
|---|---|
| 스프린트 | sprint-01 |
| 브랜치 | `sprint-01/env-setup` |
| 판정 | PASS (1회 시도) |
| 완료일 | 2026-04-23 |

---

## 구현 내용

### 1. 프로젝트 환경 (`pyproject.toml`)

**설명**
`uv` 기반 패키지 관리. `uv sync --extra dev`로 모든 의존성 설치.

**핵심 의존성**

| 패키지 | 버전 | 용도 |
|---|---|---|
| torch | ≥2.4.0 | 딥러닝 프레임워크 |
| transformers | ≥4.46.0 | klue/roberta-base 파인튜닝 |
| scikit-learn | ≥1.5.0 | 베이스라인 모델 |
| pandas | ≥2.2.0 | 데이터 처리 |
| loguru | ≥0.7.0 | 로깅 |
| pytest | ≥8.3.0 | 테스트 (dev) |

선택 의존성: `serve` 그룹 (`gradio≥4.44.0`) — sprint-06 용.

**근거**
- **uv 선택**: `pip` 대비 의존성 해결 속도가 빠르고, `uv.lock`으로 환경을 완전히 고정할 수 있어 재현성이 보장된다. `conda`처럼 가상환경과 패키지 관리를 통합하면서도 표준 `pyproject.toml`을 그대로 사용한다.
- **dev/serve 그룹 분리**: 학습 서버에 Gradio를 설치할 필요가 없고, CI 환경에 pytest만 추가하면 되므로 실행 환경별 최소 설치를 유지한다.
- **버전 하한(≥) 방식**: 상한을 고정하면 보안 패치를 받지 못하는 문제가 생긴다. `uv.lock`이 실제 버전을 고정하므로 `pyproject.toml`에서는 하한만 명시하는 것이 관례에 맞다.

---

### 2. NSMC 데이터 (`data/raw/`)

**설명**
[e9t/nsmc](https://github.com/e9t/nsmc) 원본 데이터를 다운로드.

| 파일 | 크기 | 원본 행 수 | 결측 제거 후 |
|---|---|---|---|
| `ratings_train.txt` | 13.9 MB | 150,001 (헤더 포함) | 149,995건 |
| `ratings_test.txt` | 4.8 MB | 50,001 (헤더 포함) | 49,997건 |

컬럼 구조: `id` (int64) · `document` (str) · `label` (int64, 0=부정/1=긍정)

원본 데이터에 null document가 train 5건, test 3건 존재. `load_nsmc()` 내부에서 자동 제거.

**근거**
- **`data/raw/` 원본 보존**: 전처리된 데이터만 남기면 원본 재현이 불가능해진다. 원본을 별도로 보존하면 전처리 로직이 바뀌어도 raw → processed 파이프라인을 재실행할 수 있다. 이 디렉토리는 수정 금지 규칙으로 보호된다.
- **결측 제거를 로더에서 처리**: 원본 파일을 수정하지 않으면서도 하위 스프린트가 clean한 데이터를 전제로 개발할 수 있다. 제거 사실을 로그로 남겨 데이터 품질 이슈를 추적 가능하게 했다.

---

### 3. 데이터 로더 (`src/data_loader.py`)

**설명**

```
load_nsmc(train_path?, test_path?) → (train_df, test_df)
```

**처리 흐름**

```
TSV 읽기 (UTF-8, tab 구분)
  → 필수 컬럼 검증 (id, document, label)
  → NaN 제거 (dropna)
  → 빈 문자열 제거 (str.strip() == "")
  → 인덱스 리셋
  → 타입 변환 (label, id → int64)
```

- 경로 미지정 시 `data/raw/` 기본 경로 사용
- 파일 없을 때 `FileNotFoundError` — 재현 방법(curl 명령) 포함한 메시지 출력
- 결측 제거 시 `loguru`로 제거 건수 INFO 로그

**근거**
- **`train_path` / `test_path` 인자 노출**: 기본값을 제공하되 경로를 오버라이드 가능하게 해 테스트에서 픽스처 파일을 주입할 수 있다. 실제 NSMC 150만 건을 매 테스트마다 읽으면 CI가 느려진다.
- **필수 컬럼 검증**: NSMC 포맷이 바뀌거나 잘못된 파일이 들어왔을 때 `KeyError` 대신 명확한 `ValueError`를 발생시켜 원인 파악 시간을 줄인다.
- **NaN + 빈 문자열 두 단계 제거**: `dropna`만으로는 `"   "` 같은 공백만 있는 행이 걸러지지 않는다. 빈 문자열은 토크나이저에 빈 시퀀스를 만들어 학습 불안정을 유발하므로 로더 수준에서 차단한다.
- **`int64` 타입 강제**: pandas가 null 포함 컬럼을 `float64`로 읽는 경우가 있다. null 제거 후 명시적으로 `int64`로 변환해 하위 스프린트에서 타입 불일치 오류를 예방한다.
- **`pathlib.Path` 사용**: 문자열 경로 조합은 OS별 구분자 차이로 버그를 유발한다. `Path`는 `/` 연산자로 플랫폼 독립적인 경로를 만들고, `.exists()` 같은 메서드를 직접 제공해 가독성도 높다.
- **`loguru` 사용**: 표준 `logging` 모듈보다 설정이 간단하고, 포맷·레벨·파일 출력을 한 줄로 구성할 수 있다. `print()`는 로그 레벨·타임스탬프가 없어 운영 환경에서 추적이 어렵다.

---

### 4. 테스트 (`tests/test_data_loader.py`)

**설명**
9개 케이스, 전체 PASS. 실행: `uv run pytest tests/test_data_loader.py -v`

| 테스트 | 검증 내용 |
|---|---|
| `test_returns_tuple_of_dataframes` | 반환 타입이 `(DataFrame, DataFrame)` |
| `test_train_row_count` | train ≥ 149,990건 |
| `test_test_row_count` | test ≥ 49,990건 |
| `test_required_columns` | `id`, `document`, `label` 컬럼 존재 |
| `test_no_null_in_document` | document 컬럼 null = 0 |
| `test_no_empty_string_in_document` | document 빈 문자열 = 0 |
| `test_label_values_are_binary` | label 값이 {0, 1} |
| `test_raises_file_not_found` | 잘못된 경로에서 `FileNotFoundError` |
| `test_custom_paths` | 커스텀 경로 인자 정상 동작 |

**근거**
- **행 수를 정확한 값(150,000)이 아닌 하한(≥ 149,990)으로 검증**: 원본 NSMC에 결측이 몇 건 포함되어 있는지는 버전마다 다를 수 있다. 정확한 수를 하드코딩하면 데이터 소스가 조금만 바뀌어도 테스트가 깨진다. 하한은 "데이터가 거의 다 있다"는 의도를 표현하면서도 내성이 있다.
- **`test_custom_paths`에서 픽스처 파일 사용**: 실제 NSMC 파일(~14 MB)을 읽으면 테스트 속도가 느려지고 파일이 없는 환경에서는 실패한다. `tmp_path` 픽스처로 최소 TSV를 만들어 로더 로직만 격리 검증한다.
- **`test_raises_file_not_found`**: 에러 경로가 테스트되지 않으면 파일 없음 오류가 엉뚱한 스택트레이스로 나타날 수 있다. 예외 타입을 명시적으로 검증해 에러 메시지 품질을 보장한다.
- **`TestLoadNsmc` 클래스로 묶음**: 관련 테스트를 클래스로 묶으면 `pytest -k TestLoadNsmc`로 이 모듈만 선택 실행하기 쉽고, 스프린트가 늘어나도 파일별 테스트 클래스로 네임스페이스가 정리된다.

---

### 5. EDA 노트북 (`notebooks/01_eda.ipynb`)

**설명**
탐색 목적 전용 노트북. 실행 결과는 `artifacts/`에 저장.

| 섹션 | 내용 | 출력 파일 |
|---|---|---|
| 클래스 분포 | 긍정/부정 비율 (train/test) | `artifacts/eda_class_distribution.png` |
| 문서 길이 분포 | 문자 단위 히스토그램, 평균·중앙값 표시 | `artifacts/eda_length_distribution.png` |
| 결측값 현황 | null 처리 후 컬럼별 null 개수 확인 | — |

**근거**
- **노트북을 탐색 전용으로 제한**: 노트북에 전처리·학습 로직을 넣으면 재현이 어렵고 버전 관리가 복잡해진다. 실제 로직은 모두 `src/`에 두고, 노트북은 `src/` 함수를 호출해 결과를 시각화하는 용도로만 쓴다.
- **클래스 분포 확인**: NSMC는 긍정/부정이 약 50:50으로 균형 잡혀 있다고 알려져 있지만, 실제 로드된 데이터에서 직접 확인해야 이후 stratified split 비율 설정의 근거가 된다. 불균형이 크면 sprint-02의 분할 전략이 달라진다.
- **문서 길이 분포 확인**: `max_sequence_length: 128` (sprint-contract 제약)을 설정한 근거를 데이터로 검증한다. 대부분의 리뷰가 128 토큰 이내임을 확인해야 truncation으로 인한 정보 손실이 허용 범위 안에 있다고 판단할 수 있다. 이 결과는 sprint-02의 AC-02-01("토큰 길이 128 초과 비율 < 5%") 달성 가능성을 사전 판단하는 데 사용된다.

---

## 파일 구조

```
.
├── pyproject.toml
├── data/
│   └── raw/
│       ├── ratings_train.txt   # 원본 보존 (수정 금지)
│       └── ratings_test.txt
├── src/
│   └── data_loader.py          # load_nsmc() 구현
├── tests/
│   └── test_data_loader.py     # 9개 테스트
└── notebooks/
    └── 01_eda.ipynb
```

---

## 다음 스프린트 (sprint-02)

- `src/preprocess.py` 구현 (정규화, 클리닝)
- klue/roberta-base 토크나이저 적용
- Train/Val/Test 80/10/10 stratified 분할
- PyTorch DataLoader 구성 (`batch_size=32`)
