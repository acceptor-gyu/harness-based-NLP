"""
progress_sync — Claude Code Stop 훅 대상 스크립트.

Stop 훅 발생 시:
1. claude-progress.txt에 세션 종료 타임스탬프 기록
2. src/ tests/ artifacts/ 의 미스테이징 변경이 있으면 체크포인트 커밋

stdin: Claude Code Stop 훅 JSON { "session_id": "...", "stop_hook_active": false, ... }
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

HARNESS_ROOT = Path(__file__).parent
PROJECT_ROOT = HARNESS_ROOT.parent
PROGRESS_PATH = HARNESS_ROOT / "claude-progress.txt"

TRACKED_DIRS = ["src", "tests", "artifacts", ".harness"]


def _has_uncommitted_changes() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + TRACKED_DIRS,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _stage_and_commit(message: str) -> bool:
    subprocess.run(["git", "add", "--"] + TRACKED_DIRS, cwd=PROJECT_ROOT, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _update_progress_timestamp(session_id: str) -> None:
    if not PROGRESS_PATH.exists():
        return
    text = PROGRESS_PATH.read_text(encoding="utf-8")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 세션 종료 마커 업데이트 (마지막 갱신 줄 교체)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("마지막 갱신:"):
            lines[i] = f"마지막 갱신: {timestamp} (session={session_id[:8]})"
            break
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def on_stop(session_id: str) -> None:
    logger.info(f"[progress_sync] Stop 훅 실행 (session={session_id[:8]})")

    _update_progress_timestamp(session_id)

    if _has_uncommitted_changes():
        message = f"[harness] checkpoint — session {session_id[:8]} 종료 시점"
        committed = _stage_and_commit(message)
        if committed:
            logger.info(f"[progress_sync] 체크포인트 커밋 완료: {message}")
        else:
            logger.debug("[progress_sync] 커밋할 변경사항 없음 (이미 스테이징됨)")
    else:
        logger.debug("[progress_sync] 미커밋 변경사항 없음")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--on-stop", action="store_true")
    args = parser.parse_args()

    if not args.on_stop:
        sys.exit(0)

    # stdin에서 훅 페이로드 읽기 (없으면 빈 딕셔너리)
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, EOFError):
        payload = {}

    session_id = payload.get("session_id", "unknown")
    on_stop(session_id)
    sys.exit(0)


if __name__ == "__main__":
    main()
