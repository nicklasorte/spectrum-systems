#!/usr/bin/env python3
"""Fail-closed CI gate for governed evaluation execution.

Runs the canonical eval flow (eval_run + eval_case set), validates emitted artifacts,
computes threshold/control blocking decisions, writes a machine-readable gate summary,
and exits non-zero for any blocking condition.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.evaluation.eval_engine import run_eval_run  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_control import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    build_evaluation_control_decision,
)
from spectrum_systems.utils.artifact_envelope import build_artifact_envelope  # noqa: E402
from spectrum_systems.utils.deterministic_id import deterministic_id  # noqa: E402


_DEFAULT_POLICY_PATH = _REPO_ROOT / "data" / "policy" / "eval_ci_gate_policy.json"
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "eval_ci_gate"

_EXIT_PASS = 0
_EXIT_FAIL = 1
_EXIT_BLOCKED = 2


@dataclass
class GateArtifacts:
    eval_run: Dict[str, Any]
    eval_cases: List[Dict[str, Any]]
    eval_results: List[Dict[str, Any]]
    eval_summary: Dict[str, Any]
    evaluation_control_decision: Dict[str, Any]


def _gate_run_id(*, seed_payload: Dict[str, Any]) -> str:
    return deterministic_id(prefix="gate", namespace="evaluation_ci_gate_result", payload=seed_payload)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ref_path(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _validate_schema(instance: Dict[str, Any], schema_name: str) -> List[str]:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _git_info() -> Dict[str, Optional[str]]:
    def _run(*args: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=_REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, OSError):
            return None

    return {
        "commit_sha": _run("rev-parse", "HEAD"),
        "branch": _run("rev-parse", "--abbrev-ref", "HEAD"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
    }


def _load_eval_cases(path: Path) -> List[Dict[str, Any]]:
    raw = _load_json(path)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return [raw]
    raise ValueError("eval cases payload must be a JSON object or array")


def _run_gate(
    *,
    eval_run_path: Path,
    eval_cases_path: Path,
    policy: Dict[str, Any],
) -> tuple[Optional[GateArtifacts], List[str], List[str], List[Dict[str, Any]], List[str]]:
    invalid_artifacts: List[str] = []
    blocking_reasons: List[str] = []
    threshold_results: List[Dict[str, Any]] = []
    indeterminate_hits: List[str] = []

    try:
        eval_run = _load_json(eval_run_path)
        eval_cases = _load_eval_cases(eval_cases_path)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        blocking_reasons.append(f"execution_error: unable to load eval inputs ({exc})")
        return None, invalid_artifacts, blocking_reasons, threshold_results, indeterminate_hits

    eval_run_errors = _validate_schema(eval_run, "eval_run")
    if eval_run_errors:
        invalid_artifacts.append("eval_run")
        blocking_reasons.append("invalid_schema: eval_run")

    for index, case in enumerate(eval_cases):
        case_errors = _validate_schema(case, "eval_case")
        if case_errors:
            invalid_artifacts.append(f"eval_case[{index}]")
            blocking_reasons.append(f"invalid_schema: eval_case[{index}]")

    if blocking_reasons:
        return None, invalid_artifacts, blocking_reasons, threshold_results, indeterminate_hits

    try:
        execution = run_eval_run(eval_run, eval_cases)
    except Exception as exc:  # noqa: BLE001
        blocking_reasons.append(f"execution_error: run_eval_run failed ({exc})")
        return None, invalid_artifacts, blocking_reasons, threshold_results, indeterminate_hits

    eval_results = execution.get("eval_results") or []
    eval_summary = execution.get("eval_summary") or {}

    for index, result in enumerate(eval_results):
        result_errors = _validate_schema(result, "eval_result")
        if result_errors:
            invalid_artifacts.append(f"eval_result[{index}]")
            blocking_reasons.append(f"invalid_schema: eval_result[{index}]")

        result_status = str(result.get("result_status", "")).strip().lower()
        failure_modes = [str(item).lower() for item in (result.get("failure_modes") or [])]
        if result_status == "indeterminate" or any("indeterminate" in item for item in failure_modes):
            indeterminate_hits.append(result.get("eval_case_id") or f"eval_result[{index}]")

    summary_errors = _validate_schema(eval_summary, "eval_summary")
    if summary_errors:
        invalid_artifacts.append("eval_summary")
        blocking_reasons.append("invalid_schema: eval_summary")

    if indeterminate_hits and bool(policy.get("indeterminate_is_blocking", True)):
        blocking_reasons.append("indeterminate_eval_outcome_detected")

    thresholds = policy.get("thresholds", {})
    threshold_checks = [
        ("pass_rate_min", float(eval_summary.get("pass_rate", 0.0)) >= float(thresholds.get("pass_rate_min", 1.0))),
        ("failure_rate_max", float(eval_summary.get("failure_rate", 1.0)) <= float(thresholds.get("failure_rate_max", 0.0))),
        ("drift_rate_max", float(eval_summary.get("drift_rate", 1.0)) <= float(thresholds.get("drift_rate_max", 0.0))),
        (
            "reproducibility_score_min",
            float(eval_summary.get("reproducibility_score", 0.0)) >= float(thresholds.get("reproducibility_score_min", 1.0)),
        ),
    ]
    for name, passed in threshold_checks:
        threshold_results.append({"threshold": name, "passed": passed})
        if not passed:
            blocking_reasons.append(f"threshold_failed: {name}")

    control_thresholds = {
        "reliability_threshold": float(thresholds.get("pass_rate_min", DEFAULT_THRESHOLDS["reliability_threshold"])),
        "drift_threshold": float(thresholds.get("drift_rate_max", DEFAULT_THRESHOLDS["drift_threshold"])),
        "trust_threshold": float(
            thresholds.get("reproducibility_score_min", DEFAULT_THRESHOLDS["trust_threshold"])
        ),
    }
    control_thresholds.update(policy.get("control_thresholds", {}))

    try:
        control_decision = build_evaluation_control_decision(eval_summary, thresholds=control_thresholds)
    except Exception as exc:  # noqa: BLE001
        blocking_reasons.append(f"execution_error: control decision failed ({exc})")
        return None, invalid_artifacts, blocking_reasons, threshold_results, indeterminate_hits

    control_errors = _validate_schema(control_decision, "evaluation_control_decision")
    if control_errors:
        invalid_artifacts.append("evaluation_control_decision")
        blocking_reasons.append("invalid_schema: evaluation_control_decision")

    if control_decision.get("system_response") in set(policy.get("blocking_system_responses", ["freeze", "block"])):
        blocking_reasons.append(
            f"control_decision_blocked: {control_decision.get('system_response')}"
        )

    artifacts = GateArtifacts(
        eval_run=eval_run,
        eval_cases=eval_cases,
        eval_results=eval_results,
        eval_summary=eval_summary,
        evaluation_control_decision=control_decision,
    )
    return artifacts, invalid_artifacts, blocking_reasons, threshold_results, indeterminate_hits


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fail-closed eval CI gate.")
    parser.add_argument("--eval-run", default="contracts/examples/eval_run.json")
    parser.add_argument("--eval-cases", default="contracts/examples/eval_case.json")
    parser.add_argument("--policy", default=str(_DEFAULT_POLICY_PATH))
    parser.add_argument("--output-dir", default=str(_DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_path = Path(args.policy)
    required_input_artifacts = ["eval_run", "eval_cases"]
    required_emitted_artifacts = [
        "eval_summary",
        "evaluation_control_decision",
        "evaluation_ci_gate_result",
    ]

    missing_artifacts: List[str] = []
    if not Path(args.eval_run).exists():
        missing_artifacts.append("eval_run")
    if not Path(args.eval_cases).exists():
        missing_artifacts.append("eval_cases")
    if not policy_path.exists():
        missing_artifacts.append("eval_ci_gate_policy")

    if missing_artifacts:
        status = "blocked"
        blocking_reasons = [f"missing_required_artifact: {name}" for name in missing_artifacts]
        summary_id = _gate_run_id(
            seed_payload={
                "status": status,
                "missing_artifacts": sorted(missing_artifacts),
                "eval_run": str(args.eval_run),
                "eval_cases": str(args.eval_cases),
                "policy": str(policy_path),
            }
        )
        summary = {
            "artifact_type": "evaluation_ci_gate_result",
            **build_artifact_envelope(
                artifact_id=summary_id,
                timestamp=_utc_now(),
                schema_version="1.1.0",
                primary_trace_ref=summary_id,
                related_trace_refs=[],
            ),
            "gate_run_id": summary_id,
            "status": status,
            "blocking_reasons": blocking_reasons,
            "required_artifacts_checked": required_input_artifacts + required_emitted_artifacts,
            "missing_artifacts": missing_artifacts,
            "invalid_artifacts": [],
            "eval_summary_refs": [],
            "threshold_results": [],
            "control_decision_ref": None,
            "repo_state": _git_info(),
        }
        _write_json(output_dir / "evaluation_ci_gate_result.json", summary)
        print(f"[eval-ci-gate] BLOCKED: {', '.join(blocking_reasons)}")
        return _EXIT_BLOCKED

    try:
        policy = _load_json(policy_path)
    except (json.JSONDecodeError, OSError) as exc:
        summary_id = _gate_run_id(
            seed_payload={
                "status": "blocked",
                "invalid_artifacts": ["eval_ci_gate_policy"],
                "policy_path": str(policy_path),
            }
        )
        summary = {
            "artifact_type": "evaluation_ci_gate_result",
            **build_artifact_envelope(
                artifact_id=summary_id,
                timestamp=_utc_now(),
                schema_version="1.1.0",
                primary_trace_ref=summary_id,
                related_trace_refs=[],
            ),
            "gate_run_id": summary_id,
            "status": "blocked",
            "blocking_reasons": [f"execution_error: invalid policy ({exc})"],
            "required_artifacts_checked": required_input_artifacts + required_emitted_artifacts,
            "missing_artifacts": [],
            "invalid_artifacts": ["eval_ci_gate_policy"],
            "eval_summary_refs": [],
            "threshold_results": [],
            "control_decision_ref": None,
            "repo_state": _git_info(),
        }
        _write_json(output_dir / "evaluation_ci_gate_result.json", summary)
        print(f"[eval-ci-gate] BLOCKED: invalid policy ({exc})")
        return _EXIT_BLOCKED

    artifacts, invalid_artifacts, blocking_reasons, threshold_results, indeterminate_hits = _run_gate(
        eval_run_path=Path(args.eval_run),
        eval_cases_path=Path(args.eval_cases),
        policy=policy,
    )

    eval_summary_ref = None
    control_ref = None
    trace_refs: List[str] = []
    if artifacts is not None:
        eval_summary_ref = _ref_path(output_dir / "eval_summary.json")
        control_ref = _ref_path(output_dir / "evaluation_control_decision.json")
        _write_json(output_dir / "eval_summary.json", artifacts.eval_summary)
        _write_json(output_dir / "evaluation_control_decision.json", artifacts.evaluation_control_decision)
        trace_id = artifacts.eval_summary.get("trace_id")
        if isinstance(trace_id, str) and trace_id.strip():
            trace_refs.append(trace_id)

    status = "pass"
    exit_code = _EXIT_PASS
    if blocking_reasons:
        threshold_failed = any(reason.startswith("threshold_failed:") for reason in blocking_reasons)
        only_threshold_failures = threshold_failed and all(
            reason.startswith("threshold_failed:") for reason in blocking_reasons
        )
        if only_threshold_failures:
            status = "fail"
            exit_code = _EXIT_FAIL
        else:
            status = "blocked"
            exit_code = _EXIT_BLOCKED

    if (
        indeterminate_hits
        and bool(policy.get("indeterminate_is_blocking", True))
        and "indeterminate_eval_outcome_detected" not in blocking_reasons
    ):
        blocking_reasons.append("indeterminate_eval_outcome_detected")
        status = "blocked"
        exit_code = _EXIT_BLOCKED

    summary_id = _gate_run_id(
        seed_payload={
            "status": status,
            "blocking_reasons": sorted(blocking_reasons),
            "invalid_artifacts": sorted(invalid_artifacts),
            "indeterminate_hits": sorted(indeterminate_hits),
            "eval_run": str(args.eval_run),
            "eval_cases": str(args.eval_cases),
            "policy": str(policy_path),
        }
    )
    sorted_trace_refs = sorted(set(trace_refs))
    summary = {
        "artifact_type": "evaluation_ci_gate_result",
        **build_artifact_envelope(
            artifact_id=summary_id,
            timestamp=_utc_now(),
            schema_version="1.1.0",
            primary_trace_ref=sorted_trace_refs[0] if sorted_trace_refs else summary_id,
            related_trace_refs=sorted_trace_refs[1:] if len(sorted_trace_refs) > 1 else [],
        ),
        "gate_run_id": summary_id,
        "status": status,
        "blocking_reasons": blocking_reasons,
        "required_artifacts_checked": required_input_artifacts + required_emitted_artifacts,
        "missing_artifacts": missing_artifacts,
        "invalid_artifacts": invalid_artifacts,
        "eval_summary_refs": [eval_summary_ref] if eval_summary_ref else [],
        "threshold_results": threshold_results,
        "control_decision_ref": control_ref,
        "repo_state": _git_info(),
    }

    summary_errors = _validate_schema(summary, "evaluation_ci_gate_result")
    if summary_errors:
        summary["status"] = "blocked"
        summary["blocking_reasons"] = list(summary.get("blocking_reasons", [])) + [
            "invalid_schema: evaluation_ci_gate_result"
        ]
        summary["invalid_artifacts"] = sorted(set(summary.get("invalid_artifacts", []) + ["evaluation_ci_gate_result"]))
        exit_code = _EXIT_BLOCKED

    summary_path = output_dir / "evaluation_ci_gate_result.json"
    _write_json(summary_path, summary)

    print(f"[eval-ci-gate] status={summary['status']} exit_code={exit_code}")
    if summary["blocking_reasons"]:
        print("[eval-ci-gate] blocking_reasons:")
        for reason in summary["blocking_reasons"]:
            print(f"  - {reason}")
    print(f"[eval-ci-gate] summary={summary_path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
