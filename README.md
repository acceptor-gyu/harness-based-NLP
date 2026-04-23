# 한국어 감성 분석기

NSMC(Naver Sentiment Movie Corpus) 기반 한국어 영화 리뷰 감성 분류기.
`klue/roberta-base`를 파인튜닝하여 긍정/부정 이진 분류를 수행한다.

**Planner → Generator → Evaluator** 3단계 에이전트 하네스 위에서 6개 스프린트로 개발된다.
각 스프린트는 수치 기반 Acceptance Criteria(AC)로 독립 검증되며, 자동 평가 스크립트가 PASS/FAIL을 판정한다.

---

## 성능 목표

| 모델 | Accuracy | Macro F1 |
|------|----------|----------|
| TF-IDF + Logistic Regression (베이스라인) | ≥ 0.85 | ≥ 0.83 |
| klue/roberta-base (파인튜닝) | ≥ 0.90 | ≥ 0.88 |

---

## 기술 스택

| 범주 | 선택 |
|------|------|
| 언어 | Python 3.11 |
| 의존성 관리 | `uv` |
| ML | PyTorch 2.4 + HuggingFace Transformers 4.46 |
| 베이스라인 | scikit-learn 1.5 (TF-IDF + LogisticRegression) |
| 데이터 | NSMC — train 150,000건 / test 50,000건 |
| 테스트 | pytest |
| 로깅 | loguru |
| UI (선택) | Gradio |

---

## 프로젝트 구조

```
sentiment-analyzer/
├── CLAUDE.md                     # 에이전트 시스템 프롬프트 (자동 주입)
├── PLAN.md                       # 전체 개발 계획
├── docs/
│   └── harness-spec.md           # 하네스 엔지니어링 상세 명세
├── .harness/
│   ├── sprint-contract.yaml      # SSOT — Planner 출력, 이후 수정 금지
│   ├── claude-progress.txt       # 세션 간 상태 공유 (스프린트 상태 / 비용 / 재시도)
│   ├── evaluator.py              # 자동 평가 스크립트
│   ├── progress_sync.py          # Stop 훅 대상 (세션 종료 체크포인트)
│   ├── hooks/
│   │   └── preflight_check.py    # PreToolUse(Bash) 훅 (비용/순서/디바이스 검사)
│   └── sprints/
│       └── sprint-XX/
│           ├── evaluation-request.md   # Generator → Evaluator 핸드오프
│           └── evaluation-report.md    # Evaluator 판정 결과
├── src/                          # 소스 코드 (모든 구현은 여기)
├── data/
│   └── raw/                      # NSMC 원본 (수정 금지)
├── artifacts/
│   ├── checkpoints/              # 모델 체크포인트 (타임스탬프 포함 파일명)
│   └── baseline_metrics.json     # 베이스라인 지표
├── notebooks/                    # EDA 탐색 전용
└── tests/
```

---

## 빠른 시작

```bash
# 의존성 설치
uv sync

# 스프린트 평가 (자동)
uv run python .harness/evaluator.py --sprint sprint-01 --json

# 평가 보고서 확인
cat .harness/sprints/sprint-01/evaluation-report.md
```

---

## 스프린트 구성

| 스프린트 | 제목 | 핵심 산출물 | 핵심 AC |
|----------|------|-------------|---------|
| sprint-01 | 환경 세팅 및 데이터 로드 | `src/data_loader.py` | train 150k건, null = 0 |
| sprint-02 | 전처리 파이프라인 | `src/preprocess.py`, DataLoader | 토큰 128 초과 < 5%, Val 10% ± 1% |
| sprint-03 | 베이스라인 (TF-IDF + LogReg) | `src/baseline.py`, `artifacts/baseline_metrics.json` | Accuracy ≥ 0.85 |
| sprint-04 | BERT 파인튜닝 | `src/train.py`, `artifacts/checkpoints/` | Val Accuracy ≥ 0.90 |
| sprint-05 | 평가 및 리포트 | `src/evaluate.py`, `artifacts/eval_report.md` | Test Accuracy ≥ 0.90, F1 ≥ 0.88 |
| sprint-06 *(선택)* | Gradio UI | `src/serve.py` | 응답 < 1초, 신뢰도 > 0.9 |

---

## 하네스 엔지니어링

단일 세션 컨텍스트 한계를 넘는 멀티-스프린트 개발을 자동화하기 위해 파일 기반 에이전트 하네스를 사용한다.

### 에이전트 구성

```
Planner (Opus 4.7)
└─► sprint-contract.yaml

Orchestrator (Claude Code Agent)
├── Generator (Sonnet 4.6)          # 코드 구현
│   └─► evaluation-request.md
├── 리뷰어 ×3 (bug / ml / test)     # 병렬 실행
├── review-synthesis
├── slop-cleaner
└── Evaluator
    ├── evaluator.py                 # 수치/파일/명령 자동 판정
    └── evaluator-llm (Haiku 4.5)   # semantic_eval 항목만
```

| 에이전트 | 모델 | 역할 |
|---------|------|------|
| Planner | Opus 4.7 | 스프린트 계획 (1회) |
| Generator | Sonnet 4.6 | 코드 구현 (스프린트별 반복) |
| Evaluator (규칙) | 자동화 스크립트 | 수치/파일 기반 판정 |
| Evaluator (의미) | Haiku 4.5 | 오분류 분석 등 의미 판정 |

### 자동 평가 (`evaluator.py`)

`sprint-contract.yaml`의 AC를 읽어 verification 타입별로 PASS/FAIL을 판정한다.

| verification 타입 | 판정 방식 |
|-------------------|-----------|
| `command_exec` | 쉘 명령 실행 후 exit code 0 확인 |
| `file_check` | 파일 존재 + 크기 > 0 |
| `file_schema` | 파일 내 필수 키/섹션 존재 |
| `metric_threshold` | `artifacts/{sprint_id}_metrics.json`에서 지표 조회 후 임계값 비교 |
| `python_assert` | `uv run python -c <script>` 실행 |
| `log_schema` | 로그 파일 내 필수 필드 존재 |
| `semantic_eval` | SKIP 반환 → orchestrator가 Haiku 서브에이전트로 위임 |

### Claude Code 훅

`.claude/settings.json`에 등록된 자동 실행 훅:

**PreToolUse(Bash) — `preflight_check.py`**

Bash 명령 실행 직전 세 가지를 검사한다.

| 검사 항목 | 임계값 | 동작 |
|-----------|--------|------|
| 비용 상한 초과 | `$20.00` | 명령 차단 (exit 2) |
| 비용 경고 | `$16.00` (80%) | 경고 출력 후 허용 |
| 스프린트 순서 위반 | sprint-01~03 PASS 전 train.py 실행 시 | 명령 차단 (exit 2) |
| GPU/MPS 미검출 | 학습 명령 시 | 경고 출력 후 허용 |

**Stop — `progress_sync.py`**

세션 종료 시 `claude-progress.txt` 타임스탬프를 갱신하고, 미커밋 변경이 있으면 자동으로 체크포인트 커밋을 생성한다.

### Stop Condition

| 조건 | 임계값 | 동작 |
|------|--------|------|
| 스프린트 재시도 | 3회 초과 | 에스컬레이션 |
| 전체 비용 | $20 초과 | 즉시 중단 |
| 동일 AC 연속 실패 | 3회 | 에스컬레이션 |

### 파일 기반 핸드오프 흐름

```
Generator 구현 완료
      │
      ▼ evaluation-request.md 작성
Evaluator 판정
      │
      ├─ PASS
      │   └─ claude-progress.txt 갱신 → 다음 스프린트 IN_PROGRESS
      │
      └─ FAIL
          └─ 실패 AC 피드백 → Generator 재시도 (최대 3회)
                  │
                  └─ 3회 초과 → 에스컬레이션
```

---

## 문서

- [개발 계획 상세](PLAN.md)
- [하네스 엔지니어링 명세](docs/harness-spec.md)
- [스프린트 계약](.harness/sprint-contract.yaml)
- [진행 상태](.harness/claude-progress.txt)
