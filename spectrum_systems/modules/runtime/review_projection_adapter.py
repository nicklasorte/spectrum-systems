"""Deterministic Review Intelligence Layer (RIL-004) read-only projection adapters."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewProjectionAdapterError(ValueError):
    """Raised when review_integration_packet_artifact cannot be projected fail-closed."""


_ALLOWED_PRIORITIES = {"P0", "P1", "P2", "monitor"}
_ALLOWED_SEVERITIES = {"critical", "high", "medium"}
_ALLOWED_INPUT_TYPES = {
    "blocker_intake",
    "escalation_intake",
    "roadmap_priority_intake",
    "drift_watch_intake",
    "recovery_followup_intake",
    "governance_attention_intake",
}


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ReviewProjectionAdapterError(f"missing required non-empty field: {field_name}")
    return text


def _validate_source_artifact(review_integration_packet_artifact: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema("review_integration_packet_artifact"))
    errors = sorted(validator.iter_errors(review_integration_packet_artifact), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewProjectionAdapterError(f"review_integration_packet_artifact failed schema validation: {details}")


def _validate_input_item(item: dict[str, Any], *, expected_channel: str) -> None:
    _require_non_empty(item.get("input_id"), "input_id")
    if item.get("input_channel") != expected_channel:
        raise ReviewProjectionAdapterError(
            f"input {item.get('input_id')} channel mismatch: expected {expected_channel}, got {item.get('input_channel')}"
        )

    input_type = _require_non_empty(item.get("input_type"), "input_type")
    if input_type not in _ALLOWED_INPUT_TYPES:
        raise ReviewProjectionAdapterError(f"unsupported input_type: {input_type}")

    priority = _require_non_empty(item.get("priority"), "priority")
    if priority not in _ALLOWED_PRIORITIES:
        raise ReviewProjectionAdapterError(f"unsupported priority: {priority}")

    severity = _require_non_empty(item.get("severity"), "severity")
    if severity not in _ALLOWED_SEVERITIES:
        raise ReviewProjectionAdapterError(f"unsupported severity: {severity}")

    affected_systems = item.get("affected_systems")
    if not isinstance(affected_systems, list) or not affected_systems:
        raise ReviewProjectionAdapterError(f"input {item.get('input_id')} missing affected_systems")

    trace_refs = item.get("trace_refs")
    if not isinstance(trace_refs, list) or not trace_refs:
        raise ReviewProjectionAdapterError(f"input {item.get('input_id')} missing trace_refs")


def _validate_counts(packet: dict[str, Any], *, control_loop_inputs: list[dict[str, Any]], roadmap_inputs: list[dict[str, Any]], readiness_inputs: list[dict[str, Any]]) -> None:
    counts_by_channel = packet.get("counts_by_channel")
    if not isinstance(counts_by_channel, dict):
        raise ReviewProjectionAdapterError("counts_by_channel must be an object")

    expected_channel_counts = {
        "control_loop": len(control_loop_inputs),
        "roadmap": len(roadmap_inputs),
        "readiness": len(readiness_inputs),
    }
    if counts_by_channel != expected_channel_counts:
        raise ReviewProjectionAdapterError("counts_by_channel does not match channel input lengths")

    counts_by_type = packet.get("counts_by_type")
    if not isinstance(counts_by_type, dict) or not counts_by_type:
        raise ReviewProjectionAdapterError("counts_by_type must be a non-empty object")

    derived_counts_by_type: dict[str, int] = {}
    for item in (*control_loop_inputs, *roadmap_inputs, *readiness_inputs):
        input_type = item["input_type"]
        derived_counts_by_type[input_type] = derived_counts_by_type.get(input_type, 0) + 1

    if set(counts_by_type.keys()) != set(derived_counts_by_type.keys()):
        raise ReviewProjectionAdapterError("counts_by_type keys do not match projected input types")

    if counts_by_type != derived_counts_by_type:
        raise ReviewProjectionAdapterError("counts_by_type does not match projected input type counts")


def _sorted_inputs(packet: dict[str, Any], *, channel: str) -> list[dict[str, Any]]:
    raw_inputs = packet.get(f"{channel}_inputs")
    if not isinstance(raw_inputs, list):
        raise ReviewProjectionAdapterError(f"{channel}_inputs must be an array")

    sorted_inputs = sorted(
        raw_inputs,
        key=lambda value: (
            str(value.get("source_signal_id", "")),
            str(value.get("input_type", "")),
            str(value.get("input_id", "")),
        ),
    )
    for item in sorted_inputs:
        if not isinstance(item, dict):
            raise ReviewProjectionAdapterError(f"{channel}_inputs entry must be an object")
        _validate_input_item(item, expected_channel=channel)
    return sorted_inputs


def _projection_trace(packet: dict[str, Any], *, projection_type: str) -> dict[str, Any]:
    provenance = packet.get("provenance")
    if not isinstance(provenance, dict):
        raise ReviewProjectionAdapterError("source packet provenance missing")

    source_review_hash = _require_non_empty(provenance.get("source_review_hash"), "provenance.source_review_hash")
    source_action_tracker_hash = _require_non_empty(
        provenance.get("source_action_tracker_hash"), "provenance.source_action_tracker_hash"
    )

    return {
        "adapter": "review_projection_adapter",
        "projection_type": projection_type,
        "deterministic_hash_basis": "canonical-json-sha256",
        "source_review_control_signal_id": _require_non_empty(
            packet.get("source_review_control_signal_ref"), "source_review_control_signal_ref"
        ),
        "source_review_hash": source_review_hash,
        "source_action_tracker_hash": source_action_tracker_hash,
        "source_packet_id": _require_non_empty(packet.get("review_integration_packet_id"), "review_integration_packet_id"),
    }


def _roadmap_projection(packet: dict[str, Any], roadmap_inputs: list[dict[str, Any]]) -> dict[str, Any]:
    projected_items: list[dict[str, Any]] = []
    for item in roadmap_inputs:
        seed = {
            "source_review_integration_packet_ref": packet["review_integration_packet_id"],
            "source_input_id": item["input_id"],
            "projection": "roadmap",
        }
        projected_items.append(
            {
                "projection_item_id": deterministic_id(prefix="rpi", namespace="roadmap_projection_item", payload=seed),
                "source_input_id": item["input_id"],
                "priority": item["priority"],
                "severity": item["severity"],
                "affected_systems": item["affected_systems"],
                "rationale": item["rationale"],
                "trace_refs": item["trace_refs"],
            }
        )

    projection = {
        "artifact_type": "roadmap_review_projection_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "roadmap_review_projection_id": deterministic_id(
            prefix="rrp",
            namespace="roadmap_review_projection_artifact",
            payload={
                "source_review_integration_packet_ref": packet["review_integration_packet_id"],
                "projection_item_ids": [item["projection_item_id"] for item in projected_items],
            },
        ),
        "source_review_integration_packet_ref": packet["review_integration_packet_id"],
        "source_review_path": packet["source_review_path"],
        "review_date": packet["review_date"],
        "system_scope": packet["system_scope"],
        "projected_roadmap_items": projected_items,
        "highest_priority": packet["highest_priority"],
        "item_count": len(projected_items),
        "blocker_present": bool(packet.get("blocker_present")),
        "emitted_at": packet["emitted_at"],
        "provenance": _projection_trace(packet, projection_type="roadmap"),
    }

    validator = Draft202012Validator(load_schema("roadmap_review_projection_artifact"))
    errors = sorted(validator.iter_errors(projection), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewProjectionAdapterError(f"roadmap_review_projection_artifact failed schema validation: {details}")

    return projection


def _control_loop_projection(packet: dict[str, Any], control_loop_inputs: list[dict[str, Any]]) -> dict[str, Any]:
    queue_items: list[dict[str, Any]] = []
    for item in control_loop_inputs:
        seed = {
            "source_review_integration_packet_ref": packet["review_integration_packet_id"],
            "source_input_id": item["input_id"],
            "projection": "control_loop",
        }
        queue_items.append(
            {
                "queue_item_id": deterministic_id(prefix="rqi", namespace="control_loop_review_queue_item", payload=seed),
                "source_input_id": item["input_id"],
                "intake_type": item["input_type"],
                "priority": item["priority"],
                "severity": item["severity"],
                "blocker_related": item["input_type"] == "blocker_intake" or item["priority"] == "P0",
                "rationale": item["rationale"],
                "trace_refs": item["trace_refs"],
            }
        )

    projection = {
        "artifact_type": "control_loop_review_intake_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "control_loop_review_intake_id": deterministic_id(
            prefix="cri",
            namespace="control_loop_review_intake_artifact",
            payload={
                "source_review_integration_packet_ref": packet["review_integration_packet_id"],
                "queue_item_ids": [item["queue_item_id"] for item in queue_items],
            },
        ),
        "source_review_integration_packet_ref": packet["review_integration_packet_id"],
        "source_review_path": packet["source_review_path"],
        "review_date": packet["review_date"],
        "system_scope": packet["system_scope"],
        "control_queue_items": queue_items,
        "escalation_present": bool(packet.get("escalation_present")),
        "blocker_present": bool(packet.get("blocker_present")),
        "item_count": len(queue_items),
        "emitted_at": packet["emitted_at"],
        "provenance": _projection_trace(packet, projection_type="control_loop"),
    }

    validator = Draft202012Validator(load_schema("control_loop_review_intake_artifact"))
    errors = sorted(validator.iter_errors(projection), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewProjectionAdapterError(f"control_loop_review_intake_artifact failed schema validation: {details}")

    return projection


def _readiness_projection(packet: dict[str, Any], readiness_inputs: list[dict[str, Any]]) -> dict[str, Any]:
    readiness_items: list[dict[str, Any]] = []
    counts_by_severity = {"critical": 0, "high": 0, "medium": 0}
    counts_by_type: dict[str, int] = {}

    for item in readiness_inputs:
        seed = {
            "source_review_integration_packet_ref": packet["review_integration_packet_id"],
            "source_input_id": item["input_id"],
            "projection": "readiness",
        }
        readiness_items.append(
            {
                "readiness_item_id": deterministic_id(prefix="rdi", namespace="readiness_projection_item", payload=seed),
                "source_input_id": item["input_id"],
                "input_type": item["input_type"],
                "priority": item["priority"],
                "severity": item["severity"],
                "affected_systems": item["affected_systems"],
                "rationale": item["rationale"],
                "trace_refs": item["trace_refs"],
            }
        )
        counts_by_severity[item["severity"]] += 1
        counts_by_type[item["input_type"]] = counts_by_type.get(item["input_type"], 0) + 1

    projection = {
        "artifact_type": "readiness_review_projection_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "readiness_review_projection_id": deterministic_id(
            prefix="rdp",
            namespace="readiness_review_projection_artifact",
            payload={
                "source_review_integration_packet_ref": packet["review_integration_packet_id"],
                "readiness_item_ids": [item["readiness_item_id"] for item in readiness_items],
            },
        ),
        "source_review_integration_packet_ref": packet["review_integration_packet_id"],
        "source_review_path": packet["source_review_path"],
        "review_date": packet["review_date"],
        "system_scope": packet["system_scope"],
        "readiness_items": readiness_items,
        "blocker_present": bool(packet.get("blocker_present")),
        "escalation_present": bool(packet.get("escalation_present")),
        "counts_by_severity": counts_by_severity,
        "counts_by_type": counts_by_type,
        "item_count": len(readiness_items),
        "emitted_at": packet["emitted_at"],
        "provenance": _projection_trace(packet, projection_type="readiness"),
    }

    validator = Draft202012Validator(load_schema("readiness_review_projection_artifact"))
    errors = sorted(validator.iter_errors(projection), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewProjectionAdapterError(f"readiness_review_projection_artifact failed schema validation: {details}")

    return projection


def build_review_projection_bundle(review_integration_packet_artifact: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic read-only RIL-004 projections from a bounded RIL-003 integration packet."""

    _validate_source_artifact(review_integration_packet_artifact)

    source_packet_id = _require_non_empty(
        review_integration_packet_artifact.get("review_integration_packet_id"), "review_integration_packet_id"
    )

    control_loop_inputs = _sorted_inputs(review_integration_packet_artifact, channel="control_loop")
    roadmap_inputs = _sorted_inputs(review_integration_packet_artifact, channel="roadmap")
    readiness_inputs = _sorted_inputs(review_integration_packet_artifact, channel="readiness")

    _validate_counts(
        review_integration_packet_artifact,
        control_loop_inputs=control_loop_inputs,
        roadmap_inputs=roadmap_inputs,
        readiness_inputs=readiness_inputs,
    )

    source_review_path = _require_non_empty(review_integration_packet_artifact.get("source_review_path"), "source_review_path")
    review_date = _require_non_empty(review_integration_packet_artifact.get("review_date"), "review_date")
    system_scope = _require_non_empty(review_integration_packet_artifact.get("system_scope"), "system_scope")
    highest_priority = _require_non_empty(review_integration_packet_artifact.get("highest_priority"), "highest_priority")
    if highest_priority not in _ALLOWED_PRIORITIES:
        raise ReviewProjectionAdapterError(f"unsupported highest_priority: {highest_priority}")

    roadmap_projection = _roadmap_projection(review_integration_packet_artifact, roadmap_inputs)
    control_loop_projection = _control_loop_projection(review_integration_packet_artifact, control_loop_inputs)
    readiness_projection = _readiness_projection(review_integration_packet_artifact, readiness_inputs)

    bundle = {
        "artifact_type": "review_projection_bundle_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.1.0",
        "review_projection_bundle_id": deterministic_id(
            prefix="rpb",
            namespace="review_projection_bundle_artifact",
            payload={
                "source_review_integration_packet_ref": source_packet_id,
                "roadmap_projection_ref": roadmap_projection["roadmap_review_projection_id"],
                "control_loop_projection_ref": control_loop_projection["control_loop_review_intake_id"],
                "readiness_projection_ref": readiness_projection["readiness_review_projection_id"],
            },
        ),
        "source_review_integration_packet_ref": source_packet_id,
        "source_review_path": source_review_path,
        "review_date": review_date,
        "system_scope": system_scope,
        "roadmap_projection_ref": roadmap_projection["roadmap_review_projection_id"],
        "control_loop_projection_ref": control_loop_projection["control_loop_review_intake_id"],
        "readiness_projection_ref": readiness_projection["readiness_review_projection_id"],
        "roadmap_projection": roadmap_projection,
        "control_loop_projection": control_loop_projection,
        "readiness_projection": readiness_projection,
        "blocker_present": bool(review_integration_packet_artifact.get("blocker_present")),
        "escalation_present": bool(review_integration_packet_artifact.get("escalation_present")),
        "emitted_at": _require_non_empty(review_integration_packet_artifact.get("emitted_at"), "emitted_at"),
        "provenance": {
            **_projection_trace(review_integration_packet_artifact, projection_type="bundle"),
            "source_projection_ids": {
                "roadmap_review_projection_id": roadmap_projection["roadmap_review_projection_id"],
                "control_loop_review_intake_id": control_loop_projection["control_loop_review_intake_id"],
                "readiness_review_projection_id": readiness_projection["readiness_review_projection_id"],
            },
        },
    }

    validator = Draft202012Validator(load_schema("review_projection_bundle_artifact"))
    errors = sorted(validator.iter_errors(bundle), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewProjectionAdapterError(f"review_projection_bundle_artifact failed schema validation: {details}")

    return bundle


__all__ = ["ReviewProjectionAdapterError", "build_review_projection_bundle"]
