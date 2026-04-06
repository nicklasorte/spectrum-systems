"""Deterministic Review Intelligence Layer (RIL-003) signal consumption and bounded routing."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewSignalConsumptionError(ValueError):
    """Raised when review_control_signal_artifact cannot be consumed fail-closed."""


_ALLOWED_SIGNAL_CLASSES = {
    "control_escalation",
    "enforcement_block",
    "roadmap_priority",
    "drift_watch",
    "recovery_followup",
    "governance_attention",
}
_ALLOWED_CHANNELS = ("control_loop", "roadmap", "readiness")
_ALLOWED_INPUT_TYPES = (
    "blocker_intake",
    "escalation_intake",
    "roadmap_priority_intake",
    "drift_watch_intake",
    "recovery_followup_intake",
    "governance_attention_intake",
)
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "monitor": 3}


def _validate_source_artifact(review_control_signal_artifact: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema("review_control_signal_artifact"))
    errors = sorted(validator.iter_errors(review_control_signal_artifact), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewSignalConsumptionError(f"review_control_signal_artifact failed schema validation: {details}")


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ReviewSignalConsumptionError(f"missing required non-empty field: {field_name}")
    return text


def _validate_trace_refs(signal: dict[str, Any]) -> None:
    trace_refs = signal.get("trace_refs")
    if not isinstance(trace_refs, list) or not trace_refs:
        raise ReviewSignalConsumptionError(f"signal {signal.get('signal_id')} missing trace_refs")
    for trace in trace_refs:
        if not isinstance(trace, dict):
            raise ReviewSignalConsumptionError(f"signal {signal.get('signal_id')} trace_refs entry must be object")
        _require_non_empty(trace.get("source_path"), "trace_refs.source_path")
        if not isinstance(trace.get("line_number"), int):
            raise ReviewSignalConsumptionError(f"signal {signal.get('signal_id')} missing integer trace_refs.line_number")
        _require_non_empty(trace.get("source_excerpt"), "trace_refs.source_excerpt")


def _routing_for_signal(signal: dict[str, Any]) -> list[tuple[str, str]]:
    signal_class = str(signal.get("signal_class"))
    severity = str(signal.get("severity"))
    priority = str(signal.get("signal_priority"))

    if signal_class == "enforcement_block":
        return [("control_loop", "blocker_intake"), ("readiness", "blocker_intake")]

    if signal_class == "control_escalation":
        return [("control_loop", "escalation_intake"), ("readiness", "escalation_intake")]

    if signal_class == "roadmap_priority":
        return [("roadmap", "roadmap_priority_intake")]

    if signal_class == "drift_watch":
        return [("readiness", "drift_watch_intake")]

    if signal_class == "recovery_followup":
        return [("roadmap", "recovery_followup_intake"), ("readiness", "recovery_followup_intake")]

    if signal_class == "governance_attention":
        routes: list[tuple[str, str]] = [("readiness", "governance_attention_intake")]
        if severity == "critical" or priority in {"P0", "P1"}:
            routes.append(("control_loop", "governance_attention_intake"))
        return routes

    raise ReviewSignalConsumptionError(f"unsupported signal class: {signal_class}")


def _build_input_item(signal: dict[str, Any], *, channel: str, input_type: str) -> dict[str, Any]:
    if channel not in _ALLOWED_CHANNELS:
        raise ReviewSignalConsumptionError(f"unsupported input channel: {channel}")
    if input_type not in _ALLOWED_INPUT_TYPES:
        raise ReviewSignalConsumptionError(f"unsupported input type: {input_type}")

    source_signal_id = _require_non_empty(signal.get("signal_id"), "classified_signals.signal_id")
    priority = _require_non_empty(signal.get("signal_priority"), "classified_signals.signal_priority")
    severity = _require_non_empty(signal.get("severity"), "classified_signals.severity")
    rationale = _require_non_empty(signal.get("rationale"), "classified_signals.rationale")

    if priority not in _PRIORITY_RANK:
        raise ReviewSignalConsumptionError(f"unsupported signal priority: {priority}")
    if severity not in {"critical", "high", "medium"}:
        raise ReviewSignalConsumptionError(f"unsupported signal severity: {severity}")

    affected_systems = signal.get("affected_systems")
    if not isinstance(affected_systems, list) or not affected_systems:
        raise ReviewSignalConsumptionError(f"signal {source_signal_id} missing affected_systems")
    cleaned_affected = sorted({_require_non_empty(value, "classified_signals.affected_systems") for value in affected_systems})

    _validate_trace_refs(signal)

    input_seed = {
        "source_signal_id": source_signal_id,
        "input_channel": channel,
        "input_type": input_type,
    }
    return {
        "input_id": deterministic_id(prefix="rii", namespace="review_integration_input", payload=input_seed),
        "source_signal_id": source_signal_id,
        "input_channel": channel,
        "input_type": input_type,
        "priority": priority,
        "severity": severity,
        "affected_systems": cleaned_affected,
        "rationale": rationale,
        "trace_refs": signal["trace_refs"],
    }


def build_review_integration_packet(review_control_signal_artifact: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic bounded integration packet from RIL-002 control signals."""
    _validate_source_artifact(review_control_signal_artifact)

    source_review_control_signal_ref = _require_non_empty(
        review_control_signal_artifact.get("review_control_signal_id"), "review_control_signal_id"
    )
    source_review_path = _require_non_empty(review_control_signal_artifact.get("source_review_path"), "source_review_path")
    source_action_tracker_path = _require_non_empty(
        review_control_signal_artifact.get("source_action_tracker_path"), "source_action_tracker_path"
    )
    review_date = _require_non_empty(review_control_signal_artifact.get("review_date"), "review_date")
    system_scope = _require_non_empty(review_control_signal_artifact.get("system_scope"), "system_scope")

    classified_signals = review_control_signal_artifact.get("classified_signals")
    if not isinstance(classified_signals, list) or not classified_signals:
        raise ReviewSignalConsumptionError("classified_signals must be a non-empty array")

    sorted_signals = sorted(
        classified_signals,
        key=lambda signal: (
            str(signal.get("source_item_id", "")),
            str(signal.get("signal_class", "")),
            str(signal.get("signal_id", "")),
        ),
    )

    control_loop_inputs: list[dict[str, Any]] = []
    roadmap_inputs: list[dict[str, Any]] = []
    readiness_inputs: list[dict[str, Any]] = []

    counts_by_type = {input_type: 0 for input_type in _ALLOWED_INPUT_TYPES}
    highest_priority = "monitor"

    for signal in sorted_signals:
        signal_class = _require_non_empty(signal.get("signal_class"), "classified_signals.signal_class")
        if signal_class not in _ALLOWED_SIGNAL_CLASSES:
            raise ReviewSignalConsumptionError(f"unsupported classified signal class: {signal_class}")

        routes = _routing_for_signal(signal)
        for channel, input_type in routes:
            item = _build_input_item(signal, channel=channel, input_type=input_type)
            counts_by_type[input_type] += 1
            if _PRIORITY_RANK[item["priority"]] < _PRIORITY_RANK[highest_priority]:
                highest_priority = item["priority"]

            if channel == "control_loop":
                control_loop_inputs.append(item)
            elif channel == "roadmap":
                roadmap_inputs.append(item)
            elif channel == "readiness":
                readiness_inputs.append(item)
            else:
                raise ReviewSignalConsumptionError(f"unsupported channel routing result: {channel}")

    for collection in (control_loop_inputs, roadmap_inputs, readiness_inputs):
        collection.sort(key=lambda value: (value["source_signal_id"], value["input_channel"], value["input_type"], value["input_id"]))

    counts_by_channel = {
        "control_loop": len(control_loop_inputs),
        "roadmap": len(roadmap_inputs),
        "readiness": len(readiness_inputs),
    }

    packet_seed = {
        "source_review_control_signal_ref": source_review_control_signal_ref,
        "review_date": review_date,
        "control_loop_input_ids": [item["input_id"] for item in control_loop_inputs],
        "roadmap_input_ids": [item["input_id"] for item in roadmap_inputs],
        "readiness_input_ids": [item["input_id"] for item in readiness_inputs],
    }

    output = {
        "artifact_type": "review_integration_packet_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "review_integration_packet_id": deterministic_id(
            prefix="rip",
            namespace="review_integration_packet_artifact",
            payload=packet_seed,
        ),
        "source_review_control_signal_ref": source_review_control_signal_ref,
        "source_review_path": source_review_path,
        "source_action_tracker_path": source_action_tracker_path,
        "review_date": review_date,
        "system_scope": system_scope,
        "overall_verdict": review_control_signal_artifact.get("overall_verdict"),
        "control_loop_inputs": control_loop_inputs,
        "roadmap_inputs": roadmap_inputs,
        "readiness_inputs": readiness_inputs,
        "blocker_present": bool(review_control_signal_artifact.get("blocker_present")),
        "escalation_present": bool(review_control_signal_artifact.get("escalation_present")),
        "highest_priority": highest_priority,
        "counts_by_channel": counts_by_channel,
        "counts_by_type": counts_by_type,
        "emitted_at": _require_non_empty(review_control_signal_artifact.get("emitted_at"), "emitted_at"),
        "provenance": {
            "consumer": "review_signal_consumer",
            "deterministic_hash_basis": "canonical-json-sha256",
            "source_review_control_signal_id": source_review_control_signal_ref,
            "source_review_hash": review_control_signal_artifact["provenance"]["source_review_hash"],
            "source_action_tracker_hash": review_control_signal_artifact["provenance"]["source_action_tracker_hash"],
            "routing_rules_version": "ril-003-v1",
        },
    }

    validator = Draft202012Validator(load_schema("review_integration_packet_artifact"))
    errors = sorted(validator.iter_errors(output), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewSignalConsumptionError(f"review_integration_packet_artifact failed schema validation: {details}")

    return output


__all__ = ["ReviewSignalConsumptionError", "build_review_integration_packet"]
