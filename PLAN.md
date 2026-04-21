# 한국어 감성 분석기 개발 계획

> Planner-Generator-Evaluator 3단계 하네스 기반 스프린트 개발 계획

---

## 1. 프로젝트 정의

| 항목 | 내용 |
|------|------|
| 프로젝트명 | `sentiment-analyzer` |
| 목표 | 한국어 영화 리뷰(NSMC)를 입력받아 긍정/부정을 분류하는 분류기 |
| 최종 산출물 | CLI + 선택적 Gradio UI, 파인튜닝된 체크포인트, 평가 리포트 |
| 데이터셋 | NSMC (Naver Sentiment Movie Corpus) 150,000 train / 50,000 test |
| 모델 | 베이스라인: TF-IDF + Logistic Regression / 본 모델: `klue/roberta-base` |
| 성능 목표 | Baseline Accuracy ≥ 0.85, BERT Accuracy ≥ 0.90, Macro F1 ≥ 0.88 |
| 전체 기간 | 4.5일 (선택 스프린트 포함 시 5.5일) |

---

## 2. 기술 스택

| 범주 | 선택 | 비고 |
|------|------|------|
| 언어 | Python 3.11 | f-string, 타입 힌트 |
| 의존성 관리 | `uv` | 빠른 설치, lockfile 지원 |
| ML 프레임워크 | PyTorch 2.4 + `transformers` 4.46 | HuggingFace 생태계 |
| 베이스라인 | `scikit-learn` 1.5 | TF-IDF, LogisticRegression |
| 데이터 | `datasets`, `pandas` | NSMC 로드 |
| 평가 | `sklearn.metrics`, `evaluate` | Accuracy, F1, Confusion Matrix |
| 실행 환경 | 로컬 CPU / Google Colab T4 | BERT 학습 시 GPU 권장 |
| 서빙 | `gradio` (선택) | 웹 UI |
| 테스트 | `pytest` | 파이프라인 단위 테스트 |
| 로깅 | `loguru` | 구조화 로그 |

---

## 3. 6-Sprint 구성

### Sprint-01: 환경 세팅 및 데이터 로드 (0.5일)
- **목적**: 프로젝트 스캐폴딩, 데이터 다운로드, 초기 DataLoader 검증
- **산출물**: `pyproject.toml`, `src/data_loader.py`, NSMC 파일 `data/` 저장
- **핵심 AC**: 데이터 로드 후 결측값 0건, train/test 분할 정상

### Sprint-02: 전처리 파이프라인 (1일)
- **목적**: 텍스트 정제 + 토크나이저 적용 + Train/Val/Test 분할
- **산출물**: `src/preprocess.py`, 전처리된 Dataset 캐시
- **핵심 AC**: 토큰 길이 128 초과 비율 < 5%, Val 분할 10%

### Sprint-03: 베이스라인 (0.5일)
- **목적**: TF-IDF + LogReg로 빠른 성능 바닥 확보
- **산출물**: `src/baseline.py`, `artifacts/baseline_metrics.json`
- **핵심 AC**: Test Accuracy ≥ 0.85

### Sprint-04: BERT 파인튜닝 (2일)
- **목적**: `klue/roberta-base` 파인튜닝, 체크포인트 저장
- **산출물**: `src/train.py`, `artifacts/checkpoints/best.pt`, loss 곡선
- **핵심 AC**: Val Accuracy ≥ 0.90, Early stopping 정상 동작

### Sprint-05: 평가 및 리포트 (0.5일)
- **목적**: Test 세트 평가 + 오분류 분석 + 리포트 생성
- **산출물**: `src/evaluate.py`, `artifacts/eval_report.md`
- **핵심 AC**: Test Accuracy ≥ 0.90, Macro F1 ≥ 0.88, Confusion Matrix 생성

### Sprint-06 (선택): Gradio UI (1일)
- **목적**: 실시간 추론 웹 UI
- **산출물**: `src/serve.py`, 배포 스크립트
- **핵심 AC**: 입력 → 1초 이내 응답, 신뢰도 표시

---

## 4. 타임라인

```
Day 1 오전  ├─ Sprint-01 환경 세팅
Day 1 오후  ├─ Sprint-02 전처리 파이프라인 (시작)
Day 2 오전  ├─ Sprint-02 전처리 파이프라인 (완료)
Day 2 오후  ├─ Sprint-03 베이스라인
Day 3      ├─ Sprint-04 BERT 파인튜닝 (학습 시작)
Day 4 오전  ├─ Sprint-04 BERT 파인튜닝 (검증 및 튜닝)
Day 4 오후  ├─ Sprint-05 평가 및 리포트
Day 5 (선택) ├─ Sprint-06 Gradio UI
```

---

## 5. 리스크 및 대응

| 리스크 | 영향도 | 대응 |
|--------|--------|------|
| GPU 없음 → BERT 학습 시간 폭증 | 높음 | Colab T4 전환, 또는 `distilkobert` 소형 모델로 대체 |
| NSMC 데이터 노이즈 (오타, 이모지) | 중간 | 전처리 단계 정규화 강화, 일부 샘플 육안 검증 |
| 오버피팅 | 중간 | Early stopping + Dropout 0.1, Val 모니터링 |
| 학습 중단 (OOM, 네트워크) | 중간 | 체크포인트 주기 저장, `resume_from_checkpoint` 지원 |
| 긴 시퀀스로 인한 메모리 초과 | 낮음 | max_length=128 고정, truncation 활성 |

---

## 6. 하네스 적용 전략

### 왜 하네스를 쓰는가
- 총 4.5일, 스프린트 6개로 단일 세션 컨텍스트 한계 초과 → 파일 기반 상태 관리 필수
- 각 스프린트가 독립 검증 가능(AC 기반) → Evaluator 자동화로 자기 편향 제거
- 학습 실패 시 빠른 재시도 + 비용 상한 → Stop Condition 필요

### 하네스 구성

```
사용자 (요구사항)
      │
      ▼
  Planner (Opus) ─► sprint-contract.yaml
      │
      ▼
  Generator (Sonnet) ─► 코드 + evaluation-request.md
      │
      ▼
  Evaluator (Haiku + 자동화 스크립트) ─► evaluation-report.md
      │
      ├─ PASS → claude-progress.txt 갱신 → 다음 스프린트
      └─ FAIL → 피드백 반영 → 재시도 (최대 3회)
              │
              └─ 3회 초과 → 에스컬레이션
```

### 모델 티어링
| 에이전트 | 모델 | 이유 |
|---------|------|------|
| Planner | Opus 4.7 | 1회 실행, 전략적 스프린트 분해 |
| Generator | Sonnet 4.6 | 반복 코드 생성, 속도/품질 균형 |
| Evaluator (규칙) | 자동화 스크립트 | 수치 기반 판정, LLM 불필요 |
| Evaluator (의미) | Haiku 4.5 | 오분류 분석 시 경량 판정 |

### Stop Condition 3종
1. **재시도 한도**: 스프린트당 최대 3회
2. **비용 상한**: 전체 $20 (학습 비용 제외)
3. **구조적 루프 탐지**: 동일 AC 3회 연속 실패 → 즉시 에스컬레이션

---

## 7. 파일 기반 핸드오프 구조

```
sentiment-analyzer/
├── AGENTS.md                 # 전역 하네스 가이드 (자동 주입)
├── PLAN.md                   # 이 문서
├── pyproject.toml
├── .harness/
│   ├── sprint-contract.yaml  # SSOT — Planner 출력
│   ├── claude-progress.txt   # 세션 간 상태 공유
│   ├── runner.py             # Stop Condition 관리자
│   ├── evaluator.py          # 자동 평가 스크립트
│   └── sprints/
│       └── sprint-<ID>/
│           ├── evaluation-request.md   # Generator → Evaluator
│           └── evaluation-report.md    # Evaluator → Generator
├── src/
├── data/
├── artifacts/
├── notebooks/
└── tests/
```

---

## 8. 성공 판정 기준 (전체)

- [ ] 6개 스프린트 중 필수 5개(01~05) 모두 Evaluator PASS
- [ ] Test Accuracy ≥ 0.90, Macro F1 ≥ 0.88
- [ ] `artifacts/eval_report.md` 생성
- [ ] 전체 소요 비용 ≤ $20
- [ ] 재현 가능: `uv run python -m src.train` 명령으로 end-to-end 실행
