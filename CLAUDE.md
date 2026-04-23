# AGENTS.md

> 이 파일은 에이전트 시스템 프롬프트에 자동 주입된다. 60줄 이하 간결 유지.

## 프로젝트
한국어 감성 분석기 (NSMC + klue/roberta-base). 6-스프린트 하네스 기반 개발.

## 공통 규칙
- 모든 코드는 `src/` 하위에 작성. 노트북은 탐색 용도만.
- 의존성 변경 시 `uv add <pkg>` 사용. `pip install` 금지.
- 타입 힌트 필수. `Any`는 경계 지점에서만.
- 로그는 `loguru` 사용. `print()` 금지.
- 파일 경로는 `pathlib.Path` 사용. 문자열 조합 금지.
- 실패 메시지는 구체적으로 (파일/라인/재현 방법 포함).

## Planner (Opus)
- 출력은 반드시 `.harness/sprint-contract.yaml`.
- 세부 구현 금지, 스프린트 분해만 수행.
- 각 스프린트는 독립 검증 가능해야 함.
- AC는 스프린트당 3~5개, 수치 기반 우선.

## Planner/Generator (Sonnet)
- `.harness/sprint-contract.yaml` + `.harness/claude-progress.txt` 읽고 시작.
- 작업 완료 시 `.harness/sprints/sprint-XX/evaluation-request.md` 작성.
- 스프린트 브랜치 사용: `sprint-XX/<slug>`.
- 기능 단위 커밋. 한 커밋에 여러 기능 금지.
- 구현 후 반드시 `pytest` 실행하여 자체 검증.
- 완료 선언 금지 — Evaluator가 판정.

## Orchestrator (Claude Code Agent)
- 실행: `Agent(subagent_type="orchestrator", prompt="sprint-XX를 실행하십시오.")`
- planner → 병렬 리뷰어(bug/ml/test) → review-synthesis → slop-cleaner → evaluator 순으로 서브에이전트를 조율.
- semantic_eval AC는 evaluator-llm 서브에이전트로 위임.
- Stop Condition 및 최대 3회 재시도 관리는 orchestrator 에이전트 내에서 처리.

## Evaluator (자동화 + Haiku 서브에이전트)
- `uv run python .harness/evaluator.py --sprint sprint-XX --json` 으로 수치/파일/명령 판정.
- `semantic_eval` 타입 AC는 evaluator.py가 SKIP 반환 → orchestrator가 evaluator-llm 서브에이전트 spawn.
- 코드 읽기만으로 판정 금지. 반드시 실행/테스트 결과 기반.
- 호의적 해석 금지. AC 미충족은 FAIL.
- 출력은 `.harness/sprints/sprint-XX/evaluation-report.md`.

## Stop Condition
- 스프린트당 재시도 3회 초과 → 에스컬레이션
- 비용 $20 초과 → 즉시 중단
- 동일 AC 3회 연속 FAIL → 구조적 문제, 에스컬레이션

## 금지 행동
- `data/raw/` 수정 금지 (원본 보존).
- `artifacts/checkpoints/` 덮어쓰기 금지. 타임스탬프 포함 파일명.
- `git push --force` 금지.
- `uv.lock` 수동 편집 금지.
