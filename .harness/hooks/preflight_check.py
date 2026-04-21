"""
preflight_check — Claude Code PreToolUse(Bash) 훅.

Bash 명령 실행 전 세 가지를 검증한다:
1. 비용 상한 ($20) 초과 여부
2. 학습 명령(train.py) 실행 시 디바이스 가용성
3. 스프린트 순서 위반 (sprint-04 학습 명령인데 01~03이 PASS 아닐 때)

stdin: { "tool_name": "Bash", "tool_input": { "command": "..." }, ... }
exit 0 → 허용, exit 2 → 차단 (stderr 메시지가 사용자에게 표시됨)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = HARNESS_ROOT.parent
COST_LEDGER = HARNESS_ROOT / "cost-ledger.json"
PROGRESS_PATH = HARNESS_ROOT / "claude-progress.txt"

COST_CEILING = 20.0

# 학습 관련 명령 패턴
TRAINING_PATTERNS = [
    re.compile(r"python.*src[/\\]train\.py"),
    re.compile(r"-m\s+src\.train"),
    re.compile(r"torch\.cuda|transformers.*Trainer"),
]

# Sprint-04 이상 학습이 필요한 명령 패턴
SPRINT04_PATTERNS = [
    re.compile(r"src[/\\]train\.py"),
    re.compile(r"-m\s+src\.train"),
]


def _read_current_cost() -> float:
    if not COST_LEDGER.exists():
        return 0.0
    try:
        data = json.loads(COST_LEDGER.read_text(encoding="utf-8"))
        return float(data.get("total_usd", 0.0))
    except Exception:
        return 0.0


def _read_sprint_statuses() -> dict[str, str]:
    """progress.txt에서 각 스프린트의 현재 상태를 파싱한다."""
    if not PROGRESS_PATH.exists():
        return {}
    statuses: dict[str, str] = {}
    pattern = re.compile(r"\[(\w+)\]\s+(sprint-\d+)")
    for line in PROGRESS_PATH.read_text(encoding="utf-8").splitlines():
        m = pattern.search(line)
        if m:
            statuses[m.group(2)] = m.group(1)
    return statuses


def _is_training_command(command: str) -> bool:
    return any(p.search(command) for p in TRAINING_PATTERNS)


def _is_sprint04_command(command: str) -> bool:
    return any(p.search(command) for p in SPRINT04_PATTERNS)


def _check_cost(command: str) -> str | None:
    current = _read_current_cost()
    if current >= COST_CEILING:
        return (
            f"[preflight] 비용 상한 초과: ${current:.2f} / ${COST_CEILING:.2f}\n"
            f"명령 차단: {command[:80]}\n"
            "계속하려면 .harness/cost-ledger.json의 total_usd를 확인하고 상한을 조정하십시오."
        )
    if current >= COST_CEILING * 0.8:
        # 경고 출력은 하되 차단하지 않음 (stdout으로 보내 사용자에게 표시)
        print(
            f"[preflight] 경고: 비용 ${current:.2f} / ${COST_CEILING:.2f} "
            f"({current/COST_CEILING*100:.0f}%) — 상한 근접",
            file=sys.stdout,
        )
    return None


def _check_sprint_order(command: str) -> str | None:
    """Sprint-04 학습 명령 실행 전 sprint-01~03이 PASS인지 확인한다."""
    if not _is_sprint04_command(command):
        return None
    statuses = _read_sprint_statuses()
    prerequisites = ["sprint-01", "sprint-02", "sprint-03"]
    not_passed = [s for s in prerequisites if statuses.get(s) != "PASS"]
    if not_passed:
        return (
            f"[preflight] 순서 위반: {', '.join(not_passed)}가 아직 PASS 아님\n"
            f"Sprint-04 학습 명령은 앞선 스프린트가 모두 PASS여야 실행 가능합니다.\n"
            f"현재 상태: {statuses}"
        )
    return None


def _check_device(command: str) -> str | None:
    """학습 명령인데 MPS/CUDA 모두 없으면 경고 (차단은 안 함)."""
    if not _is_training_command(command):
        return None
    try:
        import torch  # noqa: PLC0415
        has_gpu = torch.cuda.is_available() or (hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
        if not has_gpu:
            print(
                "[preflight] 경고: GPU/MPS를 찾을 수 없습니다. CPU 학습은 매우 느릴 수 있습니다.",
                file=sys.stdout,
            )
    except ImportError:
        pass  # torch 미설치 상태면 이 체크 생략
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)  # 파싱 실패 시 차단하지 않음

    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    # 검사 순서: 비용 > 스프린트 순서 > 디바이스
    for checker in (_check_cost, _check_sprint_order, _check_device):
        error_msg = checker(command)
        if error_msg:
            print(error_msg, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
