"""
하네스 러너 — Stop Condition을 관리하고 Generator/Evaluator 루프를 조율한다.

사용 예시:
    uv run python .harness/runner.py --sprint sprint-03
    uv run python .harness/runner.py --sprint sprint-03 --max-retries 3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger

HARNESS_ROOT = Path(__file__).parent
PROJECT_ROOT = HARNESS_ROOT.parent
CONTRACT_PATH = HARNESS_ROOT / "sprint-contract.yaml"
PROGRESS_PATH = HARNESS_ROOT / "claude-progress.txt"
ESCALATION_PATH = HARNESS_ROOT / "escalation-log.md"
COST_LEDGER_PATH = HARNESS_ROOT / "cost-ledger.json"


@dataclass
class RetryRecord:
    sprint_id: str
    attempt: int
    failed_acs: list[str]
    timestamp: str


@dataclass
class StopConditionState:
    cost_ceiling_usd: float
    current_cost_usd: float = 0.0
    history: list[RetryRecord] = field(default_factory=list)

    def record_failure(self, sprint_id: str, attempt: int, failed_acs: list[str]) -> None:
        self.history.append(
            RetryRecord(
                sprint_id=sprint_id,
                attempt=attempt,
                failed_acs=sorted(failed_acs),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    def detect_stuck_loop(self, sprint_id: str, window: int = 3) -> bool:
        """동일 AC가 window회 연속 실패하면 구조적 문제로 판단한다."""
        recent = [r for r in self.history if r.sprint_id == sprint_id][-window:]
        if len(recent) < window:
            return False
        first = set(recent[0].failed_acs)
        return all(set(r.failed_acs) == first for r in recent[1:])

    def is_cost_exceeded(self) -> bool:
        return self.current_cost_usd >= self.cost_ceiling_usd


def load_contract() -> dict:
    if not CONTRACT_PATH.exists():
        logger.error(f"계약서를 찾을 수 없습니다: {CONTRACT_PATH}")
        sys.exit(1)
    with CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_sprint(contract: dict, sprint_id: str) -> dict:
    for sprint in contract["sprints"]:
        if sprint["id"] == sprint_id:
            return sprint
    logger.error(f"알 수 없는 스프린트: {sprint_id}")
    sys.exit(1)


def run_evaluator(sprint_id: str) -> dict:
    """자동 평가 스크립트를 실행하고 JSON 결과를 반환한다."""
    cmd = ["uv", "run", "python", ".harness/evaluator.py", "--sprint", sprint_id, "--json"]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        logger.error(f"Evaluator 실행 실패 (exit={result.returncode}):\n{result.stderr}")
        sys.exit(2)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.error(f"Evaluator 출력 파싱 실패:\n{result.stdout}")
        sys.exit(2)


def escalate(sprint_id: str, reason: str, context: dict) -> None:
    ESCALATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = (
        f"\n## {timestamp} — {sprint_id} ESCALATION\n"
        f"**Reason:** {reason}\n\n"
        f"```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```\n"
    )
    with ESCALATION_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)
    logger.warning(f"에스컬레이션 기록: {ESCALATION_PATH}")


def load_cost() -> float:
    if not COST_LEDGER_PATH.exists():
        return 0.0
    with COST_LEDGER_PATH.open("r", encoding="utf-8") as f:
        return float(json.load(f).get("total_usd", 0.0))


def save_cost(total: float) -> None:
    with COST_LEDGER_PATH.open("w", encoding="utf-8") as f:
        json.dump({"total_usd": total, "updated_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)


def run_sprint_loop(sprint_id: str, max_retries: int) -> str:
    contract = load_contract()
    sprint = find_sprint(contract, sprint_id)
    cost_ceiling = float(contract["global_constraints"]["cost_ceiling_usd"])

    state = StopConditionState(
        cost_ceiling_usd=cost_ceiling,
        current_cost_usd=load_cost(),
    )

    logger.info(f"[{sprint_id}] '{sprint['title']}' 시작 — 최대 재시도 {max_retries}회")
    logger.info(f"비용 현황: ${state.current_cost_usd:.2f} / ${cost_ceiling:.2f}")

    for attempt in range(1, max_retries + 1):
        logger.info(f"[{sprint_id}] 시도 {attempt}/{max_retries}")

        if state.is_cost_exceeded():
            escalate(sprint_id, "COST_CEILING_REACHED", {"cost_usd": state.current_cost_usd})
            return "ESCALATED_COST"

        eval_result = run_evaluator(sprint_id)
        verdict = eval_result.get("overall", "FAIL")
        failed_acs = eval_result.get("failed_acs", [])

        if verdict == "PASS":
            logger.success(f"[{sprint_id}] PASS (시도 {attempt}회)")
            save_cost(state.current_cost_usd)
            return "PASS"

        logger.warning(f"[{sprint_id}] FAIL — 실패 AC: {failed_acs}")
        state.record_failure(sprint_id, attempt, failed_acs)

        if state.detect_stuck_loop(sprint_id):
            escalate(
                sprint_id,
                "STUCK_LOOP_DETECTED",
                {"failed_acs": failed_acs, "attempts": attempt},
            )
            return "ESCALATED_STUCK"

    escalate(
        sprint_id,
        "RETRY_LIMIT_EXCEEDED",
        {"max_retries": max_retries, "last_failed_acs": failed_acs},
    )
    return "ESCALATED_RETRY"


def main() -> None:
    parser = argparse.ArgumentParser(description="하네스 러너 (Stop Condition 관리자)")
    parser.add_argument("--sprint", required=True, help="실행할 스프린트 ID (예: sprint-03)")
    parser.add_argument("--max-retries", type=int, default=3, help="최대 재시도 횟수 (기본 3)")
    args = parser.parse_args()

    outcome = run_sprint_loop(args.sprint, args.max_retries)
    logger.info(f"종료: {outcome}")
    sys.exit(0 if outcome == "PASS" else 1)


if __name__ == "__main__":
    main()
