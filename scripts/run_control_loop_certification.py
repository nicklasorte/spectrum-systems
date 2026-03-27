#!/usr/bin/env python3
"""Build a governed control-loop certification pack for trust-boundary/runtime."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.utils.deterministic_id import deterministic_id  # noqa: E402

DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "control_loop_certification" / "control_loop_certification_pack.json"
DEFAULT_CHAOS_OUTPUT_PATH = _REPO_ROOT / "outputs" / "control_loop_chaos" / "evaluation_control_chaos_summary.json"
DEFAULT_LOG_DIR = _REPO_ROOT / "outputs" / "control_loop_certification"
DEFAULT_REVIEW_JSON = (
    _REPO_ROOT / "docs" / "reviews" / "2026-03-27-control-loop-trust-boundary-surgical-review.json"
)
DEFAULT_REVIEW_MD = (
    _REPO_ROOT / "docs" / "reviews" / "2026-03-27-control-loop-trust-boundary-surgical-review.md"
)

DEFAULT_COMMANDS = {
    "control_loop_chaos_runner": (
        "python scripts/run_control_loop_chaos_tests.py "
        "--scenarios tests/fixtures/control_loop_chaos_scenarios.json "
        "--output outputs/control_loop_chaos/evaluation_control_chaos_summary.json"
    ),
    "targeted_control_loop_eval_gate_tests": (
        "pytest tests/test_control_loop.py tests/test_control_loop_chaos.py tests/test_eval_ci_gate.py -q"
    ),
    "review_artifact_validation": (
        "python scripts/validate_review_artifact.py "
        "docs/reviews/2026-03-27-control-loop-trust-boundary-surgical-review.json "
        "--markdown docs/reviews/2026-03-27-control-loop-trust-boundary-surgical-review.md"
    ),
    "repo_review_validator": "python scripts/validate_review_artifacts.py",
}

CHECK_NAMES = {
    "control_loop_chaos_runner": "Control-loop chaos runner",
    "targeted_control_loop_eval_gate_tests": "Targeted control-loop/eval gate test set",
    "review_artifact_validation": "Review artifact pair validation",
    "repo_review_validator": "Repository review validator",
}

REQUIRED_CHECK_IDS = tuple(DEFAULT_COMMANDS.keys())


@dataclass
class CheckResult:
    check_id: str
    check_name: str
    command: str
    status: str
    exit_code: int | None
    evidence_ref: str
    summary: str


@dataclass
class CommandExecution:
    exit_code: int
    stdout: str
    stderr: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ref_path(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _run_command(command: str) -> CommandExecution:
    result = subprocess.run(
        shlex.split(command),
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandExecution(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def _git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "unknown"


def _status_from_checks(checks: list[CheckResult]) -> tuple[str, str]:
    statuses = {check.status for check in checks}
    if "blocked" in statuses:
        return "blocked", "blocked"
    if "fail" in statuses:
        return "uncertified", "fail"
    return "certified", "pass"


def _validate_chaos_payload(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "chaos output is not a JSON object"
    for key in ("chaos_run_id", "scenario_count", "pass_count", "fail_count"):
        if key not in payload:
            return False, f"chaos output missing required key: {key}"
    for key in ("scenario_count", "pass_count", "fail_count"):
        if not isinstance(payload.get(key), int) or payload[key] < 0:
            return False, f"chaos output key '{key}' must be a non-negative integer"
    return True, ""


def _check_missing_required_commands(commands: dict[str, str]) -> list[CheckResult]:
    missing_ids = [check_id for check_id in REQUIRED_CHECK_IDS if not commands.get(check_id, "").strip()]
    if not missing_ids:
        return []

    blocked: list[CheckResult] = []
    for check_id in REQUIRED_CHECK_IDS:
        command = commands.get(check_id, "").strip()
        if check_id in missing_ids:
            summary = "Required check command is missing."
            evidence_ref = "missing"
        else:
            summary = "Check not executed because one or more required commands were missing."
            evidence_ref = "blocked"
        blocked.append(
            CheckResult(
                check_id=check_id,
                check_name=CHECK_NAMES[check_id],
                command=command or "<missing>",
                status="blocked",
                exit_code=None,
                evidence_ref=evidence_ref,
                summary=summary,
            )
        )
    return blocked


def _execute_checks(
    *,
    commands: dict[str, str],
    chaos_output_path: Path,
    review_json: Path,
    review_markdown: Path,
    log_dir: Path,
) -> tuple[list[CheckResult], dict[str, Any], dict[str, Any], dict[str, Any]]:
    log_dir.mkdir(parents=True, exist_ok=True)

    checks: list[CheckResult] = []
    scenario_summary: dict[str, Any] = {
        "chaos_run_id": "blocked",
        "scenario_count": 0,
        "pass_count": 0,
        "fail_count": 0,
    }
    test_summary: dict[str, Any] = {
        "targeted_test_command": commands["targeted_control_loop_eval_gate_tests"],
        "targeted_test_status": "blocked",
        "targeted_test_exit_code": None,
    }
    artifact_validation_summary: dict[str, Any] = {
        "review_artifact_validation_status": "blocked",
        "repo_review_validator_status": "blocked",
    }

    # 1) Chaos runner check.
    chaos_cmd = commands["control_loop_chaos_runner"]
    try:
        chaos_exec = _run_command(chaos_cmd)
    except (OSError, ValueError) as exc:
        checks.append(
            CheckResult(
                check_id="control_loop_chaos_runner",
                check_name=CHECK_NAMES["control_loop_chaos_runner"],
                command=chaos_cmd,
                status="blocked",
                exit_code=None,
                evidence_ref=_ref_path(chaos_output_path),
                summary=f"Unable to execute chaos runner command: {exc}",
            )
        )
    else:
        evidence_ref = _ref_path(chaos_output_path)
        summary = "Chaos runner completed successfully."
        status = "pass" if chaos_exec.exit_code == 0 else "fail"
        if chaos_exec.exit_code == 0:
            try:
                chaos_payload = _load_json(chaos_output_path)
            except (OSError, json.JSONDecodeError) as exc:
                status = "blocked"
                summary = f"Chaos runner output missing or malformed JSON: {exc}"
            else:
                valid, message = _validate_chaos_payload(chaos_payload)
                if not valid:
                    status = "blocked"
                    summary = f"Chaos runner output malformed: {message}"
                else:
                    scenario_summary = {
                        "chaos_run_id": str(chaos_payload["chaos_run_id"]),
                        "scenario_count": int(chaos_payload["scenario_count"]),
                        "pass_count": int(chaos_payload["pass_count"]),
                        "fail_count": int(chaos_payload["fail_count"]),
                    }
                    summary = (
                        f"Chaos runner passed with {scenario_summary['pass_count']} passing "
                        f"scenario(s) and {scenario_summary['fail_count']} failing scenario(s)."
                    )
        else:
            summary = f"Chaos runner exited non-zero ({chaos_exec.exit_code})."
        checks.append(
            CheckResult(
                check_id="control_loop_chaos_runner",
                check_name=CHECK_NAMES["control_loop_chaos_runner"],
                command=chaos_cmd,
                status=status,
                exit_code=chaos_exec.exit_code,
                evidence_ref=evidence_ref,
                summary=summary,
            )
        )

    # 2) Targeted test check.
    tests_cmd = commands["targeted_control_loop_eval_gate_tests"]
    tests_log = log_dir / "targeted_test_output.log"
    try:
        tests_exec = _run_command(tests_cmd)
    except (OSError, ValueError) as exc:
        checks.append(
            CheckResult(
                check_id="targeted_control_loop_eval_gate_tests",
                check_name=CHECK_NAMES["targeted_control_loop_eval_gate_tests"],
                command=tests_cmd,
                status="blocked",
                exit_code=None,
                evidence_ref=_ref_path(tests_log),
                summary=f"Unable to execute targeted test command: {exc}",
            )
        )
    else:
        tests_log.write_text(
            f"STDOUT:\n{tests_exec.stdout}\n\nSTDERR:\n{tests_exec.stderr}\n",
            encoding="utf-8",
        )
        status = "pass" if tests_exec.exit_code == 0 else "fail"
        test_summary = {
            "targeted_test_command": tests_cmd,
            "targeted_test_status": status,
            "targeted_test_exit_code": tests_exec.exit_code,
        }
        checks.append(
            CheckResult(
                check_id="targeted_control_loop_eval_gate_tests",
                check_name=CHECK_NAMES["targeted_control_loop_eval_gate_tests"],
                command=tests_cmd,
                status=status,
                exit_code=tests_exec.exit_code,
                evidence_ref=_ref_path(tests_log),
                summary=(
                    "Targeted test command completed successfully."
                    if status == "pass"
                    else f"Targeted test command exited non-zero ({tests_exec.exit_code})."
                ),
            )
        )

    # 3) Pairwise review artifact validation check.
    review_cmd = commands["review_artifact_validation"]
    if not review_json.is_file() or not review_markdown.is_file():
        status = "blocked"
        exit_code = None
        summary = (
            "Required review artifact evidence missing: "
            f"json_exists={review_json.is_file()} markdown_exists={review_markdown.is_file()}"
        )
    else:
        try:
            review_exec = _run_command(review_cmd)
        except (OSError, ValueError) as exc:
            status = "blocked"
            exit_code = None
            summary = f"Unable to execute review artifact validation command: {exc}"
        else:
            status = "pass" if review_exec.exit_code == 0 else "fail"
            exit_code = review_exec.exit_code
            summary = (
                "Pairwise review artifact validation passed."
                if status == "pass"
                else f"Pairwise review artifact validation exited non-zero ({review_exec.exit_code})."
            )

    artifact_validation_summary["review_artifact_validation_status"] = status
    checks.append(
        CheckResult(
            check_id="review_artifact_validation",
            check_name=CHECK_NAMES["review_artifact_validation"],
            command=review_cmd,
            status=status,
            exit_code=exit_code,
            evidence_ref=_ref_path(review_json),
            summary=summary,
        )
    )

    # 4) Repo-level review validation check.
    repo_cmd = commands["repo_review_validator"]
    repo_log = log_dir / "repo_review_validation.log"
    try:
        repo_exec = _run_command(repo_cmd)
    except (OSError, ValueError) as exc:
        checks.append(
            CheckResult(
                check_id="repo_review_validator",
                check_name=CHECK_NAMES["repo_review_validator"],
                command=repo_cmd,
                status="blocked",
                exit_code=None,
                evidence_ref=_ref_path(repo_log),
                summary=f"Unable to execute repository review validator command: {exc}",
            )
        )
    else:
        repo_log.write_text(
            f"STDOUT:\n{repo_exec.stdout}\n\nSTDERR:\n{repo_exec.stderr}\n",
            encoding="utf-8",
        )
        status = "pass" if repo_exec.exit_code == 0 else "fail"
        artifact_validation_summary["repo_review_validator_status"] = status
        checks.append(
            CheckResult(
                check_id="repo_review_validator",
                check_name=CHECK_NAMES["repo_review_validator"],
                command=repo_cmd,
                status=status,
                exit_code=repo_exec.exit_code,
                evidence_ref=_ref_path(repo_log),
                summary=(
                    "Repository review validator passed."
                    if status == "pass"
                    else f"Repository review validator exited non-zero ({repo_exec.exit_code})."
                ),
            )
        )

    return checks, scenario_summary, test_summary, artifact_validation_summary


def _build_certification_artifact(
    *,
    checks: list[CheckResult],
    scenario_summary: dict[str, Any],
    test_summary: dict[str, Any],
    artifact_validation_summary: dict[str, Any],
    related_review_refs: list[str],
    related_plan_refs: list[str],
) -> dict[str, Any]:
    certification_status, decision = _status_from_checks(checks)

    id_payload = {
        "certification_scope": "trust-boundary/runtime",
        "certification_status": certification_status,
        "decision": decision,
        "executed_checks": [
            {
                "check_id": c.check_id,
                "status": c.status,
                "exit_code": c.exit_code,
                "evidence_ref": c.evidence_ref,
            }
            for c in checks
        ],
        "related_review_refs": sorted(related_review_refs),
        "related_plan_refs": sorted(related_plan_refs),
    }

    return {
        "artifact_type": "control_loop_certification_pack",
        "schema_version": "1.0.0",
        "certification_id": deterministic_id(
            prefix="clcp",
            namespace="control_loop_certification_pack",
            payload=id_payload,
        ),
        "certification_scope": "trust-boundary/runtime",
        "certification_status": certification_status,
        "decision": decision,
        "executed_checks": [
            {
                "check_id": c.check_id,
                "check_name": c.check_name,
                "status": c.status,
                "exit_code": c.exit_code,
                "command": c.command,
                "evidence_ref": c.evidence_ref,
                "summary": c.summary,
            }
            for c in checks
        ],
        "scenario_summary": scenario_summary,
        "test_summary": test_summary,
        "artifact_validation_summary": artifact_validation_summary,
        "related_review_refs": related_review_refs,
        "related_plan_refs": related_plan_refs,
        "generated_at": _utc_now(),
        "provenance_trace_refs": {
            "commit_sha": _git_value("rev-parse", "HEAD"),
            "branch": _git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "trace_refs": [
                f"control_loop_chaos:{scenario_summary.get('chaos_run_id', 'blocked')}",
                f"review_artifact:{related_review_refs[0] if related_review_refs else 'missing'}",
            ],
        },
    }


def _validate_certification_schema(artifact: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(
        load_schema("control_loop_certification_pack"),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(artifact), key=lambda error: list(error.absolute_path))
    return [f"{list(err.absolute_path) or ['root']}: {err.message}" for err in errors]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run governed control-loop certification pack checks.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to write certification artifact JSON.")
    parser.add_argument(
        "--chaos-output",
        default=str(DEFAULT_CHAOS_OUTPUT_PATH),
        help="Path to chaos summary JSON emitted by the chaos runner check.",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Directory for generated command output logs.",
    )
    parser.add_argument("--review-json", default=str(DEFAULT_REVIEW_JSON), help="Review artifact JSON path.")
    parser.add_argument("--review-markdown", default=str(DEFAULT_REVIEW_MD), help="Review artifact markdown path.")
    parser.add_argument(
        "--related-plan-ref",
        action="append",
        default=["docs/review-actions/PLAN-PQX-CLT-003-2026-03-27.md"],
        help="Related plan reference (repeatable).",
    )
    parser.add_argument(
        "--related-review-ref",
        action="append",
        default=[],
        help="Related review reference (repeatable). Defaults to --review-json path.",
    )
    parser.add_argument("--chaos-command", default=DEFAULT_COMMANDS["control_loop_chaos_runner"])
    parser.add_argument("--tests-command", default=DEFAULT_COMMANDS["targeted_control_loop_eval_gate_tests"])
    parser.add_argument("--review-command", default=DEFAULT_COMMANDS["review_artifact_validation"])
    parser.add_argument("--repo-review-command", default=DEFAULT_COMMANDS["repo_review_validator"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    commands = {
        "control_loop_chaos_runner": args.chaos_command.strip(),
        "targeted_control_loop_eval_gate_tests": args.tests_command.strip(),
        "review_artifact_validation": args.review_command.strip(),
        "repo_review_validator": args.repo_review_command.strip(),
    }

    checks = _check_missing_required_commands(commands)

    if not checks:
        executed, scenario_summary, test_summary, artifact_validation_summary = _execute_checks(
            commands=commands,
            chaos_output_path=Path(args.chaos_output).resolve(),
            review_json=Path(args.review_json).resolve(),
            review_markdown=Path(args.review_markdown).resolve(),
            log_dir=Path(args.log_dir).resolve(),
        )
        checks.extend(executed)
    else:
        scenario_summary = {
            "chaos_run_id": "blocked",
            "scenario_count": 0,
            "pass_count": 0,
            "fail_count": 0,
        }
        test_summary = {
            "targeted_test_command": commands["targeted_control_loop_eval_gate_tests"] or "<missing>",
            "targeted_test_status": "blocked",
            "targeted_test_exit_code": None,
        }
        artifact_validation_summary = {
            "review_artifact_validation_status": "blocked",
            "repo_review_validator_status": "blocked",
        }

    related_review_refs = args.related_review_ref or [str(Path(args.review_json).as_posix())]
    related_plan_refs = args.related_plan_ref

    artifact = _build_certification_artifact(
        checks=checks,
        scenario_summary=scenario_summary,
        test_summary=test_summary,
        artifact_validation_summary=artifact_validation_summary,
        related_review_refs=related_review_refs,
        related_plan_refs=related_plan_refs,
    )

    schema_errors = _validate_certification_schema(artifact)
    if schema_errors:
        artifact["certification_status"] = "blocked"
        artifact["decision"] = "blocked"
        artifact["executed_checks"].append(
            {
                "check_id": "repo_review_validator",
                "check_name": "Schema self-validation",
                "status": "blocked",
                "exit_code": None,
                "command": "internal:schema_validation",
                "evidence_ref": "contracts/schemas/control_loop_certification_pack.schema.json",
                "summary": f"Generated artifact failed schema validation: {'; '.join(schema_errors)}",
            }
        )

    output_path = Path(args.output).resolve()
    _write_json(output_path, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))

    status = artifact["certification_status"]
    if status == "certified":
        return 0
    if status == "uncertified":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
