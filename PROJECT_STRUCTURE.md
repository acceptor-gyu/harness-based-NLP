# 프로젝트 구조 설명

한국어 감성 분석기 프로젝트의 폴더/파일별 역할 정리.

---

## 최상위 파일

| 파일 | 역할 |
|------|------|
| `CLAUDE.md` | 에이전트 시스템 프롬프트 자동 주입 파일. Planner/Generator/Evaluator/Orchestrator의 공통 규칙 및 금지 행동 정의. |
| `PLAN.md` | 구현 계획 문서 (사람이 읽는 용도). |
| `README.md` | 프로젝트 개요 및 실행 방법. |
| `pyproject.toml` | uv 패키지 매니저 설정. 의존성, ruff/pytest 설정 포함. `uv sync`로 환경 재현. |

---

## `.claude/` — Claude Code 설정

```
.claude/
├── settings.json          # 훅(Hook) 연결 설정
└── agents/
    ├── generator.md       # Generator 서브에이전트 시스템 프롬프트
    ├── orchestrator.md    # Orchestrator 서브에이전트 시스템 프롬프트
    └── evaluator-llm.md   # Evaluator-LLM 서브에이전트 시스템 프롬프트
```

### `settings.json`
세 가지 훅을 Claude Code 이벤트에 연결한다:
- **Stop** → `progress_sync.py` 실행 (세션 종료 시 체크포인트 커밋)
- **PreToolUse(Bash)** → `preflight_check.py` 실행 (비용/순서 검증)
- **PostToolUse(Write|Edit)** → `auto_commit.py` 실행 (파일 저장 시 자동 커밋)

### `agents/*.md`
`claude -p` 로 spawn되는 서브에이전트의 역할 정의 파일. 각 파일 frontmatter에 사용 모델과 허용 도구가 명시된다.

| 에이전트 | 모델 | 역할 |
|----------|------|------|
| `generator.md` | Sonnet 4.6 | 스프린트 범위 코드 구현 후 `evaluation-request.md` 작성 |
| `orchestrator.md` | Sonnet 4.6 | Generator spawn → Evaluator 실행 → Stop Condition 관리 루프 |
| `evaluator-llm.md` | Haiku 4.5 | AC-05-05(오분류 분석 품질) 의미 판정, JSON만 출력 |

---

## `.harness/` — 하네스 엔진

자동화 파이프라인의 핵심. 사람이 직접 편집하지 않는 구동 파일들.

```
.harness/
├── sprint-contract.yaml        # 스프린트 계약서 (Single Source of Truth)
├── claude-progress.txt         # 현재 스프린트 진행 상태 추적 파일
├── orchestrator.py             # 스프린트 전체 루프 실행기
├── runner.py                   # Stop Condition 전담 관리자
├── evaluator.py                # 자동 AC 판정 스크립트
├── evaluator_llm.py            # LLM 기반 의미 판정 스크립트 (AC-05-05용)
├── progress_sync.py            # Stop 훅 대상 — 세션 종료 시 체크포인트 커밋
├── hooks/
│   ├── __init__.py
│   ├── auto_commit.py          # PostToolUse 훅 — Write/Edit 후 자동 git 커밋
│   └── preflight_check.py      # PreToolUse 훅 — Bash 실행 전 안전성 검사
└── sprints/
    └── sprint-01/
        ├── evaluation-request.md.template   # Generator가 작성할 완료 신호 템플릿
        └── evaluation-report.md.template    # Evaluator가 작성할 판정 결과 템플릿
```

### 핵심 파일 상세

**`sprint-contract.yaml`**
Planner가 생성하는 계약서. sprint-01~06의 범위, 인수 조건(AC), 검증 방식, 기술 스택, 비용 상한을 정의한다. Generator와 Evaluator 모두 이 파일을 기준으로 동작한다.

**`claude-progress.txt`**
각 스프린트의 현재 상태(`PENDING` → `IN_PROGRESS` → `PASS` / `ESCALATED`)를 기록한다. 비용 추적, 재시도 이력, 에스컬레이션 로그도 포함.

**`orchestrator.py`**
`uv run python .harness/orchestrator.py --sprint sprint-XX` 로 실행. `claude -p` CLI로 Generator를 spawn하고, Evaluator 결과에 따라 재시도 또는 다음 스프린트로 핸드오프하는 루프를 조율한다.

**`runner.py`**
`orchestrator.py`와 역할이 유사하지만 Stop Condition(비용 상한, Stuck Loop 탐지)에 더 집중한 경량 버전. `cost-ledger.json`을 읽어 누적 비용을 추적한다.

**`evaluator.py`**
`sprint-contract.yaml`의 AC를 읽고 검증 타입별로 판정한다:
- `command_exec` — 쉘 명령 exit code 확인
- `file_check` — 파일 존재 및 크기 확인
- `file_schema` — 필수 키/섹션 존재 확인
- `metric_threshold` — `artifacts/{sprint_id}_metrics.json`에서 수치 비교
- `python_assert` — Python 스크립트 실행 후 exit code 확인
- `semantic_eval` — `evaluator_llm.py`로 위임

결과는 `.harness/sprints/{sprint_id}/evaluation-report.md`에 저장되고 `--json` 옵션 시 stdout에도 출력.

**`evaluator_llm.py`**
스크립트로 판정 불가한 의미 기반 AC(현재 AC-05-05)를 `claude -p`로 evaluator-llm 에이전트에 위임. `artifacts/eval_report.md` 내용을 프롬프트에 포함해 호출하고 JSON 응답을 파싱한다.

**`hooks/preflight_check.py`**
Bash 명령 실행 전 세 가지를 검사:
1. 누적 비용이 $20 초과 시 **명령 차단** (exit 2)
2. `train.py` 실행 시 sprint-01~03이 PASS인지 확인, 미충족 시 **차단**
3. GPU/MPS 없을 때 CPU 학습 **경고** (차단 아님)

**`hooks/auto_commit.py`**
`src/` 또는 `tests/` 하위 파일이 Write/Edit될 때마다 자동으로 `[src]` / `[test]` 커밋을 생성한다. `artifacts/`, `data/`, `notebooks/`는 제외.

**`progress_sync.py`**
Claude Code 세션이 종료(Stop 이벤트)될 때 실행. `claude-progress.txt`에 타임스탬프를 기록하고, 미커밋 변경이 있으면 체크포인트 커밋을 생성한다.

---

## `src/` — 실제 구현 코드 (스프린트별 생성)

```
src/
├── data_loader.py    # sprint-01: NSMC 로드, load_nsmc() 반환
├── preprocess.py     # sprint-02: 정규화/토크나이저/DataLoader
├── baseline.py       # sprint-03: TF-IDF + LogisticRegression
├── train.py          # sprint-04: klue/roberta-base 파인튜닝
├── evaluate.py       # sprint-05: 체크포인트 로드 후 Test 평가
└── serve.py          # sprint-06(선택): Gradio UI
```

Generator가 각 스프린트 구현 시 채워나간다. 현재는 아직 생성 전.

---

## `tests/` — 테스트 코드

Generator 구현과 함께 작성. `pytest tests/ -x -q`로 자체 검증.

---

## `data/` — 데이터

```
data/
└── raw/
    ├── ratings_train.txt   # NSMC 학습 데이터 (150,000건) — 수정 금지
    └── ratings_test.txt    # NSMC 테스트 데이터 (50,000건) — 수정 금지
```

sprint-01에서 다운로드. 이후 스프린트에서 원본 변경 금지.

---

## `artifacts/` — 학습 결과물

```
artifacts/
├── baseline_metrics.json          # sprint-03: TF-IDF 모델 평가 지표
├── checkpoints/
│   └── best_<timestamp>.pt        # sprint-04: 최고 성능 체크포인트
├── confusion_matrix.png           # sprint-05: 혼동 행렬 이미지
└── eval_report.md                 # sprint-05: 베이스라인 vs BERT 비교 리포트
```

`auto_commit` 훅의 자동 커밋 대상에서 제외 (대용량 파일 방지). 체크포인트는 타임스탬프 포함 파일명 필수.

---

## `notebooks/` — 탐색용 노트북

sprint-01 EDA 노트북 등 탐색 목적으로만 사용. 프로덕션 코드는 반드시 `src/`에 작성.

---

## 스프린트 흐름 요약

```
Orchestrator
  └─ Generator (claude -p) ──→ src/ 코드 구현
       └─ evaluation-request.md 작성 (완료 신호)
  └─ Evaluator (evaluator.py) ──→ AC PASS/FAIL 판정
       └─ PASS → 다음 스프린트
       └─ FAIL → 피드백과 함께 Generator 재호출 (최대 3회)
       └─ 3회 FAIL → escalation-log.md 기록 후 중단
```
