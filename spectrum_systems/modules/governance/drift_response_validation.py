"""VAL-09 drift response validation over deterministic replay drift progression."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Tuple

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.drift_detection import (
    DriftDetectionError,
    build_drift_detection_result,
)
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)


class DriftResponseValidationError(ValueError):
    """Raised when VAL-09 inputs are malformed or incomplete."""


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _stable_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    return f"{prefix}-{_stable_hash(payload)[:12].upper()}"


def _require_object(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise DriftResponseValidationError(f"{field_name} must be an object")
    return _clone(value)


def _require_replay_results(input_refs: Dict[str, Any]) -> List[Dict[str, Any]]:
    value = input_refs.get("replay_results")
    if not isinstance(value, list) or not value:
        raise DriftResponseValidationError("replay_results must be a non-empty list")
    outputs: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise DriftResponseValidationError(f"replay_results[{idx}] must be an object")
        outputs.append(_clone(item))
    return outputs


def _require_timestamp(replay_results: List[Dict[str, Any]]) -> str:
    for replay in replay_results:
        value = replay.get("timestamp")
        if isinstance(value, str) and value:
            return value
    raise DriftResponseValidationError("deterministic timestamp cannot be derived from replay_results")


def _apply_drift_stage(replay: Dict[str, Any], stage: int) -> Dict[str, Any]:
    staged = _clone(replay)
    staged["replay_run_id"] = f"{replay.get('replay_run_id', 'replay-run')}-stage-{stage}"
    staged["replay_id"] = f"{replay.get('replay_id', 'replay-id')}-stage-{stage}"
    staged["observability_metrics"]["run_ids"] = [staged["replay_run_id"]]
    staged["observability_metrics"]["source_artifact_ids"] = [staged["replay_id"]]

    if stage >= 1:
        staged["consistency_status"] = "mismatch"
        staged["drift_detected"] = True
        staged["failure_reason"] = None
        staged["replay_enforcement_action"] = "deny_execution"
        staged["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = 0.30
    if stage >= 2:
        staged["replay_final_status"] = "deny"
        staged["replay_decision"] = "deny"
        staged["consistency_status"] = "mismatch"
        staged["drift_detected"] = True
        staged["failure_reason"] = None
        staged["observability_metrics"]["metrics"]["replay_success_rate"] = 0.80
    if stage >= 3:
        staged["consistency_status"] = "indeterminate"
        staged["drift_detected"] = False
        staged["failure_reason"] = "progressive_drift_stage_3"
        staged["observability_metrics"]["metrics"]["replay_success_rate"] = 0.60

    return staged


def _detection_score(drift_result: Dict[str, Any]) -> float:
    metrics = drift_result.get("metrics")
    if not isinstance(metrics, dict):
        return 0.0
    return float(sum(float(v) for v in metrics.values() if isinstance(v, (int, float))))


def _response_rank(system_response: str) -> int:
    ranks = {"allow": 0, "warn": 1, "freeze": 2, "block": 3}
    return ranks.get(system_response, -1)


def _run_detection_and_control(
    baseline_replay: Dict[str, Any],
    policy: Dict[str, Any],
    staged_replay: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    drift_result = build_drift_detection_result(staged_replay, baseline_replay, policy)
    control_decision = build_evaluation_control_decision(staged_replay)
    return drift_result, control_decision


def run_drift_response_validation(input_refs: dict) -> dict:
    """Run VAL-09 deterministic drift-response validation matrix."""
    if not isinstance(input_refs, dict):
        raise DriftResponseValidationError("input_refs must be an object")

    replay_results = _require_replay_results(input_refs)
    baseline_replay = _clone(replay_results[0])
    policy = _require_object(input_refs.get("baseline_gate_policy"), "baseline_gate_policy")

    drift_sequence: List[Dict[str, Any]] = []
    detection_points: List[Dict[str, Any]] = []
    control_responses: List[Dict[str, Any]] = []
    threshold_crossings: List[Dict[str, Any]] = []

    # A: progressive gradual drift across runs (stage 0..3)
    progressive_scores: List[float] = []
    for stage in (0, 1, 2, 3):
        staged = _apply_drift_stage(baseline_replay, stage)
        drift_result, control_decision = _run_detection_and_control(baseline_replay, policy, staged)
        score = _detection_score(drift_result)
        progressive_scores.append(score)

        drift_sequence.append(
            {
                "case_id": f"VAL09-A-{stage}",
                "case_type": "gradual_drift_increase",
                "run_index": stage,
                "drift_detected": bool(drift_result.get("drift_status") != "no_drift"),
                "drift_status": str(drift_result.get("drift_status")),
            }
        )
        detection_points.append(
            {
                "case_id": f"VAL09-A-{stage}",
                "run_index": stage,
                "signal_strength": score,
                "drift_status": str(drift_result.get("drift_status")),
            }
        )
        control_responses.append(
            {
                "case_id": f"VAL09-A-{stage}",
                "run_index": stage,
                "system_status": str(control_decision.get("system_status")),
                "system_response": str(control_decision.get("system_response")),
                "decision": str(control_decision.get("decision")),
            }
        )

    # B: threshold crossing -> warning/freeze response
    stage_b = _apply_drift_stage(baseline_replay, 1)
    drift_b, control_b = _run_detection_and_control(baseline_replay, policy, stage_b)
    threshold_crossings.append(
        {
            "case_id": "VAL09-B",
            "threshold_type": "warning_or_freeze",
            "crossed": bool(drift_b.get("drift_status") != "no_drift"),
            "expected_response": "freeze",
            "actual_response": str(control_b.get("system_response")),
            "response_on_time": str(control_b.get("system_response")) in {"warn", "freeze", "block"},
        }
    )

    # C: late-stage severe drift -> blocked/escalated response
    stage_c = _apply_drift_stage(baseline_replay, 3)
    drift_c, control_c = _run_detection_and_control(baseline_replay, policy, stage_c)
    threshold_crossings.append(
        {
            "case_id": "VAL09-C",
            "threshold_type": "severe",
            "crossed": bool(drift_c.get("drift_status") != "no_drift"),
            "expected_response": "block",
            "actual_response": str(control_c.get("system_response")),
            "response_on_time": str(control_c.get("system_response")) == "block",
        }
    )

    # D: flat baseline no drift -> no false positive
    stage_d = _apply_drift_stage(baseline_replay, 0)
    drift_d, control_d = _run_detection_and_control(baseline_replay, policy, stage_d)
    drift_sequence.append(
        {
            "case_id": "VAL09-D",
            "case_type": "flat_no_drift_baseline",
            "run_index": 0,
            "drift_detected": bool(drift_d.get("drift_status") != "no_drift"),
            "drift_status": str(drift_d.get("drift_status")),
        }
    )
    detection_points.append(
        {
            "case_id": "VAL09-D",
            "run_index": 0,
            "signal_strength": _detection_score(drift_d),
            "drift_status": str(drift_d.get("drift_status")),
        }
    )
    control_responses.append(
        {
            "case_id": "VAL09-D",
            "run_index": 0,
            "system_status": str(control_d.get("system_status")),
            "system_response": str(control_d.get("system_response")),
            "decision": str(control_d.get("decision")),
        }
    )

    # E: insufficient input fail-closed
    insufficient_error = ""
    try:
        _require_replay_results({"replay_results": []})
    except DriftResponseValidationError as exc:
        insufficient_error = str(exc)

    threshold_crossings.append(
        {
            "case_id": "VAL09-E",
            "threshold_type": "insufficient_input_fail_closed",
            "crossed": True,
            "expected_response": "fail_closed",
            "actual_response": "fail_closed" if insufficient_error else "unexpected_allow",
            "response_on_time": bool(insufficient_error),
        }
    )

    monotonic_increase = all(
        progressive_scores[idx] <= progressive_scores[idx + 1]
        for idx in range(len(progressive_scores) - 1)
    )

    delayed_response = any(not entry["response_on_time"] for entry in threshold_crossings)
    missed_detection = not monotonic_increase or progressive_scores[-1] <= 0.0
    incorrect_response = any(
        _response_rank(str(entry["actual_response"])) < _response_rank(str(entry["expected_response"]))
        for entry in threshold_crossings
        if entry["expected_response"] in {"warn", "freeze", "block"}
    ) or bool(drift_d.get("drift_status") != "no_drift")

    run_identity = {
        "trace_id": baseline_replay.get("trace_id"),
        "progressive_scores": progressive_scores,
        "threshold_crossings": [
            {"case_id": item["case_id"], "actual_response": item["actual_response"]}
            for item in threshold_crossings
        ],
    }

    result = {
        "validation_run_id": _stable_id("VAL09", run_identity),
        "drift_sequence": drift_sequence,
        "detection_points": detection_points,
        "control_responses": control_responses,
        "threshold_crossings": threshold_crossings,
        "missed_detection": missed_detection,
        "delayed_response": delayed_response,
        "incorrect_response": incorrect_response,
        "final_status": "PASSED" if not (missed_detection or delayed_response or incorrect_response) else "FAILED",
    }

    validate_artifact(result, "drift_response_validation_result")
    return result


__all__ = ["DriftResponseValidationError", "run_drift_response_validation"]
