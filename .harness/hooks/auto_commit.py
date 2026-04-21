"""
auto_commit — Claude Code PostToolUse(Write|Edit) 훅.

src/ 또는 tests/ 하위 파일이 변경되면 스프린트 태그 커밋을 자동 생성한다.
.harness/ 파일은 별도 "[harness]" 커밋 메시지를 사용한다.
artifacts/ 파일은 자동 커밋 대상에서 제외 (대용량 파일 방지).

stdin: { "tool_name": "Write"|"Edit", "tool_input": { "file_path": "...", ... }, ... }
exit 0 → 항상 허용 (커밋 실패해도 훅은 성공으로 처리)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# 자동 커밋 대상 경로 규칙
AUTO_COMMIT_RULES: list[tuple[str, str]] = [
    # (경로 prefix, 커밋 메시지 prefix)
    ("src/", "[src]"),
    ("tests/", "[test]"),
    (".harness/sprints/", "[harness]"),
]

# 커밋에서 제외할 경로
EXCLUDE_PREFIXES = ["artifacts/", "data/", "notebooks/"]


def _current_sprint_id() -> str:
    progress = PROJECT_ROOT / ".harness" / "claude-progress.txt"
    if not progress.exists():
        return "sprint-??"
    for line in progress.read_text(encoding="utf-8").splitlines():
        m = re.search(r"\[IN_PROGRESS\]\s+(sprint-\d+)", line)
        if m:
            return m.group(1)
    return "sprint-??"


def _relative_path(abs_path: str) -> str | None:
    """절대 경로를 PROJECT_ROOT 기준 상대 경로로 변환. 프로젝트 외부 경로면 None."""
    try:
        return str(Path(abs_path).relative_to(PROJECT_ROOT))
    except ValueError:
        return None


def _should_commit(rel_path: str) -> tuple[bool, str]:
    """
    커밋 여부와 메시지 prefix를 반환한다.
    반환: (should_commit, prefix)
    """
    if any(rel_path.startswith(ex) for ex in EXCLUDE_PREFIXES):
        return False, ""
    for prefix, msg_prefix in AUTO_COMMIT_RULES:
        if rel_path.startswith(prefix):
            return True, msg_prefix
    return False, ""


def _git_stage_and_commit(rel_path: str, msg_prefix: str, sprint_id: str) -> None:
    file_name = Path(rel_path).name
    commit_msg = f"{msg_prefix} [{sprint_id}] {file_name}"

    subprocess.run(["git", "add", rel_path], cwd=PROJECT_ROOT, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"[auto_commit] 커밋 완료: {commit_msg}", file=sys.stdout)
    # returncode=1 은 "nothing to commit" — 정상 케이스이므로 무시


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = payload.get("tool_input", {})

    # Write 도구는 file_path, Edit 도구는 file_path
    abs_path = tool_input.get("file_path", "")
    if not abs_path:
        sys.exit(0)

    rel_path = _relative_path(abs_path)
    if rel_path is None:
        sys.exit(0)

    should, prefix = _should_commit(rel_path)
    if not should:
        sys.exit(0)

    sprint_id = _current_sprint_id()
    _git_stage_and_commit(rel_path, prefix, sprint_id)
    sys.exit(0)


if __name__ == "__main__":
    main()
