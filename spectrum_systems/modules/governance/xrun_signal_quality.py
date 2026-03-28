"""VAL-06 XRUN signal quality validation over the real XRUN-01 intelligence seam."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.cross_run_intelligence import (
    CrossRunIntelligenceError,
    run_cross_run_intelligence,
)


class XRunSignalQualityError(ValueError):
    """Raised when VAL-06 inputs are malformed or insufficient."""


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _require_list_of_objects(input_refs: Dict[str, Any], field: str) -> List[Dict[str, Any]]:
    value = input_refs.get(field)
    if not isinstance(value, list) or not value:
        raise XRunSignalQualityError(f"{field} must be a non-empty list")
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise XRunSignalQualityError(f"{field}[{idx}] must be an object")
        out.append(_clone(item))
    return out


def _require_policy_ref(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    value = input_refs.get("policy_ref")
    if not isinstance(value, dict):
        raise XRunSignalQualityError("policy_ref must be an object")
    if not str(value.get("policy_version") or "").strip():
        raise XRunSignalQualityError("policy_ref.policy_version must be a non-empty string")
    return _clone(value)


def _input_refs_artifact(base: Dict[str, Any], expected_outcomes_ref: str = "") -> Dict[str, Any]:
    refs = {
        "replay_results": [str(i.get("replay_id") or i.get("artifact_id") or "unknown") for i in base["replay_results"]],
        "eval_summaries": [str(i.get("eval_run_id") or "unknown") for i in base["eval_summaries"]],
        "regression_results": [str(i.get("run_id") or i.get("suite_id") or "unknown") for i in base["regression_results"]],
        "drift_results": [str(i.get("artifact_id") or "unknown") for i in base["drift_results"]],
        "monitor_records": [str(i.get("monitor_record_id") or i.get("record_id") or "unknown") for i in base["monitor_records"]],
        "policy_ref": str(base["policy_ref"].get("policy_id") or base["policy_ref"].get("policy_version") or "unknown"),
    }
    if expected_outcomes_ref:
        refs["expected_outcomes_ref"] = expected_outcomes_ref
    return refs


def _expected_override(expected_outcomes: Dict[str, Any], case_id: str, key: str, default: Any) -> Any:
    case_payload = expected_outcomes.get(case_id)
    if isinstance(case_payload, dict) and key in case_payload:
        return _clone(case_payload[key])
    return _clone(default)


def _base_inputs(input_refs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    if not isinstance(input_refs, dict):
        raise XRunSignalQualityError("input_refs must be an object")

    base = {
        "replay_results": _require_list_of_objects(input_refs, "replay_results"),
        "eval_summaries": _require_list_of_objects(input_refs, "eval_summaries"),
        "regression_results": _require_list_of_objects(input_refs, "regression_results"),
        "drift_results": _require_list_of_objects(input_refs, "drift_results"),
        "monitor_records": _require_list_of_objects(input_refs, "monitor_records"),
        "policy_ref": _require_policy_ref(input_refs),
    }
    expected_outcomes = input_refs.get("expected_outcomes_ref")
    if expected_outcomes is None:
        expected_outcomes = {}
    if not isinstance(expected_outcomes, dict):
        raise XRunSignalQualityError("expected_outcomes_ref must be an object when provided")

    for idx, summary in enumerate(base["eval_summaries"]):
        try:
            validate_artifact(summary, "eval_summary")
        except Exception as exc:
            raise XRunSignalQualityError(f"eval_summaries[{idx}] is invalid: {exc}") from exc
    for idx, drift in enumerate(base["drift_results"]):
        try:
            validate_artifact(drift, "drift_detection_result")
        except Exception as exc:
            raise XRunSignalQualityError(f"drift_results[{idx}] is invalid: {exc}") from exc
    for idx, monitor in enumerate(base["monitor_records"]):
        try:
            validate_artifact(monitor, "evaluation_monitor_record")
        except Exception as exc:
            raise XRunSignalQualityError(f"monitor_records[{idx}] is invalid: {exc}") from exc

    expected_ref = str(input_refs.get("expected_outcomes_ref_path") or "").strip()
    return base, expected_outcomes, expected_ref


def _build_case_payload(base: Dict[str, Any], case_id: str) -> Dict[str, Any]:
    payload = _clone(base)

    if case_id == "VAL06-A":
        return payload

    if case_id == "VAL06-B":
        payload["eval_summaries"][0]["failure_rate"] = 0.10
        payload["eval_summaries"][0]["pass_rate"] = 0.90
        payload["eval_summaries"][-1]["failure_rate"] = 0.35
        payload["eval_summaries"][-1]["pass_rate"] = 0.65
        return payload

    if case_id == "VAL06-C":
        payload["eval_summaries"][0]["drift_rate"] = 0.05
        payload["eval_summaries"][-1]["drift_rate"] = 0.40
        return payload

    if case_id == "VAL06-D":
        for reg in payload["regression_results"]:
            results = reg.get("results")
            if isinstance(results, list) and results:
                mismatch_target = max(1, int(len(results) * 0.5))
                for idx, item in enumerate(results):
                    if isinstance(item, dict):
                        item["mismatch_summary"] = [{"field": "replay_final_status"}] if idx < mismatch_target else []
        return payload

    if case_id == "VAL06-E":
        payload["eval_summaries"][0]["reproducibility_score"] = 1.0
        payload["eval_summaries"][-1]["reproducibility_score"] = 0.1
        return payload

    if case_id == "VAL06-F":
        payload["eval_summaries"] = [_clone(payload["eval_summaries"][0])]
        return payload

    if case_id == "VAL06-G":
        payload["eval_summaries"][0] = {
            "artifact_type": "eval_summary",
            "schema_version": "1.0.0",
        }
        return payload

    raise XRunSignalQualityError(f"unknown case_id: {case_id}")


def _validate_generated_eval_cases(generated_eval_cases: List[Dict[str, Any]]) -> str:
    for idx, case in enumerate(generated_eval_cases):
        try:
            validate_artifact(case, "eval_case")
        except Exception as exc:
            return f"generated_eval_cases[{idx}] invalid: {exc}"
    return ""


def _evaluate_case(
    *,
    case_id: str,
    case_type: str,
    payload: Dict[str, Any],
    expected_patterns: List[str],
    expected_actions: List[str],
    expected_system_signal: str,
) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    false_pattern = False
    missed_pattern = False
    incorrect_action = False
    incorrect_signal = False

    actual_patterns: List[str] = []
    actual_actions: List[str] = []
    actual_system_signal = "error"
    blocking_reason = ""

    try:
        output = run_cross_run_intelligence(payload)
        decision = output["cross_run_intelligence_decision"]
        actual_patterns = sorted(set(decision.get("detected_patterns") or []))
        actual_actions = sorted(set(decision.get("recommended_actions") or []))
        actual_system_signal = str(decision.get("system_signal") or "error")

        if expected_system_signal == "fail_closed":
            blocking_reason = "expected fail-closed error but decision was emitted"
            incorrect_signal = True
        else:
            expected_pattern_set = set(expected_patterns)
            actual_pattern_set = set(actual_patterns)
            expected_action_set = set(expected_actions)
            actual_action_set = set(actual_actions)

            false_pattern = len(actual_pattern_set - expected_pattern_set) > 0
            missed_pattern = len(expected_pattern_set - actual_pattern_set) > 0
            incorrect_action = actual_action_set != expected_action_set
            incorrect_signal = actual_system_signal != expected_system_signal

            if "generate_eval_cases" in actual_action_set:
                generated = output.get("generated_eval_cases")
                if not isinstance(generated, list) or not generated:
                    incorrect_action = True
                    blocking_reason = "generate_eval_cases recommended without generated eval artifacts"
                else:
                    generated_error = _validate_generated_eval_cases(generated)
                    if generated_error:
                        incorrect_action = True
                        blocking_reason = generated_error

    except CrossRunIntelligenceError as exc:
        actual_system_signal = "fail_closed"
        blocking_reason = str(exc)
        if expected_system_signal != "fail_closed":
            incorrect_signal = True

    passed = not (false_pattern or missed_pattern or incorrect_action or incorrect_signal)

    if not passed and not blocking_reason:
        reasons: List[str] = []
        if false_pattern:
            reasons.append("false_pattern_detected")
        if missed_pattern:
            reasons.append("missed_pattern_detected")
        if incorrect_action:
            reasons.append("incorrect_action_detected")
        if incorrect_signal:
            reasons.append("incorrect_signal_detected")
        blocking_reason = ",".join(reasons)

    return (
        {
            "case_id": case_id,
            "case_type": case_type,
            "expected_patterns": sorted(set(expected_patterns)),
            "actual_patterns": actual_patterns,
            "expected_actions": sorted(set(expected_actions)),
            "actual_actions": actual_actions,
            "expected_system_signal": expected_system_signal,
            "actual_system_signal": actual_system_signal,
            "passed": passed,
            "blocking_reason": blocking_reason,
        },
        {
            "false_pattern_detected": false_pattern,
            "missed_pattern_detected": missed_pattern,
            "incorrect_action_detected": incorrect_action,
            "incorrect_signal_detected": incorrect_signal,
        },
    )


def run_xrun_signal_quality_validation(input_refs: dict) -> dict:
    """Run VAL-06 deterministic matrix against the real run_cross_run_intelligence seam."""
    base, expected_outcomes, expected_outcomes_ref = _base_inputs(input_refs)

    matrix = [
        ("VAL06-A", "stable_baseline", [], [], "stable"),
        ("VAL06-B", "repeated_failure_cluster", ["recurring_failure_type"], ["generate_eval_cases"], "warning"),
        (
            "VAL06-C",
            "rising_drift_trend",
            ["drift_cluster"],
            ["tighten_policy_threshold", "trigger_drift_alert"],
            "warning",
        ),
        ("VAL06-D", "regression_density_spike", ["unstable_module"], ["require_manual_review"], "unstable"),
        ("VAL06-E", "reproducibility_instability", ["unstable_module"], ["require_manual_review"], "unstable"),
        ("VAL06-F", "insufficient_input", [], [], "fail_closed"),
        ("VAL06-G", "malformed_input", [], [], "fail_closed"),
    ]

    validation_cases: List[Dict[str, Any]] = []
    summary_flags = {
        "false_pattern_detected": False,
        "missed_pattern_detected": False,
        "incorrect_action_detected": False,
        "incorrect_signal_detected": False,
    }

    for case_id, case_type, default_patterns, default_actions, default_signal in matrix:
        expected_patterns = _expected_override(expected_outcomes, case_id, "expected_patterns", default_patterns)
        expected_actions = _expected_override(expected_outcomes, case_id, "expected_actions", default_actions)
        expected_signal = _expected_override(expected_outcomes, case_id, "expected_system_signal", default_signal)
        payload = _build_case_payload(base, case_id)
        case_result, case_flags = _evaluate_case(
            case_id=case_id,
            case_type=case_type,
            payload=payload,
            expected_patterns=list(expected_patterns),
            expected_actions=list(expected_actions),
            expected_system_signal=str(expected_signal),
        )
        validation_cases.append(case_result)
        for flag_name, flag_value in case_flags.items():
            summary_flags[flag_name] = summary_flags[flag_name] or bool(flag_value)

    total_cases = len(validation_cases)
    passed_cases = sum(1 for case in validation_cases if case["passed"])
    failed_cases = total_cases - passed_cases

    trace_ids = []
    for summary in base["eval_summaries"]:
        trace_id = summary.get("trace_id")
        if isinstance(trace_id, str) and trace_id and trace_id not in trace_ids:
            trace_ids.append(trace_id)

    result = {
        "validation_run_id": _stable_id("VAL06", {"cases": validation_cases, "input": _input_refs_artifact(base, expected_outcomes_ref)}),
        "timestamp": _now_iso(),
        "input_refs": _input_refs_artifact(base, expected_outcomes_ref),
        "validation_cases": validation_cases,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "false_pattern_detected": summary_flags["false_pattern_detected"],
            "missed_pattern_detected": summary_flags["missed_pattern_detected"],
            "incorrect_action_detected": summary_flags["incorrect_action_detected"],
            "incorrect_signal_detected": summary_flags["incorrect_signal_detected"],
        },
        "final_status": "PASSED" if failed_cases == 0 else "FAILED",
        "trace_ids": trace_ids,
    }

    validate_artifact(result, "xrun_signal_quality_result")
    return result
