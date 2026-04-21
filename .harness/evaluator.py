"""
자동 평가 스크립트 — sprint-contract.yaml의 AC 기준으로 PASS/FAIL을 판정한다.

verification 타입별 판정 방식:
- command_exec: 쉘 명령 실행 후 exit code 0 확인
- file_check: 파일 존재 및 크기 > 0 확인
- file_schema: 파일 내 필수 키/섹션 존재 확인
- metric_threshold: 수치가 임계값 이상/이하 확인
- python_assert: assertion 스크립트 실행
- log_schema: 로그 파일에 필수 필드 존재 확인
- integration_test: 통합 테스트 실행

결과는 evaluation-report.md에 기록되고, --json 옵션 사용 시 stdout에 JSON 출력.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger

HARNESS_ROOT = Path(__file__).parent
PROJECT_ROOT = HARNESS_ROOT.parent
CONTRACT_PATH = HARNESS_ROOT / "sprint-contract.yaml"
SPRINTS_DIR = HARNESS_ROOT / "sprints"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


@dataclass
class ACResult:
    ac_id: str
    description: str
    verdict: str  # "PASS" | "FAIL" | "SKIP"
    evidence: str
    details: dict


@dataclass
class SprintEvalResult:
    sprint_id: str
    overall: str
    ac_results: list[ACResult]
    failed_acs: list[str]
    evaluated_at: str
    evaluator_version: str = "1.0.0"


def load_contract() -> dict:
    with CONTRACT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_sprint(contract: dict, sprint_id: str) -> dict:
    for sprint in contract["sprints"]:
        if sprint["id"] == sprint_id:
            return sprint
    raise ValueError(f"알 수 없는 스프린트: {sprint_id}")


def verify_command_exec(ac: dict) -> ACResult:
    """AC의 description에 명시된 명령을 ac['command'] 키로 받는다."""
    cmd = ac.get("command")
    if not cmd:
        return ACResult(ac["id"], ac["description"], "SKIP", "command 필드 없음", {})
    result = subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT, capture_output=True, text=True)
    verdict = "PASS" if result.returncode == 0 else "FAIL"
    return ACResult(
        ac_id=ac["id"],
        description=ac["description"],
        verdict=verdict,
        evidence=f"exit_code={result.returncode}",
        details={"stdout_tail": result.stdout[-500:], "stderr_tail": result.stderr[-500:]},
    )


def verify_file_check(ac: dict) -> ACResult:
    paths = ac.get("paths", [])
    missing = [p for p in paths if not (PROJECT_ROOT / p).exists()]
    empty = [p for p in paths if (PROJECT_ROOT / p).exists() and (PROJECT_ROOT / p).stat().st_size == 0]
    if missing:
        return ACResult(ac["id"], ac["description"], "FAIL", f"누락: {missing}", {"missing": missing})
    if empty:
        return ACResult(ac["id"], ac["description"], "FAIL", f"빈 파일: {empty}", {"empty": empty})
    return ACResult(ac["id"], ac["description"], "PASS", f"모든 파일 존재: {paths}", {})


def verify_metric_threshold(ac: dict, metrics: dict) -> ACResult:
    """artifacts/{sprint_id}_metrics.json에서 AC에 명시된 지표를 조회한다."""
    metric_key = ac.get("metric_key")
    threshold = ac.get("threshold")
    if metric_key is None or threshold is None:
        return ACResult(ac["id"], ac["description"], "SKIP", "metric_key/threshold 없음", {})
    value = metrics.get(metric_key)
    if value is None:
        return ACResult(ac["id"], ac["description"], "FAIL", f"지표 없음: {metric_key}", {})
    op = ac.get("op", ">=")
    passed = (value >= threshold) if op == ">=" else (value <= threshold)
    return ACResult(
        ac_id=ac["id"],
        description=ac["description"],
        verdict="PASS" if passed else "FAIL",
        evidence=f"{metric_key}={value} {op} {threshold}",
        details={"value": value, "threshold": threshold, "op": op},
    )


def verify_file_schema(ac: dict) -> ACResult:
    path = PROJECT_ROOT / ac.get("path", "")
    required_keys = ac.get("required_keys", [])
    if not path.exists():
        return ACResult(ac["id"], ac["description"], "FAIL", f"파일 없음: {path}", {})
    text = path.read_text(encoding="utf-8")
    missing = [k for k in required_keys if k not in text]
    if missing:
        return ACResult(ac["id"], ac["description"], "FAIL", f"필수 키 누락: {missing}", {"missing": missing})
    return ACResult(ac["id"], ac["description"], "PASS", f"모든 필수 키 존재", {})


def verify_python_assert(ac: dict) -> ACResult:
    script = ac.get("script")
    if not script:
        return ACResult(ac["id"], ac["description"], "SKIP", "script 필드 없음", {})
    cmd = ["uv", "run", "python", "-c", script]
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    verdict = "PASS" if result.returncode == 0 else "FAIL"
    return ACResult(
        ac_id=ac["id"],
        description=ac["description"],
        verdict=verdict,
        evidence=f"exit_code={result.returncode}",
        details={"stderr_tail": result.stderr[-500:]},
    )


VERIFIERS = {
    "command_exec": verify_command_exec,
    "file_check": verify_file_check,
    "file_schema": verify_file_schema,
    "python_assert": verify_python_assert,
    "integration_test": verify_command_exec,
    "log_schema": verify_file_schema,
}


def load_metrics(sprint_id: str) -> dict:
    metrics_path = ARTIFACTS_DIR / f"{sprint_id}_metrics.json"
    if not metrics_path.exists():
        return {}
    with metrics_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_sprint(sprint_id: str) -> SprintEvalResult:
    contract = load_contract()
    sprint = find_sprint(contract, sprint_id)
    metrics = load_metrics(sprint_id)

    results: list[ACResult] = []
    for ac in sprint["acceptance_criteria"]:
        verification = ac.get("verification", "command_exec")
        if verification == "metric_threshold":
            results.append(verify_metric_threshold(ac, metrics))
        elif verification in VERIFIERS:
            results.append(VERIFIERS[verification](ac))
        else:
            results.append(ACResult(ac["id"], ac["description"], "SKIP", f"알 수 없는 검증 타입: {verification}", {}))

    failed_acs = [r.ac_id for r in results if r.verdict == "FAIL"]
    overall = "PASS" if not failed_acs else "FAIL"

    return SprintEvalResult(
        sprint_id=sprint_id,
        overall=overall,
        ac_results=results,
        failed_acs=failed_acs,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )


def write_report(result: SprintEvalResult) -> Path:
    sprint_dir = SPRINTS_DIR / result.sprint_id
    sprint_dir.mkdir(parents=True, exist_ok=True)
    report_path = sprint_dir / "evaluation-report.md"

    lines = [
        f"# Evaluation Report: {result.sprint_id}",
        f"평가 일시: {result.evaluated_at}",
        f"평가자: Evaluator-Script v{result.evaluator_version}",
        "",
        f"## 종합 판정: **{result.overall}**",
        "",
        "## AC별 판정 결과",
        "",
        "| AC | 판정 | 근거 |",
        "|----|------|------|",
    ]
    for r in result.ac_results:
        lines.append(f"| {r.ac_id} | {r.verdict} | {r.evidence} |")

    if result.failed_acs:
        lines += ["", "## 실패 AC 상세", ""]
        for r in result.ac_results:
            if r.verdict == "FAIL":
                lines += [f"### {r.ac_id}", f"- 설명: {r.description}", f"- 근거: {r.evidence}", ""]
                if r.details:
                    lines += ["```json", json.dumps(r.details, indent=2, ensure_ascii=False), "```", ""]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="스프린트 자동 평가")
    parser.add_argument("--sprint", required=True)
    parser.add_argument("--json", action="store_true", help="stdout에 JSON 출력")
    args = parser.parse_args()

    result = evaluate_sprint(args.sprint)
    report_path = write_report(result)

    if args.json:
        payload = {
            "sprint_id": result.sprint_id,
            "overall": result.overall,
            "failed_acs": result.failed_acs,
            "report_path": str(report_path),
            "ac_results": [asdict(r) for r in result.ac_results],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        logger.info(f"평가 완료: {result.overall} (리포트: {report_path})")

    sys.exit(0 if result.overall == "PASS" else 1)


if __name__ == "__main__":
    main()
