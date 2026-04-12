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


def _eval_type_from_result(item: dict[str, Any]) -> str | None:
    for mode in item.get("failure_modes", []):
        if isinstance(mode, str) and mode.startswith("eval_type:"):
            return mode.split(":", 1)[1]
    return None


def _reason_codes_from_results(eval_results: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            mode
            for item in eval_results
            for mode in item.get("failure_modes", [])
            if isinstance(mode, str) and mode and ":" not in mode
        }
    )


def _canonical_eval_signal(eval_results: list[dict[str, Any]]) -> tuple[str, ...]:
    rows: list[str] = []
    for item in eval_results:
        eval_type = _eval_type_from_result(item) or "unknown"
        status = str(item.get("result_status", "unknown"))
        reasons = sorted(
            mode
            for mode in item.get("failure_modes", [])
            if isinstance(mode, str) and mode and ":" not in mode
        )
        rows.append(f"{eval_type}|{status}|{','.join(reasons)}")
    return tuple(sorted(rows))




def _trace_lineage_from_eval_results(*, eval_results: list[dict[str, Any]], target_ref: str, expected_trace_id: str | None) -> dict[str, bool]:
    trace_linked = True
    trace_complete = True
    for item in eval_results:
        refs = [ref for ref in item.get("provenance_refs", []) if isinstance(ref, str)]
        if target_ref not in refs:
            trace_linked = False
        if not any(ref.startswith("trace://") for ref in refs):
            trace_complete = False
        if expected_trace_id and f"trace://{expected_trace_id}" not in refs:
            trace_complete = False
    return {"trace_linked": trace_linked, "trace_complete": trace_complete}

def _critical_failure_classification(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return bool(normalized and normalized not in {"none", "pass", "ok"})


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

    present_eval_types = sorted({etype for item in eval_results if (etype := _eval_type_from_result(item))})
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
    assurance_audit: dict[str, Any] | None = None,
    trace_integrity_evidence: dict[str, Any] | None = None,
    lineage_provenance_evidence: dict[str, Any] | None = None,
    dependency_state: dict[str, Any] | None = None,
    authority_records: dict[str, Any] | None = None,
    replay_baseline_store: dict[str, Any] | None = None,
    replay_key: str | None = None,
) -> dict[str, Any]:
    policy = _load_policy()
    required_eval_types = list(policy.get("required_eval_types", []))

    present_eval_types = sorted({etype for item in eval_results if (etype := _eval_type_from_result(item))})
    missing_required_eval_types = sorted(set(required_eval_types) - set(present_eval_types))
    reason_codes = _reason_codes_from_results(eval_results)

    blocking_reasons: list[str] = []
    if not required_eval_types:
        blocking_reasons.append("required_eval_types_unavailable")
    if missing_required_eval_types:
        blocking_reasons.append("missing_required_eval_types")
        blocking_reasons.extend(f"missing_eval:{name}" for name in missing_required_eval_types)

    # never trust caller-supplied coverage summary without recomputation.
    declared_required = set(required_eval_coverage.get("required_eval_types") or [])
    if declared_required and declared_required != set(required_eval_types):
        blocking_reasons.append("required_eval_types_mismatch_with_governed_policy")

    summary_present = set(required_eval_coverage.get("present_eval_types") or [])
    if summary_present != set(present_eval_types):
        blocking_reasons.append("required_eval_coverage_summary_mismatch")

    declared_missing = set(required_eval_coverage.get("missing_required_eval_types") or [])
    if declared_missing != set(missing_required_eval_types):
        blocking_reasons.append("required_eval_coverage_missing_set_mismatch")

    overall_fail = bool(missing_required_eval_types)
    has_eval_failures = False
    for item in eval_results:
        eval_type = _eval_type_from_result(item)
        if eval_type in required_eval_types and item.get("result_status") != "pass":
            has_eval_failures = True
            blocking_reasons.append(f"required_eval_failed:{eval_type}")
            overall_fail = True

    if has_eval_failures:
        blocking_reasons.append("contradictory_eval_signals")

    if required_eval_coverage.get("overall_result") != ("pass" if not overall_fail else "fail"):
        blocking_reasons.append("required_eval_coverage_overall_result_mismatch")

    if eval_summary.get("system_status") == "healthy" and (overall_fail or has_eval_failures):
        blocking_reasons.append("eval_summary_contradicts_eval_results")

    if reason_codes:
        blocking_reasons.extend(reason_codes)

    if assurance_audit is None:
        blocking_reasons.append("missing_assurance_audit_artifact")
    else:
        if assurance_audit.get("acceptance_decision") != "accept_candidate":
            blocking_reasons.append("assurance_audit_not_accept_candidate")
        if _critical_failure_classification(assurance_audit.get("failure_classification")):
            blocking_reasons.append("critical_failure_classification_present")

    derived_trace = _trace_lineage_from_eval_results(
        eval_results=eval_results,
        target_ref=target_ref,
        expected_trace_id=eval_summary.get("trace_id") if isinstance(eval_summary, dict) else None,
    )
    if not derived_trace["trace_linked"]:
        blocking_reasons.append("artifact_not_trace_linked")
    if not derived_trace["trace_complete"]:
        blocking_reasons.append("trace_incomplete")

    if trace_integrity_evidence is None:
        blocking_reasons.append("missing_trace_integrity_evidence")
    else:
        if trace_integrity_evidence.get("trace_linked") is not True:
            blocking_reasons.append("artifact_not_trace_linked")
        if trace_integrity_evidence.get("trace_complete") is not True:
            blocking_reasons.append("trace_incomplete")

    if lineage_provenance_evidence is None:
        blocking_reasons.append("missing_lineage_provenance_evidence")
    else:
        if lineage_provenance_evidence.get("lineage_valid") is not True:
            blocking_reasons.append("artifact_lineage_invalid")

    if dependency_state is None:
        blocking_reasons.append("missing_dependency_state")
    else:
        if dependency_state.get("graph_integrity") is not True:
            blocking_reasons.append("dependency_graph_corrupt")
        unresolved = dependency_state.get("unresolved_dependencies") or []
        if unresolved:
            blocking_reasons.append("dependency_graph_unresolved")

    if authority_records is None or not authority_records:
        blocking_reasons.append("missing_version_authority_evidence")

    baseline_regression_detected = "baseline_regression_detected" in reason_codes
    if baseline_regression_detected:
        blocking_reasons.append("baseline_regression_detected")

    version_authority_aligned = "source_version_drift" not in reason_codes and "missing_version_authority_evidence" not in blocking_reasons

    cross_run_inconsistency = False
    if replay_baseline_store is not None and replay_key:
        signal = _canonical_eval_signal(eval_results)
        previous = replay_baseline_store.get(replay_key)
        if previous is not None and tuple(previous.get("signal", ())) != signal:
            cross_run_inconsistency = True
            blocking_reasons.append("cross_run_eval_signal_inconsistency")
        replay_baseline_store[replay_key] = {"signal": signal, "target_ref": target_ref}

    trace_complete = (
        "rax_trace_integrity" in present_eval_types
        and "rax_trace_integrity" not in missing_required_eval_types
        and derived_trace["trace_complete"] is True
        and derived_trace["trace_linked"] is True
        and (trace_integrity_evidence or {}).get("trace_complete") is True
        and (trace_integrity_evidence or {}).get("trace_linked") is True
    )

    blocking_reasons = sorted(set(blocking_reasons))
    ready_for_control = len(blocking_reasons) == 0
    if ready_for_control:
        decision = "ready"
    elif cross_run_inconsistency:
        decision = "hold"
    else:
        decision = "block"

    if blocking_reasons and decision == "ready":
        decision = "block"
        ready_for_control = False

    record = {
        "artifact_type": "rax_control_readiness_record",
        "schema_version": "1.0.0",
        "batch": batch,
        "target_ref": target_ref,
        "ready_for_control": ready_for_control,
        "decision": decision,
        "blocking_reasons": blocking_reasons,
        "required_eval_types": required_eval_types,
        "present_eval_types": present_eval_types,
        "missing_required_eval_types": missing_required_eval_types,
        "trace_complete": trace_complete,
        "baseline_regression_detected": baseline_regression_detected,
        "version_authority_aligned": version_authority_aligned,
    }
    validate_artifact(record, "rax_control_readiness_record")
    return record


def enforce_rax_control_advancement(*, readiness_record: dict[str, Any] | None) -> dict[str, Any]:
    """Mandatory fail-closed control-readiness gate for advancement."""
    reasons: list[str] = []
    if readiness_record is None:
        reasons.append("missing_control_readiness_artifact")
    else:
        try:
            validate_artifact(readiness_record, "rax_control_readiness_record")
        except Exception:
            reasons.append("malformed_control_readiness_artifact")
        else:
            if readiness_record.get("ready_for_control") is not True:
                reasons.append("control_readiness_not_ready")
            if readiness_record.get("decision") != "ready":
                reasons.append("control_readiness_decision_not_ready")
            if readiness_record.get("blocking_reasons"):
                reasons.append("control_readiness_has_blocking_reasons")

    return {
        "allowed": len(reasons) == 0,
        "decision": "ready" if len(reasons) == 0 else "block",
        "ready_for_control": len(reasons) == 0,
        "blocking_reasons": sorted(set(reasons)),
    }


def enforce_required_rax_eval_coverage(*, eval_results: list[dict[str, Any]], required_eval_coverage: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed enforcement record for missing or incomplete required RAX eval coverage."""
    required_eval_types = set(required_eval_coverage.get("required_eval_types") or [])
    present_eval_types = {_eval_type_from_result(item) for item in eval_results}
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
