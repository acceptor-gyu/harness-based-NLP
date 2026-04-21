"""
Evaluator-LLM — `claude -p`로 evaluator-llm 서브에이전트를 호출해
스크립트로 판정 불가한 AC를 의미적으로 평가한다.

Claude Code 플랜 내에서 동작 (Anthropic API 별도 과금 없음).

현재 대상: AC-05-05 (오분류 분석 품질 판정)

사용:
    uv run python .harness/evaluator_llm.py --sprint sprint-05 --ac AC-05-05 [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


@dataclass
class LLMEvalResult:
    ac_id: str
    verdict: str       # "PASS" | "FAIL" | "SKIP"
    reasoning: str
    details: dict


# ──────────────────────────────────────────────
# AC별 평가 로직
# ──────────────────────────────────────────────


def evaluate_ac_05_05() -> LLMEvalResult:
    """
    AC-05-05: 오분류 케이스 20건 분석 및 원인 분류(3개 이상 카테고리) 기록.
    eval_report.md 내용을 프롬프트에 포함해 evaluator-llm 에이전트에 판정 위임.
    """
    report_path = ARTIFACTS_DIR / "eval_report.md"
    if not report_path.exists():
        return LLMEvalResult(
            ac_id="AC-05-05",
            verdict="FAIL",
            reasoning="artifacts/eval_report.md 파일이 존재하지 않습니다.",
            details={"missing_file": "artifacts/eval_report.md"},
        )

    report_text = report_path.read_text(encoding="utf-8")

    # 파일 내용을 프롬프트에 직접 포함 (Read 도구 불필요 → 더 빠른 응답)
    prompt = (
        "evaluator-llm 에이전트로서 아래 eval_report.md를 평가하십시오.\n\n"
        f"## eval_report.md\n{report_text[:8000]}"
    )

    result = subprocess.run(
        ["claude", "-p", prompt],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode not in (0, 1):
        return LLMEvalResult(
            ac_id="AC-05-05",
            verdict="FAIL",
            reasoning=f"claude 프로세스 오류 (exit={result.returncode})",
            details={"stderr": result.stderr[:300]},
        )

    raw = result.stdout.strip()

    # stdout에서 JSON 추출 (claude가 앞뒤에 텍스트를 붙이는 경우 대비)
    parsed = _extract_json(raw)
    if parsed is None:
        return LLMEvalResult(
            ac_id="AC-05-05",
            verdict="FAIL",
            reasoning=f"응답 JSON 파싱 실패: {raw[:200]}",
            details={"raw": raw[:500]},
        )

    verdict = parsed.get("verdict", "FAIL")
    reasoning = parsed.get("reasoning", "")
    details = {k: v for k, v in parsed.items() if k not in ("verdict", "reasoning")}
    return LLMEvalResult(ac_id="AC-05-05", verdict=verdict, reasoning=reasoning, details=details)


def _extract_json(text: str) -> dict | None:
    """텍스트에서 첫 번째 JSON 객체를 추출한다."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


# ──────────────────────────────────────────────
# AC 라우터
# ──────────────────────────────────────────────

_AC_EVALUATORS = {
    "AC-05-05": evaluate_ac_05_05,
}


def evaluate_ac(ac_id: str) -> LLMEvalResult:
    evaluator = _AC_EVALUATORS.get(ac_id)
    if evaluator is None:
        return LLMEvalResult(
            ac_id=ac_id,
            verdict="SKIP",
            reasoning=f"semantic_eval 핸들러 없음: {ac_id}",
            details={},
        )
    return evaluator()


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Code 기반 의미 평가기")
    parser.add_argument("--sprint", required=True)
    parser.add_argument("--ac", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = evaluate_ac(args.ac)

    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False))
    else:
        icon = "✓" if result.verdict == "PASS" else ("?" if result.verdict == "SKIP" else "✗")
        logger.info(f"[{result.ac_id}] {icon} {result.verdict} — {result.reasoning}")

    sys.exit(0 if result.verdict in ("PASS", "SKIP") else 1)


if __name__ == "__main__":
    main()
