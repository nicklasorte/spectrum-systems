"""VAL-11 certification integrity validation over real DONE-01 seam."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.governance.done_certification import (
    DoneCertificationError,
    run_done_certification,
)


class CertificationIntegrityError(ValueError):
    """Raised when certification integrity validation inputs are malformed."""


_CASE_SPECS: Tuple[Tuple[str, str, str], ...] = (
    (
        "VAL11-A",
        "replay_pass_regression_fail",
        "FAILED",
    ),
    (
        "VAL11-B",
        "replay_pass_error_budget_exhausted",
        "FAILED",
    ),
    (
        "VAL11-C",
        "replay_pass_failure_injection_non_fail_closed",
        "FAILED",
    ),
    (
        "VAL11-D",
        "regression_pass_replay_mismatch",
        "FAILED",
    ),
    (
        "VAL11-E",
        "all_pass_missing_certification_input",
        "FAILED",
    ),
    (
        "VAL11-F",
        "all_pass_inconsistent_trace_linkage",
        "FAILED",
    ),
    (
        "VAL11-G",
        "all_signals_valid",
        "PASSED",
    ),
)


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _stable_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    return f"{prefix}-{_stable_hash(payload)[:12].upper()}"


def _require_list_of_objects(input_refs: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = input_refs.get(field)
    if not isinstance(value, list) or not value:
        raise CertificationIntegrityError(f"{field} must be a non-empty list")
    result: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise CertificationIntegrityError(f"{field}[{idx}] must be an object")
        result.append(_clone(item))
    return result


def _require_policy(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    value = input_refs.get("policy_ref")
    if not isinstance(value, dict):
        raise CertificationIntegrityError("policy_ref must be an object")
    return _clone(value)


def _deterministic_timestamp(base: Dict[str, Any]) -> str:
    candidates = [
        base["replay_results"][0].get("timestamp"),
        base["regression_results"][0].get("created_at"),
        base["error_budget_statuses"][0].get("timestamp"),
        base["failure_injection_results"][0].get("timestamp"),
        base["control_decisions"][0].get("created_at"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    raise CertificationIntegrityError("deterministic timestamp cannot be derived from provided input refs")


def _default_certification_pack() -> Dict[str, Any]:
    pack = _clone(load_example("control_loop_certification_pack"))
    pack["decision"] = "pass"
    pack["certification_status"] = "certified"
    return pack


def _base_inputs(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(input_refs, dict):
        raise CertificationIntegrityError("input_refs must be an object")

    replay_results = _require_list_of_objects(input_refs, "replay_results")
    regression_results = _require_list_of_objects(input_refs, "regression_results")
    error_budget_statuses = _require_list_of_objects(input_refs, "error_budget_statuses")
    failure_injection_results = _require_list_of_objects(input_refs, "failure_injection_results")
    control_decisions = _require_list_of_objects(input_refs, "control_decisions")
    policy_ref = _require_policy(input_refs)

    return {
        "replay_results": replay_results,
        "regression_results": regression_results,
        "error_budget_statuses": error_budget_statuses,
        "failure_injection_results": failure_injection_results,
        "control_decisions": control_decisions,
        "policy_ref": policy_ref,
    }


def _case_payload(base: Dict[str, Any], case_type: str) -> Dict[str, Any]:
    payload = {
        "replay": _clone(base["replay_results"][0]),
        "regression": _clone(base["regression_results"][0]),
        "error_budget": _clone(base["error_budget_statuses"][0]),
        "failure_injection": _clone(base["failure_injection_results"][0]),
        "control_decision": _clone(base["control_decisions"][0]),
        "policy_ref": _clone(base["policy_ref"]),
        "certification_pack": _default_certification_pack(),
        "omit_certification_pack_ref": False,
    }
    trace_id = str(payload["replay"].get("trace_id") or "")
    if not trace_id:
        raise CertificationIntegrityError("replay_results[0].trace_id is required")
    run_id = str(payload["replay"].get("replay_run_id") or payload["replay"].get("original_run_id") or "")
    if not run_id:
        raise CertificationIntegrityError("replay_results[0].replay_run_id is required")

    payload["error_budget"]["trace_refs"]["trace_id"] = trace_id
    payload["regression"]["run_id"] = run_id
    payload["control_decision"]["run_id"] = run_id
    payload["policy_ref"]["run_id"] = run_id
    payload["certification_pack"]["run_id"] = run_id
    payload["control_decision"]["trace_id"] = trace_id
    payload["policy_ref"]["trace_id"] = trace_id
    payload["certification_pack"]["provenance_trace_refs"]["trace_refs"] = [trace_id]

    for result in payload["regression"].get("results") or []:
        result["trace_id"] = trace_id
        result["baseline_trace_id"] = trace_id
        result["current_trace_id"] = trace_id

    payload["failure_injection"]["trace_refs"]["primary"] = trace_id
    payload["failure_injection"]["trace_refs"]["related"] = []
    for result in payload["failure_injection"].get("results") or []:
        result["trace_refs"]["primary"] = trace_id
        result["trace_refs"]["related"] = []

    if case_type == "replay_pass_regression_fail":
        payload["regression"]["overall_status"] = "fail"
        payload["regression"]["regression_status"] = "fail"
        payload["regression"]["failed_traces"] = 1
        payload["regression"]["passed_traces"] = max(0, int(payload["regression"].get("total_traces", 1)) - 1)
        if payload["regression"].get("results"):
            payload["regression"]["results"][0]["passed"] = False
    elif case_type == "replay_pass_error_budget_exhausted":
        payload["error_budget"]["budget_status"] = "exhausted"
    elif case_type == "replay_pass_failure_injection_non_fail_closed":
        payload["failure_injection"]["fail_count"] = 1
        payload["failure_injection"]["pass_count"] = max(0, int(payload["failure_injection"].get("case_count", 1)) - 1)
        if payload["failure_injection"].get("results"):
            payload["failure_injection"]["results"][0]["passed"] = False
            payload["failure_injection"]["results"][0]["expected_outcome"] = "block"
            payload["failure_injection"]["results"][0]["observed_outcome"] = "allow"
            payload["failure_injection"]["results"][0]["invariant_violations"] = ["unexpected_allow_path"]
    elif case_type == "regression_pass_replay_mismatch":
        payload["replay"]["consistency_status"] = "mismatch"
        payload["replay"]["drift_detected"] = True
        payload["replay"]["failure_reason"] = "deterministic mismatch"
        if payload["regression"].get("results"):
            payload["regression"]["results"][0]["mismatch_summary"] = [
                {"field": "replay_final_status", "baseline_value": "allow", "current_value": "deny"}
            ]
    elif case_type == "all_pass_missing_certification_input":
        payload["omit_certification_pack_ref"] = True
    elif case_type == "all_pass_inconsistent_trace_linkage":
        mismatched = f"{payload['replay']['trace_id']}-mismatch"
        payload["control_decision"]["trace_id"] = mismatched
        payload["policy_ref"]["trace_id"] = mismatched
    elif case_type == "all_signals_valid":
        pass
    else:
        raise CertificationIntegrityError(f"unsupported case_type: {case_type}")

    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def _execute_case(case_id: str, case_type: str, expected_outcome: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    input_configuration = {
        "replay_consistency_status": payload["replay"].get("consistency_status"),
        "regression_status": payload["regression"].get("regression_status"),
        "error_budget_status": payload["error_budget"].get("budget_status"),
        "failure_injection_fail_count": payload["failure_injection"].get("fail_count"),
        "control_decision_trace_id": payload["control_decision"].get("trace_id"),
        "omit_certification_pack_ref": bool(payload["omit_certification_pack_ref"]),
    }

    with TemporaryDirectory(prefix=f"val11-{case_id.lower()}-") as tmpdir:
        tmp_path = Path(tmpdir)
        refs = {
            "replay_result_ref": _write_json(tmp_path / "replay.json", payload["replay"]),
            "regression_result_ref": _write_json(tmp_path / "regression.json", payload["regression"]),
            "error_budget_ref": _write_json(tmp_path / "error_budget.json", payload["error_budget"]),
            "failure_injection_ref": _write_json(tmp_path / "failure_injection.json", payload["failure_injection"]),
            "policy_ref": _write_json(tmp_path / "policy.json", payload["policy_ref"]),
        }
        if not payload["omit_certification_pack_ref"]:
            refs["certification_pack_ref"] = _write_json(tmp_path / "certification_pack.json", payload["certification_pack"])

        try:
            certification = run_done_certification(refs)
            actual_outcome = str(certification.get("final_status") or "FAILED")
            blocking_reason = ""
        except DoneCertificationError as exc:
            actual_outcome = "FAILED"
            blocking_reason = str(exc)

    passed = actual_outcome == expected_outcome
    return {
        "case_id": case_id,
        "case_type": case_type,
        "input_configuration": input_configuration,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "passed": passed,
        "blocking_reason": blocking_reason,
    }


def _evaluate_flags(validation_cases: List[Dict[str, Any]]) -> Tuple[bool, bool]:
    false_certification_detected = False
    inconsistent_signal_detected = False
    for case in validation_cases:
        expected = case["expected_outcome"]
        actual = case["actual_outcome"]
        if expected == "FAILED" and actual == "PASSED":
            false_certification_detected = True
            inconsistent_signal_detected = True
    return false_certification_detected, inconsistent_signal_detected


def _trace_ids(base: Dict[str, Any]) -> List[str]:
    values = []
    for replay in base["replay_results"]:
        trace_id = replay.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            values.append(trace_id)
    for decision in base["control_decisions"]:
        trace_id = decision.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            values.append(trace_id)
    return sorted(set(values)) or ["trace-unknown"]


def run_certification_integrity_validation(input_refs: dict) -> dict:
    """Run VAL-11 matrix against real DONE-01 run_done_certification seam."""
    base = _base_inputs(input_refs)

    validation_cases = [
        _execute_case(case_id, case_type, expected_outcome, _case_payload(base, case_type))
        for case_id, case_type, expected_outcome in _CASE_SPECS
    ]

    total_cases = len(validation_cases)
    passed_cases = sum(1 for case in validation_cases if case["passed"])
    failed_cases = total_cases - passed_cases
    false_certification_detected, inconsistent_signal_detected = _evaluate_flags(validation_cases)

    run_identity = {
        "input_refs": {
            "replay_results": len(base["replay_results"]),
            "regression_results": len(base["regression_results"]),
            "error_budget_statuses": len(base["error_budget_statuses"]),
            "failure_injection_results": len(base["failure_injection_results"]),
            "control_decisions": len(base["control_decisions"]),
            "policy_ref": str(base["policy_ref"].get("decision_id") or base["policy_ref"].get("policy_id") or "policy"),
        },
        "cases": [{"case_id": c["case_id"], "expected": c["expected_outcome"], "actual": c["actual_outcome"]} for c in validation_cases],
    }

    result = {
        "validation_run_id": _stable_id("VAL11", run_identity),
        "timestamp": _deterministic_timestamp(base),
        "input_refs": run_identity["input_refs"],
        "validation_cases": validation_cases,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "false_certification_detected": false_certification_detected,
            "inconsistent_signal_detected": inconsistent_signal_detected,
        },
        "final_status": "PASSED" if failed_cases == 0 and not false_certification_detected else "FAILED",
        "trace_ids": _trace_ids(base),
    }

    validate_artifact(result, "certification_integrity_result")
    return result
