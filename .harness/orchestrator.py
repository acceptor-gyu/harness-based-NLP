"""
하네스 오케스트레이터 — `claude -p` CLI로 generator 서브에이전트를 spawn하고
스프린트 루프(구현 → 평가 → 재시도 → 핸드오프)를 조율한다.

Claude Code 플랜 내에서 동작 (Anthropic API 별도 과금 없음).

사용:
    uv run python .harness/orchestrator.py --sprint sprint-01
    uv run python .harness/orchestrator.py --all
    uv run python .harness/orchestrator.py --all --from sprint-02
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger

HARNESS_ROOT = Path(__file__).parent
PROJECT_ROOT = HARNESS_ROOT.parent
CONTRACT_PATH = HARNESS_ROOT / "sprint-contract.yaml"
PROGRESS_PATH = HARNESS_ROOT / "claude-progress.txt"
ESCALATION_PATH = HARNESS_ROOT / "escalation-log.md"


# ──────────────────────────────────────────────
# Generator 서브에이전트 호출
# ──────────────────────────────────────────────


def _eval_request_path(sprint_id: str) -> Path:
    return HARNESS_ROOT / "sprints" / sprint_id / "evaluation-request.md"


def _build_generator_prompt(sprint_id: str, sprint_data: dict, feedback: str = "") -> str:
    ac_lines = "\n".join(
        f"  - [{ac['id']}] {ac['description']} (verification: {ac['verification']})"
        for ac in sprint_data.get("acceptance_criteria", [])
    )
    feedback_section = f"\n## 이전 시도 피드백 (반드시 반영)\n{feedback}" if feedback else ""
    return (
        f"generator 에이전트로서 {sprint_id}를 구현하십시오.\n\n"
        f"## 스프린트 정보\n"
        f"제목: {sprint_data['title']}\n\n"
        f"### 범위\n"
        + "\n".join(f"- {s}" for s in sprint_data.get("scope", []))
        + f"\n\n### 인수 조건\n{ac_lines}"
        + feedback_section
        + f"\n\n.harness/sprint-contract.yaml과 .harness/claude-progress.txt를 먼저 읽은 뒤 구현을 시작하십시오."
    )


def run_generator(sprint_id: str, sprint_data: dict, feedback: str = "") -> bool:
    """
    `claude -p`로 generator 서브에이전트를 호출한다.
    완료 신호: .harness/sprints/<sprint_id>/evaluation-request.md 존재 여부.
    반환: True = 완료 신호 확인, False = 미완료
    """
    eval_req = _eval_request_path(sprint_id)
    eval_req.unlink(missing_ok=True)  # 이전 시도 결과 초기화

    prompt = _build_generator_prompt(sprint_id, sprint_data, feedback)
    logger.info(f"[Generator] {sprint_id} 호출 시작")

    result = subprocess.run(
        ["claude", "-p", prompt],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=1800,  # 30분 (BERT 파인튜닝 스프린트 고려)
    )

    if result.returncode not in (0, 1):
        logger.error(f"[Generator] claude 프로세스 오류 (exit={result.returncode}):\n{result.stderr[:500]}")
        return False

    completed = eval_req.exists()
    if completed:
        logger.success(f"[Generator] evaluation-request.md 확인 — 구현 완료")
    else:
        logger.warning(f"[Generator] evaluation-request.md 없음 — 구현 미완료")
    return completed


# ──────────────────────────────────────────────
# Evaluator 실행
# ──────────────────────────────────────────────


def run_evaluator(sprint_id: str) -> dict:
    cmd = ["uv", "run", "python", ".harness/evaluator.py", "--sprint", sprint_id, "--json"]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        logger.error(f"[Evaluator] 실행 오류 (exit={result.returncode}):\n{result.stderr[:300]}")
        return {"overall": "FAIL", "failed_acs": ["EVALUATOR_ERROR"]}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.error(f"[Evaluator] 출력 파싱 실패:\n{result.stdout[:300]}")
        return {"overall": "FAIL", "failed_acs": ["EVALUATOR_PARSE_ERROR"]}


def _read_eval_report(sprint_id: str) -> str:
    report_path = HARNESS_ROOT / "sprints" / sprint_id / "evaluation-report.md"
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")
    return "(evaluation-report.md 없음)"


# ──────────────────────────────────────────────
# 진행 상태 갱신
# ──────────────────────────────────────────────


def _update_progress(sprint_id: str, new_status: str) -> None:
    if not PROGRESS_PATH.exists():
        return
    text = PROGRESS_PATH.read_text(encoding="utf-8")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for old in (f"[PENDING] {sprint_id}", f"[IN_PROGRESS] {sprint_id}"):
        if old in text:
            text = text.replace(old, f"[{new_status}] {sprint_id}")
            break

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("마지막 갱신:"):
            lines[i] = f"마지막 갱신: {timestamp} ({sprint_id} → {new_status})"
            break
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def _git_commit(message: str) -> None:
    subprocess.run(["git", "add", ".harness/claude-progress.txt"], cwd=PROJECT_ROOT, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=PROJECT_ROOT, capture_output=True)


def _write_escalation(sprint_id: str, reason: str, context: dict) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = (
        f"\n## {timestamp} — {sprint_id} ESCALATION\n"
        f"**Reason:** {reason}\n\n"
        f"```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```\n"
    )
    with ESCALATION_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)
    logger.warning(f"에스컬레이션 기록: {ESCALATION_PATH}")


# ──────────────────────────────────────────────
# 스프린트 루프
# ──────────────────────────────────────────────


def run_sprint(sprint_id: str, contract: dict, max_retries: int = 3) -> str:
    """
    단일 스프린트의 Generator-Evaluator 루프를 실행한다.
    반환: "PASS" | "ESCALATED_RETRY" | "ESCALATED_STUCK" | "ESCALATED_ERROR"
    """
    sprint_data = next((s for s in contract["sprints"] if s["id"] == sprint_id), None)
    if sprint_data is None:
        logger.error(f"알 수 없는 스프린트: {sprint_id}")
        return "ESCALATED_ERROR"

    _update_progress(sprint_id, "IN_PROGRESS")
    _git_commit(f"[harness] {sprint_id} → IN_PROGRESS")

    failed_acs_history: list[list[str]] = []
    feedback = ""

    for attempt in range(1, max_retries + 1):
        logger.info(f"[{sprint_id}] 시도 {attempt}/{max_retries}")

        completed = run_generator(sprint_id, sprint_data, feedback)
        if not completed:
            context = {"attempt": attempt, "reason": "evaluation-request.md 미작성"}
            if attempt == max_retries:
                _write_escalation(sprint_id, "GENERATOR_NO_COMPLETION_SIGNAL", context)
                _update_progress(sprint_id, "ESCALATED")
                return "ESCALATED_ERROR"
            feedback = "이전 시도에서 evaluation-request.md를 작성하지 않았습니다. 구현 완료 후 반드시 작성하십시오."
            continue

        eval_result = run_evaluator(sprint_id)
        verdict = eval_result.get("overall", "FAIL")
        failed_acs = eval_result.get("failed_acs", [])

        if verdict == "PASS":
            logger.success(f"[{sprint_id}] PASS (시도 {attempt}회)")
            _update_progress(sprint_id, "PASS")
            _git_commit(f"[harness] {sprint_id} → PASS")
            return "PASS"

        logger.warning(f"[{sprint_id}] FAIL — 실패 AC: {failed_acs}")
        failed_acs_history.append(sorted(failed_acs))

        # 구조적 루프 탐지
        if len(failed_acs_history) >= 3:
            recent = failed_acs_history[-3:]
            if all(s == recent[0] for s in recent[1:]):
                _write_escalation(sprint_id, "STUCK_LOOP_DETECTED", {"failed_acs": failed_acs, "attempts": attempt})
                _update_progress(sprint_id, "ESCALATED")
                return "ESCALATED_STUCK"

        # 다음 시도를 위한 피드백 구성
        report_text = _read_eval_report(sprint_id)
        feedback = (
            f"실패한 AC: {', '.join(failed_acs)}\n\n"
            f"evaluation-report.md 내용:\n{report_text[:2000]}"
        )

    _write_escalation(sprint_id, "RETRY_LIMIT_EXCEEDED", {"max_retries": max_retries, "last_failed_acs": failed_acs})
    _update_progress(sprint_id, "ESCALATED")
    return "ESCALATED_RETRY"


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────


def load_contract() -> dict:
    with CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="하네스 오케스트레이터")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sprint", help="단일 스프린트 실행 (예: sprint-01)")
    group.add_argument("--all", action="store_true", help="sprint-01 ~ sprint-05 순서 실행")
    parser.add_argument("--from", dest="from_sprint", help="--all 시작 스프린트 (예: sprint-02)")
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    contract = load_contract()

    if args.sprint:
        outcome = run_sprint(args.sprint, contract, args.max_retries)
        logger.info(f"결과: {outcome}")
        sys.exit(0 if outcome == "PASS" else 1)

    sprint_ids = [s["id"] for s in contract["sprints"] if not s.get("optional")]
    if args.from_sprint:
        try:
            sprint_ids = sprint_ids[sprint_ids.index(args.from_sprint):]
        except ValueError:
            logger.error(f"알 수 없는 시작 스프린트: {args.from_sprint}")
            sys.exit(1)

    for sprint_id in sprint_ids:
        outcome = run_sprint(sprint_id, contract, args.max_retries)
        if outcome != "PASS":
            logger.error(f"[{sprint_id}] {outcome} — 파이프라인 중단")
            sys.exit(1)
        logger.success(f"[{sprint_id}] 완료.")

    logger.success("전체 파이프라인 완료.")
    sys.exit(0)


if __name__ == "__main__":
    main()
