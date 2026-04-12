"""Deterministic governed eval runner for RAX semantic and control integrity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import load_example, validate_artifact

RUNNER_NAME = "rax_eval_runner"
RUNNER_VERSION = "1.0.0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_rax_eval_registry() -> dict[str, Any]:
    registry = load_example("rax_eval_registry")
    validate_artifact(registry, "rax_eval_registry")
    return registry


def load_rax_eval_case_set() -> dict[str, Any]:
    case_set = load_example("rax_eval_case_set")
    validate_artifact(case_set, "rax_eval_case_set")
    return case_set


def _load_policy(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    policy_path = root / "config" / "policy" / "rax_eval_policy.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def _status_from_reason_codes(reason_codes: list[str], *, blocking_codes: set[str]) -> str:
    if any(code in blocking_codes for code in reason_codes):
        return "fail"
    return "pass"


def _score_from_status(status: str) -> float:
    return 1.0 if status == "pass" else 0.0


def run_rax_eval_runner(
    *,
    run_id: str,
    target_ref: str,
    trace_id: str,
    input_assurance: dict[str, Any],
    output_assurance: dict[str, Any],
    tests_passed: bool,
    baseline_regression_detected: bool,
    version_authority_aligned: bool,
    omit_eval_types: list[str] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run deterministic required RAX evals and emit eval_result/eval_summary artifacts."""
    policy = _load_policy(repo_root)
    required_eval_types = list(policy["required_eval_types"])
    blocking_codes = set(policy["blocking_failure_reason_codes"])
    omit = set(omit_eval_types or [])

    reason_map: dict[str, list[str]] = {
        "rax_input_semantic_sufficiency": [],
        "rax_owner_intent_alignment": [],
        "rax_normalization_integrity": [],
        "rax_output_semantic_alignment": [],
        "rax_acceptance_check_strength": [],
        "rax_trace_integrity": [],
        "rax_version_authority_alignment": [],
        "rax_regression_against_baseline": [],
        "rax_control_readiness": [],
    }

    for detail in input_assurance.get("details", []):
        if "semantic_intent_insufficient" in detail:
            reason_map["rax_input_semantic_sufficiency"].append("semantic_intent_insufficient")
        if "owner_intent_contradiction" in detail:
            reason_map["rax_owner_intent_alignment"].append("owner_intent_contradiction")
        if "normalization_ambiguity" in detail:
            reason_map["rax_normalization_integrity"].append("normalization_ambiguity")
        if "missing_required_expansion_trace" in detail or "trace " in detail:
            reason_map["rax_trace_integrity"].append("missing_required_expansion_trace")
        if "source_version_drift" in detail:
            reason_map["rax_version_authority_alignment"].append("source_version_drift")

    for detail in output_assurance.get("details", []):
        if "owner_target_contradiction" in detail:
            reason_map["rax_output_semantic_alignment"].append("semantic_target_mismatch")
        if "weak_acceptance_check" in detail:
            reason_map["rax_acceptance_check_strength"].append("weak_acceptance_check")

    if any("semantic_target_mismatch" in item for item in reason_map["rax_output_semantic_alignment"]):
        pass
    if not tests_passed:
        reason_map["rax_control_readiness"].append("tests_failed")

    if baseline_regression_detected:
        reason_map["rax_regression_against_baseline"].append("baseline_regression_detected")

    if not version_authority_aligned and "source_version_drift" not in reason_map["rax_version_authority_alignment"]:
        reason_map["rax_version_authority_alignment"].append("source_version_drift")

    # tests-pass but eval-fail must still fail closed
    if tests_passed and any(reason_map[eval_type] for eval_type in required_eval_types if eval_type != "rax_control_readiness"):
        reason_map["rax_control_readiness"].append("tests_pass_eval_fail")

    eval_results: list[dict[str, Any]] = []
    for eval_type in required_eval_types:
        if eval_type in omit:
            continue
        reason_codes = reason_map[eval_type]
        status = _status_from_reason_codes(reason_codes, blocking_codes=blocking_codes)
        result = {
            "artifact_type": "eval_result",
            "schema_version": "1.0.0",
            "eval_case_id": f"{run_id}:{eval_type}",
            "run_id": run_id,
            "trace_id": trace_id,
            "result_status": status,
            "score": _score_from_status(status),
            "failure_modes": [f"eval_type:{eval_type}", *list(reason_codes), f"runner:{RUNNER_NAME}:{RUNNER_VERSION}"],
            "provenance_refs": [target_ref, f"trace://{trace_id}", f"eval_type://{eval_type}"],
        }
        validate_artifact(result, "eval_result")
        eval_results.append(result)

    present_eval_types = sorted({next((mode.split(":",1)[1] for mode in item.get("failure_modes", []) if mode.startswith("eval_type:")), "") for item in eval_results if item.get("failure_modes")})
    present_eval_types = [item for item in present_eval_types if item]
    missing_required_eval_types = sorted(set(required_eval_types) - set(present_eval_types))
    fail_closed = bool(missing_required_eval_types)

    failures = [item for item in eval_results if item["result_status"] != "pass"]
    overall_fail = bool(failures) or fail_closed

    eval_summary = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "eval_run_id": run_id,
        "pass_rate": 0.0 if not eval_results else sum(item["score"] for item in eval_results) / len(eval_results),
        "failure_rate": 1.0 if not eval_results else len(failures) / len(eval_results),
        "drift_rate": 1.0 if baseline_regression_detected else 0.0,
        "reproducibility_score": 1.0,
        "system_status": "failing" if overall_fail else "healthy",
    }
    validate_artifact(eval_summary, "eval_summary")

    return {
        "eval_results": eval_results,
        "eval_summary": eval_summary,
        "required_eval_coverage": {
            "required_eval_types": required_eval_types,
            "present_eval_types": present_eval_types,
            "missing_required_eval_types": missing_required_eval_types,
            "overall_result": "fail" if overall_fail else "pass",
            "missing_required_eval_handling": policy.get("missing_required_eval_handling", "fail_closed"),
        },
    }


def build_rax_control_readiness_record(
    *,
    batch: str,
    target_ref: str,
    eval_summary: dict[str, Any],
    eval_results: list[dict[str, Any]],
    required_eval_coverage: dict[str, Any],
) -> dict[str, Any]:
    required_eval_types = list(required_eval_coverage.get("required_eval_types") or [])
    present_eval_types = list(required_eval_coverage.get("present_eval_types") or [])
    missing_required_eval_types = list(required_eval_coverage.get("missing_required_eval_types") or [])

    reason_codes = sorted({mode for item in eval_results for mode in item.get("failure_modes", []) if mode and ":" not in mode})
    blocking_reasons = list(missing_required_eval_types)
    blocking_reasons.extend(reason_codes)

    trace_complete = "rax_trace_integrity" in present_eval_types and "rax_trace_integrity" not in missing_required_eval_types
    baseline_regression_detected = "baseline_regression_detected" in reason_codes
    version_authority_aligned = "source_version_drift" not in reason_codes

    ready_for_control = (
        required_eval_coverage.get("overall_result") == "pass"
        and not missing_required_eval_types
        and trace_complete
        and not baseline_regression_detected
        and version_authority_aligned
    )
    decision = "ready" if ready_for_control else "block"

    record = {
        "artifact_type": "rax_control_readiness_record",
        "schema_version": "1.0.0",
        "batch": batch,
        "target_ref": target_ref,
        "ready_for_control": ready_for_control,
        "decision": decision,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "required_eval_types": required_eval_types,
        "present_eval_types": present_eval_types,
        "missing_required_eval_types": missing_required_eval_types,
        "trace_complete": trace_complete,
        "baseline_regression_detected": baseline_regression_detected,
        "version_authority_aligned": version_authority_aligned,
    }
    validate_artifact(record, "rax_control_readiness_record")
    return record


def enforce_required_rax_eval_coverage(*, eval_results: list[dict[str, Any]], required_eval_coverage: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed enforcement record for missing or incomplete required RAX eval coverage."""
    required_eval_types = set(required_eval_coverage.get("required_eval_types") or [])
    present_eval_types = {next((mode.split(":",1)[1] for mode in item.get("failure_modes", []) if mode.startswith("eval_type:")), None) for item in eval_results}
    present_eval_types.discard(None)
    missing_from_results = sorted(required_eval_types - present_eval_types)
    missing_from_summary = sorted(required_eval_types - set(required_eval_coverage.get("present_eval_types") or []))

    blocked = bool(missing_from_results or missing_from_summary or required_eval_coverage.get("overall_result") != "pass")
    reasons: list[str] = []
    if missing_from_results:
        reasons.append("missing_required_eval_artifact")
    if missing_from_summary:
        reasons.append("eval_summary_missing_required_eval_reference")
    if required_eval_coverage.get("overall_result") != "pass":
        reasons.append("eval_summary_not_pass")

    return {
        "blocked": blocked,
        "reasons": sorted(set(reasons)),
        "missing_from_results": missing_from_results,
        "missing_from_summary": missing_from_summary,
    }
