"""VAL-04 control decision consistency validation over the real evaluation-control seam."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)


class ControlDecisionConsistencyError(ValueError):
    """Raised when VAL-04 inputs are malformed or incomplete."""


_CASE_IDS: Tuple[str, ...] = (
    "VAL04-A",
    "VAL04-B",
    "VAL04-C",
    "VAL04-D",
    "VAL04-E",
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
        raise ControlDecisionConsistencyError(f"{field} must be a non-empty list")
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ControlDecisionConsistencyError(f"{field}[{idx}] must be an object")
        out.append(_clone(item))
    return out


def _require_policy_ref(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    value = input_refs.get("policy_ref")
    if not isinstance(value, (dict, str)):
        raise ControlDecisionConsistencyError("policy_ref must be an object or non-empty string")
    if isinstance(value, str) and not value.strip():
        raise ControlDecisionConsistencyError("policy_ref must be non-empty when provided as a string")
    return _clone(value)


def _require_repeat_count(input_refs: Dict[str, Any]) -> int:
    value = input_refs.get("repeat_count")
    if not isinstance(value, int) or value < 2:
        raise ControlDecisionConsistencyError("repeat_count must be an integer >= 2")
    return value


def _base_inputs(input_refs: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(input_refs, dict):
        raise ControlDecisionConsistencyError("input_refs must be an object")
    base = {
        "eval_summaries": _require_list_of_objects(input_refs, "eval_summaries"),
        "error_budget_statuses": _require_list_of_objects(input_refs, "error_budget_statuses"),
        "monitor_records": _require_list_of_objects(input_refs, "monitor_records"),
        "cross_run_intelligence_decisions": _require_list_of_objects(input_refs, "cross_run_intelligence_decisions"),
        "policy_ref": _require_policy_ref(input_refs),
        "repeat_count": _require_repeat_count(input_refs),
    }
    for eval_summary in base["eval_summaries"]:
        validate_artifact(eval_summary, "eval_summary")
    for budget in base["error_budget_statuses"]:
        validate_artifact(budget, "error_budget_status")
    for record in base["monitor_records"]:
        validate_artifact(record, "evaluation_monitor_record")
    for xrun in base["cross_run_intelligence_decisions"]:
        validate_artifact(xrun, "cross_run_intelligence_decision")
    return base


def _coerce_monitor_to_metrics(record: Dict[str, Any]) -> Dict[str, float]:
    # Legacy monitor shape
    if "pass_rate" in record and "average_reproducibility_score" in record:
        pass_rate = float(record.get("pass_rate", 1.0))
        drift_rate = float((record.get("sli_snapshot") or {}).get("drift_rate", 0.0))
        reproducibility = float(record.get("average_reproducibility_score", 1.0))
        return {
            "replay_success_rate": max(0.0, min(1.0, pass_rate)),
            "drift_exceed_threshold_rate": max(0.0, min(1.0, drift_rate)),
            "reproducibility_score": max(0.0, min(1.0, reproducibility)),
        }

    # Control-loop monitor shape
    slis = record.get("slis") if isinstance(record.get("slis"), dict) else {}
    bundle_success = float(slis.get("bundle_validation_success_rate", 1.0))
    status = str(record.get("status") or "healthy")
    drift_rate = 0.0 if status == "healthy" else 0.3 if status == "indeterminate" else 0.8
    reproducibility = 1.0 if status == "healthy" else 0.5 if status == "indeterminate" else 0.2
    return {
        "replay_success_rate": max(0.0, min(1.0, bundle_success)),
        "drift_exceed_threshold_rate": max(0.0, min(1.0, drift_rate)),
        "reproducibility_score": max(0.0, min(1.0, reproducibility)),
    }


def _budget_from_eval_summary(summary: Dict[str, Any]) -> str:
    system_status = str(summary.get("system_status") or "")
    if system_status == "healthy":
        return "healthy"
    if system_status == "degraded":
        return "warning"
    return "exhausted"


def _make_replay_from_eval_summary(
    eval_summary: Dict[str, Any],
    *,
    budget_status: Dict[str, Any] | None,
    monitor_record: Dict[str, Any] | None,
    xrun: Dict[str, Any] | None,
    replay_id_suffix: str,
) -> Dict[str, Any]:
    replay = _clone(load_example("replay_result"))

    trace_id = str(eval_summary.get("trace_id") or replay.get("trace_id"))
    eval_run_id = str(eval_summary.get("eval_run_id") or "eval-run-val04")
    timestamp = "2026-03-28T00:00:00Z"

    replay["replay_id"] = f"RPL-VAL04-{replay_id_suffix}"
    replay["original_run_id"] = eval_run_id
    replay["replay_run_id"] = eval_run_id
    replay["trace_id"] = trace_id
    replay["timestamp"] = timestamp
    replay["input_artifact_reference"] = f"eval_summary:{eval_run_id}"
    replay["original_decision_reference"] = f"ECD-{eval_run_id}-BASE"
    replay["original_enforcement_reference"] = f"ENF-{eval_run_id}-BASE"
    replay["replay_decision_reference"] = f"ECD-{eval_run_id}-REPLAY"
    replay["replay_enforcement_reference"] = f"ENF-{eval_run_id}-REPLAY"
    replay["provenance"]["trace_id"] = trace_id
    replay["provenance"]["source_artifact_type"] = "eval_summary"
    replay["provenance"]["source_artifact_id"] = eval_run_id

    pass_rate = float(eval_summary.get("pass_rate", 1.0))
    drift_rate = float(eval_summary.get("drift_rate", 0.0))
    reproducibility = float(eval_summary.get("reproducibility_score", 1.0))

    if monitor_record is not None:
        monitor_metrics = _coerce_monitor_to_metrics(monitor_record)
        pass_rate = monitor_metrics["replay_success_rate"]
        drift_rate = monitor_metrics["drift_exceed_threshold_rate"]
        reproducibility = monitor_metrics["reproducibility_score"]

    if xrun is not None and str(xrun.get("schema_version")) == "2.0.0":
        signal = str(xrun.get("system_signal") or "stable")
        if signal == "warning":
            pass_rate = min(pass_rate, 0.8)
            drift_rate = max(drift_rate, 0.3)
            reproducibility = min(reproducibility, 0.7)
        elif signal == "unstable":
            pass_rate = min(pass_rate, 0.4)
            drift_rate = max(drift_rate, 0.8)
            reproducibility = min(reproducibility, 0.3)

    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["observability_metrics"]["timestamp"] = timestamp
    replay["observability_metrics"]["run_ids"] = [eval_run_id]
    replay["observability_metrics"]["metrics"]["replay_success_rate"] = max(0.0, min(1.0, pass_rate))
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = max(0.0, min(1.0, drift_rate))

    budget = replay["error_budget_status"]
    budget["trace_refs"]["trace_id"] = trace_id
    budget["timestamp"] = timestamp
    budget["observability_metrics_id"] = replay["observability_metrics"]["artifact_id"]

    if budget_status is not None:
        budget["budget_status"] = str(budget_status.get("budget_status", "invalid"))
        budget["highest_severity"] = str(budget_status.get("highest_severity", budget["budget_status"]))
        budget["triggered_conditions"] = _clone(budget_status.get("triggered_conditions", []))
        budget["reasons"] = _clone(budget_status.get("reasons", []))
    else:
        status = _budget_from_eval_summary(eval_summary)
        budget["budget_status"] = status
        budget["highest_severity"] = status
        budget["triggered_conditions"] = []
        budget["reasons"] = []

    replay["consistency_status"] = "match" if reproducibility >= 0.8 else "mismatch"
    replay["drift_detected"] = replay["consistency_status"] == "mismatch" or drift_rate > 0.2
    replay["failure_reason"] = None

    final_status = "allow" if pass_rate >= 0.85 and drift_rate <= 0.2 and reproducibility >= 0.8 else "deny"
    replay["replay_decision"] = "allow" if final_status == "allow" else "deny"
    replay["replay_enforcement_action"] = "allow_execution" if final_status == "allow" else "deny_execution"
    replay["replay_final_status"] = final_status
    replay["original_enforcement_action"] = replay["replay_enforcement_action"]
    replay["original_final_status"] = final_status

    replay_for_id = _clone(replay)
    replay_for_id["artifact_id"] = ""
    replay["artifact_id"] = _stable_hash(replay_for_id)

    validate_artifact(replay, "replay_result")
    return replay


def _decision_signature(decision: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "system_status": decision.get("system_status"),
        "system_response": decision.get("system_response"),
        "triggered_signals": _clone(decision.get("triggered_signals") or []),
        "decision": decision.get("decision"),
        "rationale_code": decision.get("rationale_code"),
    }


def _run_repeated_decisions(payload: Dict[str, Any], repeat_count: int) -> Tuple[List[Dict[str, Any]], str]:
    outputs: List[Dict[str, Any]] = []
    for _ in range(repeat_count):
        decision = build_evaluation_control_decision(_clone(payload))
        outputs.append(decision)

    first_sig = _decision_signature(outputs[0])
    for idx, out in enumerate(outputs[1:], start=2):
        if _decision_signature(out) != first_sig:
            return outputs, f"decision divergence detected on repeat #{idx}"

    return outputs, ""


def _malformed_partial_output_detected(entry: Dict[str, Any]) -> bool:
    output = entry.get("output")
    if not isinstance(output, dict):
        return False
    return any(k in output for k in ("system_status", "system_response", "triggered_signals"))


def _run_case(case_id: str, repeat_count: int, payload: Dict[str, Any], expect_fail_closed: bool = False) -> Dict[str, Any]:
    repeated_outputs: List[Dict[str, Any]] = []
    divergence_reason = ""

    for idx in range(repeat_count):
        try:
            decision = build_evaluation_control_decision(_clone(payload))
            repeated_outputs.append(
                {
                    "repeat_index": idx + 1,
                    "outcome": "decision",
                    "output": decision,
                    "error": "",
                }
            )
        except (EvaluationControlError, FileNotFoundError, ValueError) as exc:
            repeated_outputs.append(
                {
                    "repeat_index": idx + 1,
                    "outcome": "error",
                    "output": {},
                    "error": str(exc),
                }
            )

    if expect_fail_closed:
        all_errors = all(r["outcome"] == "error" for r in repeated_outputs)
        any_partial = any(_malformed_partial_output_detected(r) for r in repeated_outputs)
        actual_consistency = all_errors and not any_partial
        if not all_errors:
            divergence_reason = "malformed case did not fail closed"
        elif any_partial:
            divergence_reason = "malformed case produced partial decision output"
        passed = actual_consistency
    else:
        decision_entries = [r for r in repeated_outputs if r["outcome"] == "decision"]
        if len(decision_entries) != repeat_count:
            actual_consistency = False
            divergence_reason = "unexpected fail-closed error on valid deterministic input"
        else:
            signatures = [_decision_signature(r["output"]) for r in decision_entries]
            actual_consistency = all(sig == signatures[0] for sig in signatures[1:])
            if not actual_consistency:
                divergence_reason = "decision divergence across identical input repeats"
        passed = actual_consistency

    return {
        "case_id": case_id,
        "input_signature": _stable_hash(payload),
        "repeated_outputs": repeated_outputs,
        "expected_consistency": True,
        "actual_consistency": actual_consistency,
        "passed": passed,
        "divergence_reason": divergence_reason,
    }


def _trace_ids(base: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for summary in base["eval_summaries"]:
        trace_id = summary.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            values.append(trace_id)
    for xrun in base["cross_run_intelligence_decisions"]:
        for trace_id in xrun.get("trace_ids") or []:
            if isinstance(trace_id, str) and trace_id:
                values.append(trace_id)
    return sorted(set(values))


def run_control_decision_consistency_validation(input_refs: dict) -> dict:
    """Run VAL-04 deterministic consistency validation over real evaluation control seam."""
    base = _base_inputs(input_refs)

    eval_summary = _clone(base["eval_summaries"][0])
    budget = _clone(base["error_budget_statuses"][0])
    monitor = _clone(base["monitor_records"][0])
    xrun = _clone(base["cross_run_intelligence_decisions"][0])
    repeat_count = int(base["repeat_count"])

    case_payloads: Dict[str, Tuple[Dict[str, Any], bool]] = {
        "VAL04-A": (
            _make_replay_from_eval_summary(eval_summary, budget_status=None, monitor_record=None, xrun=None, replay_id_suffix="A"),
            False,
        ),
        "VAL04-B": (
            _make_replay_from_eval_summary(eval_summary, budget_status=budget, monitor_record=None, xrun=None, replay_id_suffix="B"),
            False,
        ),
        "VAL04-C": (
            _make_replay_from_eval_summary(eval_summary, budget_status=budget, monitor_record=monitor, xrun=xrun, replay_id_suffix="C"),
            False,
        ),
        "VAL04-D": (
            _make_replay_from_eval_summary(
                {
                    **eval_summary,
                    "pass_rate": 0.849999,
                    "drift_rate": 0.200001,
                    "reproducibility_score": 0.799999,
                },
                budget_status=budget,
                monitor_record=None,
                xrun=None,
                replay_id_suffix="D",
            ),
            False,
        ),
        "VAL04-E": (
            {
                "artifact_type": "replay_result",
                "schema_version": "1.2.0",
                "replay_id": "RPL-VAL04-E",
            },
            True,
        ),
    }

    validation_cases: List[Dict[str, Any]] = []
    divergence_detected = False
    hidden_state_suspected = False

    for case_id in _CASE_IDS:
        payload, malformed = case_payloads[case_id]
        case_result = _run_case(case_id, repeat_count, payload, expect_fail_closed=malformed)
        validation_cases.append(case_result)

        if not case_result["passed"]:
            divergence_detected = True
            if not malformed:
                hidden_state_suspected = True

    total_cases = len(validation_cases)
    passed_cases = sum(1 for case in validation_cases if case["passed"])
    failed_cases = total_cases - passed_cases

    result = {
        "validation_run_id": _stable_id(
            "VAL04",
            {
                "input_refs": {
                    "eval_summaries": [s.get("eval_run_id") for s in base["eval_summaries"]],
                    "error_budget_statuses": [b.get("artifact_id") for b in base["error_budget_statuses"]],
                    "monitor_records": [m.get("record_id") or m.get("monitor_record_id") for m in base["monitor_records"]],
                    "cross_run_intelligence_decisions": [
                        x.get("intelligence_id") or x.get("decision_id") for x in base["cross_run_intelligence_decisions"]
                    ],
                    "policy_ref": base["policy_ref"],
                },
                "repeat_count": repeat_count,
            },
        ),
        "timestamp": "2026-03-28T00:00:00Z",
        "input_refs": {
            "eval_summaries": [s.get("eval_run_id") for s in base["eval_summaries"]],
            "error_budget_statuses": [b.get("artifact_id") for b in base["error_budget_statuses"]],
            "monitor_records": [m.get("record_id") or m.get("monitor_record_id") for m in base["monitor_records"]],
            "cross_run_intelligence_decisions": [
                x.get("intelligence_id") or x.get("decision_id") for x in base["cross_run_intelligence_decisions"]
            ],
            "policy_ref": base["policy_ref"],
        },
        "repeat_count": repeat_count,
        "validation_cases": validation_cases,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "divergence_detected": divergence_detected,
            "hidden_state_suspected": hidden_state_suspected,
        },
        "final_status": "PASSED" if failed_cases == 0 else "FAILED",
        "trace_ids": _trace_ids(base),
    }

    validate_artifact(result, "control_decision_consistency_result")
    return result
