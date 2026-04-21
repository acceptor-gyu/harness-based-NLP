# Tech Stack 설명 및 선택 근거

이 문서는 `.harness/sprint-contract.yaml`의 `tech_stack` 항목에 기재된 각 도구와 기술에 대한 설명과 이 프로젝트에서 선택한 이유를 정리한다.

---

## 언어 — Python 3.11

### 설명
Python의 3.11 버전. 3.10 대비 인터프리터 자체 속도가 10~60% 향상되었고, 예외 메시지가 더 구체적으로 개선되었다.

### 선택 근거
- PyTorch, HuggingFace, scikit-learn 등 주요 ML 라이브러리가 모두 3.11을 안정 지원한다.
- 3.12는 일부 C 확장 호환성 문제가 남아있어 ML 환경에서 3.11이 사실상 표준이다.
- 타입 힌트 문법(`X | Y`, `Self`, `TypeVarTuple`)이 3.11에서 완성도가 높아 코드 품질 유지에 유리하다.

---

## 프레임워크 — PyTorch 2.4 + HuggingFace Transformers 4.46

### PyTorch 2.4

**설명**: Facebook(Meta)이 주도하는 딥러닝 프레임워크. 동적 계산 그래프(define-by-run)를 기반으로 하여 일반 Python 코드처럼 모델을 작성하고 디버깅할 수 있다. 2.x 이후 `torch.compile()`로 정적 그래프 수준의 최적화도 가능하다.

**선택 근거**
- 연구 및 교육 환경에서 TensorFlow보다 압도적으로 많이 사용되어 레퍼런스가 풍부하다.
- HuggingFace Transformers의 기본 백엔드가 PyTorch다.
- MPS(Apple Silicon) 가속을 공식 지원하여 Mac 환경에서도 GPU 학습이 가능하다.
- 동적 그래프 특성상 BERT 계열 모델의 가변 길이 입력 처리가 직관적이다.

### HuggingFace Transformers 4.46

**설명**: 사전학습 언어 모델을 쉽게 불러오고 파인튜닝할 수 있는 라이브러리. `AutoModelForSequenceClassification`, `AutoTokenizer` 등 통일된 API로 수백 개의 모델을 동일한 코드로 다룰 수 있다.

**선택 근거**
- `klue/roberta-base` 모델이 HuggingFace Hub에 올라와 있어 한 줄로 로드 가능하다.
- 토크나이저, 모델, 학습 유틸리티가 통합되어 있어 파인튜닝 코드가 간결해진다.
- `Trainer` API를 쓰지 않더라도 `AutoModel`만으로 커스텀 학습 루프를 작성하기 쉽다.
- 커뮤니티가 크고 버그 수정이 빨라 장기 유지보수에 유리하다.

---

## 베이스라인 — scikit-learn 1.5

### 설명
전통적인 머신러닝 알고리즘(회귀, 분류, 클러스터링 등)을 통일된 `fit/predict` API로 제공하는 라이브러리. TF-IDF 벡터화(`TfidfVectorizer`)와 로지스틱 회귀(`LogisticRegression`)가 포함되어 있다.

### 선택 근거
- BERT 파인튜닝 결과를 평가하려면 비교 기준(베이스라인)이 필요하다. scikit-learn의 TF-IDF + LR은 구현이 빠르고 성능이 검증된 텍스트 분류 베이스라인이다.
- 의존성이 가볍고 학습 속도가 빠르다 (GPU 불필요).
- BERT가 실제로 얼마나 개선되었는지 정량적으로 보여주는 비교 지점을 제공한다.

---

## 데이터 — NSMC (Naver Sentiment Movie Corpus)

### 설명
네이버 영화 리뷰에서 수집한 한국어 감성 분류 데이터셋. 긍정(1)·부정(0) 이진 레이블을 가진 리뷰 20만 건(train 15만, test 5만)으로 구성된다. 한국어 NLP 연구의 사실상 표준 벤치마크다.

**컬럼 구조**: `id`, `document` (리뷰 텍스트), `label` (0 또는 1)

### 선택 근거
- 공개 데이터셋으로 별도 계약 없이 무료로 사용 가능하다.
- 충분한 크기(20만 건)로 딥러닝 모델 학습에 적합하다.
- 선행 연구 결과가 많아 목표 성능 수치를 정량 설정하기 쉽다 (BERT 계열 ~91% 수준이 일반적).
- 한국어 특화 전처리와 토크나이저의 효과를 직접 확인할 수 있다.

---

## 모델 — klue/roberta-base

### 설명
KLUE(Korean Language Understanding Evaluation) 벤치마크를 위해 한국어 데이터로 사전학습된 RoBERTa 모델. RoBERTa는 BERT의 학습 방식을 개선(NSP 제거, 동적 마스킹, 더 많은 데이터)한 모델이다. `klue/roberta-base`는 약 1억 1천만 개의 파라미터를 가진다.

### 선택 근거
- 한국어 전용 사전학습 모델이므로 다국어 모델(mBERT, XLM-R)보다 한국어 태스크에서 성능이 높다.
- KLUE 벤치마크 기준 한국어 감성 분석에서 상위권 성능을 보인다.
- HuggingFace Hub에 공개되어 있어 `from_pretrained("klue/roberta-base")`로 즉시 사용 가능하다.
- `base` 크기로 GPU 메모리 부담이 적고 파인튜닝 시간이 합리적이다 (large 대비 약 1/4).

---

## 패키지 매니저 — uv

### 설명
Rust로 작성된 Python 패키지 및 프로젝트 관리 도구. `pip + venv + pip-tools`를 하나로 통합한다. `pyproject.toml`에 직접 의존성을, `uv.lock`에 전이 의존성 잠금 정보를 관리한다.

### 선택 근거
자세한 내용은 [uv_vs_pip.md](./uv_vs_pip.md) 참조.

핵심 이유: **재현성**(`uv sync` 한 번으로 동일 환경), **속도**(pip 대비 10~100배), **하네스 실행 일관성**(`uv run`으로 가상환경 활성화 없이 실행).

---

## 테스트 — pytest

### 설명
Python 표준 테스트 프레임워크. 함수 이름이 `test_`로 시작하면 자동 수집되고, `assert` 문만으로 검증이 가능하다. 픽스처(`@pytest.fixture`), 파라미터화(`@pytest.mark.parametrize`), 플러그인 생태계가 풍부하다.

### 선택 근거
- 각 스프린트의 AC(인수 기준) 검증을 자동화하려면 테스트 프레임워크가 필수다.
- `unittest`보다 문법이 간결하고, `assert` 실패 시 비교값을 상세히 출력한다.
- `pytest-cov`로 커버리지, `pytest-benchmark`로 성능 측정 등 플러그인 확장이 쉽다.
- Evaluator가 `pytest tests/test_baseline.py` 명령으로 AC를 자동 검증하는 하네스 설계와 자연스럽게 연결된다.

---

## 로깅 — loguru

### 설명
Python 기본 `logging` 모듈의 복잡한 설정을 없애고 단순한 API를 제공하는 로깅 라이브러리. `from loguru import logger` 한 줄로 시작하며, 색상 출력, 구조화 로그, 파일 로테이션을 기본 지원한다.

```python
# 기본 logging 대비 간결
from loguru import logger
logger.info("epoch={epoch} val_loss={val_loss:.4f}", epoch=1, val_loss=0.32)
```

### 선택 근거
- Evaluator가 `log_schema` 타입 AC를 검증할 때 구조화된 로그 파싱이 필요하다. loguru의 포맷이 일관성을 보장한다.
- `epoch별 train_loss, val_loss, val_acc` 기록(AC-04-02)처럼 학습 진행 상황을 추적하기 편하다.
- 기본 `print()` 대신 사용을 강제하여 운영 환경에서도 로그 레벨 제어가 가능하다.
- 설정 없이 즉시 사용 가능하여 실험 코드의 부담이 없다.

---

## 기술 스택 요약

| 범주 | 도구 | 역할 |
|------|------|------|
| 언어 | Python 3.11 | 전체 코드베이스 |
| 딥러닝 | PyTorch 2.4 | 모델 학습/추론 엔진 |
| 모델 허브 | HuggingFace Transformers 4.46 | BERT 로드 및 파인튜닝 |
| 베이스라인 | scikit-learn 1.5 | TF-IDF + LR 비교 기준 |
| 데이터 | NSMC | 한국어 감성 분류 벤치마크 |
| 사전학습 모델 | klue/roberta-base | 한국어 특화 RoBERTa |
| 패키지 관리 | uv | 의존성 잠금 및 환경 재현 |
| 테스트 | pytest | AC 자동 검증 |
| 로깅 | loguru | 학습 로그 및 Evaluator 연동 |
