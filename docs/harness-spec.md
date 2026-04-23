# 하네스 엔지니어링 명세

한국어 감성 분석기 프로젝트의 6-스프린트 개발 자동화 하네스에 대한 파일 구조, 에이전트, 훅 명세.

---

## 1. 전체 아키텍처

```
사용자 (요구사항)
      │
      ▼
  Planner (Opus 4.7)
  └─► .harness/sprint-contract.yaml  ← Single Source of Truth
      │
      ▼
  Orchestrator (Claude Code Agent)
  ├── Generator (Sonnet 4.6) × 스프린트
  │   └─► .harness/sprints/sprint-XX/evaluation-request.md
  ├── 리뷰어 서브에이전트 (병렬: bug / ml / test)
  ├── review-synthesis
  ├── slop-cleaner
  └── Evaluator
      ├── evaluator.py (자동 판정)  ─► evaluation-report.md
      └── evaluator-llm (Haiku 4.5)  ← semantic_eval 항목만
          │
          ├─ PASS → claude-progress.txt 갱신 → 다음 스프린트
          └─ FAIL → 재시도 (최대 3회) → 에스컬레이션
```

---

## 2. 파일 구조

```
.harness/
├── sprint-contract.yaml          # SSOT: Planner가 생성, 이후 수정 금지
├── claude-progress.txt           # 세션 간 상태 공유 (스프린트 상태, 비용, 재시도 이력)
├── evaluator.py                  # 자동 평가 스크립트
├── progress_sync.py              # Stop 훅 대상 스크립트
├── hooks/
│   ├── __init__.py
│   └── preflight_check.py        # PreToolUse(Bash) 훅
└── sprints/
    └── sprint-XX/
        ├── evaluation-request.md  # Generator → Evaluator 핸드오프
        └── evaluation-report.md   # Evaluator 판정 결과
```

---

## 3. 에이전트 명세

### 3.1 Planner (Opus 4.7)

| 항목 | 내용 |
|------|------|
| 역할 | 전략적 스프린트 분해 |
| 실행 | 프로젝트 시작 시 1회 |
| 입력 | 사용자 요구사항 |
| 출력 | `.harness/sprint-contract.yaml` |
| 제약 | 세부 구현 금지. 스프린트 분해만. 각 스프린트는 독립 검증 가능해야 함 |
| AC 기준 | 스프린트당 3~5개, 수치 기반 우선 |

### 3.2 Orchestrator (Claude Code Agent)

| 항목 | 내용 |
|------|------|
| 역할 | 서브에이전트 조율 및 Stop Condition 관리 |
| 실행 | `Agent(subagent_type="orchestrator", prompt="sprint-XX를 실행하십시오.")` |
| 조율 순서 | planner → 병렬 리뷰어(bug/ml/test) → review-synthesis → slop-cleaner → evaluator |
| 재시도 | 스프린트당 최대 3회, 동일 AC 3회 연속 FAIL 시 에스컬레이션 |
| semantic_eval | evaluator.py가 SKIP 반환 → evaluator-llm 서브에이전트 spawn |

### 3.3 Generator (Sonnet 4.6)

| 항목 | 내용 |
|------|------|
| 역할 | 스프린트 코드 구현 |
| 실행 시작 | `.harness/sprint-contract.yaml` + `.harness/claude-progress.txt` 읽기 |
| 브랜치 | `sprint-XX/<slug>` |
| 완료 조건 | `.harness/sprints/sprint-XX/evaluation-request.md` 작성 후 `pytest` 자체 검증 |
| 제약 | 완료 선언 금지. Evaluator가 판정 |

**evaluation-request.md 필수 항목:**
- 구현 완료 항목 (파일/기능 목록)
- 실행 방법 (uv sync, uv run, pytest)
- 검증 요청 AC 체크리스트
- 주요 변경 파일
- 아티팩트 위치 (`artifacts/{sprint_id}_metrics.json`, `logs/`)
- 알려진 제한사항 (다음 스프린트 처리 항목)
- 커밋 해시 및 브랜치

### 3.4 Evaluator — 자동화 스크립트 (`evaluator.py`)

실행: `uv run python .harness/evaluator.py --sprint sprint-XX [--json]`

**verification 타입별 판정 방식:**

| 타입 | 판정 방식 | 필수 필드 |
|------|-----------|-----------|
| `command_exec` | 쉘 명령 실행, exit code 0 확인 | `command` |
| `file_check` | 파일 존재 + 크기 > 0 | `paths: [...]` |
| `file_schema` | 파일 내 필수 키/섹션 존재 | `path`, `required_keys: [...]` |
| `metric_threshold` | `artifacts/{sprint_id}_metrics.json`에서 지표 조회 | `metric_key`, `threshold`, `op` (기본 `>=`) |
| `python_assert` | `uv run python -c <script>` 실행, exit code 확인 | `script` |
| `log_schema` | `file_schema`와 동일 (로그 파일 대상) | `path`, `required_keys: [...]` |
| `integration_test` | `command_exec`와 동일 | `command` |
| `semantic_eval` | 항상 SKIP 반환 → orchestrator가 evaluator-llm으로 위임 | — |

**출력:**
- `--json` 플래그: stdout에 JSON (`sprint_id`, `overall`, `failed_acs`, `skipped_acs`, `ac_results`)
- 파일: `.harness/sprints/sprint-XX/evaluation-report.md`
- exit code: PASS → 0, FAIL → 1

**판정 규칙:**
- `FAIL` AC가 하나라도 있으면 `overall = FAIL`
- `SKIP`(semantic_eval 등)은 overall 판정에서 제외

### 3.5 Evaluator-LLM (Haiku 4.5)

| 항목 | 내용 |
|------|------|
| 역할 | `semantic_eval` 타입 AC 판정 |
| 트리거 | evaluator.py 결과에 `skipped_acs`가 있을 때 orchestrator가 spawn |
| 입력 | evaluation-request.md, 해당 AC description, 아티팩트 파일 |
| 출력 | evaluation-report.md에 판정 결과 추가 |
| 제약 | 코드 읽기만으로 판정 금지. 실행/테스트 결과 기반. 호의적 해석 금지 |

---

## 4. 훅 명세

Claude Code `settings.json`에 등록된 훅:

### 4.1 PreToolUse(Bash) — `preflight_check.py`

**트리거:** Bash 도구 실행 직전  
**목적:** 세 가지 실행 전 안전 검사

| 검사 | 조건 | 동작 |
|------|------|------|
| 비용 상한 | `cost-ledger.json`의 `total_usd >= $20.00` | exit 2 (차단) |
| 비용 경고 | `total_usd >= $16.00` (80%) | stdout 경고, 통과 |
| 스프린트 순서 | `src/train.py` 실행 시 sprint-01~03이 PASS 아닐 때 | exit 2 (차단) |
| 디바이스 경고 | 학습 명령인데 CUDA/MPS 없을 때 | stdout 경고, 통과 |

**판정 기준:**
- `exit 0` → 허용
- `exit 2` → 차단 (stderr 메시지 사용자에게 표시)

**학습 명령 감지 패턴:**
```
python.*src/train\.py
-m\s+src\.train
torch\.cuda|transformers.*Trainer
```

### 4.2 Stop — `progress_sync.py`

**트리거:** Claude Code 세션 종료  
**목적:** 세션 종료 시점 상태 보존

**동작:**
1. `claude-progress.txt`의 "마지막 갱신" 줄을 현재 UTC 타임스탬프로 교체
2. `src/`, `tests/`, `artifacts/`, `.harness/` 에 미커밋 변경이 있으면 체크포인트 커밋 생성
   - 커밋 메시지: `[harness] checkpoint — session {session_id[:8]} 종료 시점`

---

## 5. 상태 파일 명세

### 5.1 `sprint-contract.yaml` (SSOT)

Planner가 생성. 이후 수정 금지.

```yaml
project: "한국어 감성 분석기"
version: "1.0.0"
tech_stack: { ... }
global_constraints:
  max_sequence_length: 128
  random_seed: 42
  device_preference: [cuda, mps, cpu]
  cost_ceiling_usd: 20.0
  retry_limit_per_sprint: 3
sprints:
  - id: "sprint-XX"
    title: "..."
    acceptance_criteria:
      - id: "AC-XX-YY"
        description: "..."
        verification: "command_exec | file_check | ..."
        # metric_threshold 전용 추가 필드:
        metric_key: "accuracy"
        threshold: 0.85
        op: ">="  # 기본값
        # file_check 전용:
        paths: ["data/raw/ratings_train.txt"]
        # python_assert 전용:
        script: "from src.data_loader import load_nsmc; ..."
        # command_exec 전용:
        command: "uv sync"
    handoff_to: "sprint-02"
```

### 5.2 `claude-progress.txt`

세션 간 상태 공유. Generator와 Evaluator가 갱신.

**섹션 구조:**
- `완료된 스프린트`: PASS 판정 후 이동
- `현재 스프린트`: `[PENDING | IN_PROGRESS | READY_FOR_EVAL | PASS | FAIL]`
- `대기 중인 스프린트`
- `비용 추적`: 누적 비용 / $20.00
- `재시도 이력`: `스프린트ID / 시도 / 실패 AC / 타임스탬프`
- `에스컬레이션 로그`

**갱신 규칙:**
- Generator: 구현 완료 후 `IN_PROGRESS` → `READY_FOR_EVAL`
- Evaluator: PASS 시 "완료된 스프린트"로 이동, 다음 스프린트 `IN_PROGRESS`로 설정
- 재시도: "재시도 이력"에 한 줄 추가 후 git 단독 커밋

---

## 6. Stop Condition

| 조건 | 임계값 | 동작 |
|------|--------|------|
| 재시도 한도 | 스프린트당 3회 초과 | 에스컬레이션 |
| 비용 상한 | $20 초과 | 즉시 중단 (preflight_check 차단) |
| 구조적 루프 | 동일 AC 3회 연속 FAIL | 에스컬레이션 |

---

## 7. 스프린트별 핵심 AC 요약

| 스프린트 | 핵심 지표 |
|----------|-----------|
| sprint-01 | train 150,000건 / test 50,000건, document null = 0 |
| sprint-02 | 토큰 128 초과 비율 < 5%, Val 분할 10% ± 1%, 레이블 편차 < 2%p |
| sprint-03 | Test Accuracy ≥ 0.85, Macro F1 ≥ 0.83 |
| sprint-04 | Val Accuracy ≥ 0.90, Early Stopping 동작, 재현성 편차 < 0.5%p |
| sprint-05 | Test Accuracy ≥ 0.90, Macro F1 ≥ 0.88, Confusion Matrix PNG 생성 |
| sprint-06 (선택) | 응답 시간 < 1초, 신뢰도 > 0.9 |
