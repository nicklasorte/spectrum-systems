"""Deterministic Review Intelligence Layer (RIL-005) read-only consumer wiring/validation.

This module consumes only RIL-004 projection artifacts and emits bounded consumer-facing
intake/view artifacts. Outputs are explicitly non-authoritative and must not be used as
policy mutation or enforcement decisions.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewConsumerWiringError(ValueError):
    """Raised when RIL-005 consumer wiring cannot prove projection-only read-only intake."""


_NON_AUTHORITATIVE_NOTICE = (
    "Read-only consumer intake/view artifact only; signals such as enforcement_block or "
    "control_escalation are non-authoritative and require independent governed decisions."
)


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ReviewConsumerWiringError(f"missing required non-empty field: {field_name}")
    return text


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewConsumerWiringError(f"{label} failed schema validation: {details}")


def _validate_projection_boundary(
    review_projection_bundle_artifact: dict[str, Any],
    roadmap_review_projection_artifact: dict[str, Any],
    control_loop_review_intake_artifact: dict[str, Any],
    readiness_review_projection_artifact: dict[str, Any],
) -> None:
    _validate_schema(
        review_projection_bundle_artifact,
        "review_projection_bundle_artifact",
        label="review_projection_bundle_artifact",
    )
    _validate_schema(
        roadmap_review_projection_artifact,
        "roadmap_review_projection_artifact",
        label="roadmap_review_projection_artifact",
    )
    _validate_schema(
        control_loop_review_intake_artifact,
        "control_loop_review_intake_artifact",
        label="control_loop_review_intake_artifact",
    )
    _validate_schema(
        readiness_review_projection_artifact,
        "readiness_review_projection_artifact",
        label="readiness_review_projection_artifact",
    )

    if review_projection_bundle_artifact["roadmap_projection_ref"] != roadmap_review_projection_artifact["roadmap_review_projection_id"]:
        raise ReviewConsumerWiringError("roadmap projection reference mismatch between bundle and intake")
    if (
        review_projection_bundle_artifact["control_loop_projection_ref"]
        != control_loop_review_intake_artifact["control_loop_review_intake_id"]
    ):
        raise ReviewConsumerWiringError("control-loop projection reference mismatch between bundle and intake")
    if review_projection_bundle_artifact["readiness_projection_ref"] != readiness_review_projection_artifact["readiness_review_projection_id"]:
        raise ReviewConsumerWiringError("readiness projection reference mismatch between bundle and intake")

    fields = ("source_review_path", "review_date", "system_scope")
    for field in fields:
        expected = review_projection_bundle_artifact[field]
        for artifact_name, artifact in (
            ("roadmap_review_projection_artifact", roadmap_review_projection_artifact),
            ("control_loop_review_intake_artifact", control_loop_review_intake_artifact),
            ("readiness_review_projection_artifact", readiness_review_projection_artifact),
        ):
            if artifact[field] != expected:
                raise ReviewConsumerWiringError(
                    f"{artifact_name} {field} mismatch: expected {expected!r}, got {artifact[field]!r}"
                )


def _build_roadmap_review_view_artifact(
    review_projection_bundle_artifact: dict[str, Any],
    roadmap_review_projection_artifact: dict[str, Any],
) -> dict[str, Any]:
    projection_items = sorted(
        roadmap_review_projection_artifact["projected_roadmap_items"],
        key=lambda item: (item["projection_item_id"], item["source_input_id"]),
    )

    roadmap_view_items: list[dict[str, Any]] = []
    for item in projection_items:
        if not item.get("trace_refs"):
            raise ReviewConsumerWiringError("roadmap projection item missing trace_refs")
        roadmap_view_items.append(
            {
                "view_item_id": deterministic_id(
                    prefix="rvi",
                    namespace="roadmap_review_view_item",
                    payload={
                        "source_roadmap_projection_ref": roadmap_review_projection_artifact["roadmap_review_projection_id"],
                        "source_projection_item_id": item["projection_item_id"],
                    },
                ),
                "source_projection_item_id": item["projection_item_id"],
                "priority": item["priority"],
                "severity": item["severity"],
                "affected_systems": item["affected_systems"],
                "rationale": item["rationale"],
                "trace_refs": item["trace_refs"],
            }
        )

    artifact = {
        "artifact_type": "roadmap_review_view_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "roadmap_review_view_id": deterministic_id(
            prefix="rrv",
            namespace="roadmap_review_view_artifact",
            payload={
                "source_roadmap_projection_ref": roadmap_review_projection_artifact["roadmap_review_projection_id"],
                "roadmap_view_item_ids": [item["view_item_id"] for item in roadmap_view_items],
            },
        ),
        "source_roadmap_projection_ref": roadmap_review_projection_artifact["roadmap_review_projection_id"],
        "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
        "source_review_path": roadmap_review_projection_artifact["source_review_path"],
        "review_date": roadmap_review_projection_artifact["review_date"],
        "system_scope": roadmap_review_projection_artifact["system_scope"],
        "roadmap_view_items": roadmap_view_items,
        "highest_priority": roadmap_review_projection_artifact["highest_priority"],
        "item_count": len(roadmap_view_items),
        "blocker_present": bool(roadmap_review_projection_artifact["blocker_present"]),
        "emitted_at": review_projection_bundle_artifact["emitted_at"],
        "non_authoritative_notice": _NON_AUTHORITATIVE_NOTICE,
        "provenance": {
            "adapter": "review_consumer_wiring",
            "consumer_surface": "roadmap_prioritization_view",
            "consumption_mode": "projection_only_read_only",
            "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
            "source_roadmap_projection_ref": roadmap_review_projection_artifact["roadmap_review_projection_id"],
        },
    }
    _validate_schema(artifact, "roadmap_review_view_artifact", label="roadmap_review_view_artifact")
    return artifact


def _build_control_loop_review_queue_record_artifact(
    review_projection_bundle_artifact: dict[str, Any],
    control_loop_review_intake_artifact: dict[str, Any],
) -> dict[str, Any]:
    projection_items = sorted(
        control_loop_review_intake_artifact["control_queue_items"],
        key=lambda item: (item["queue_item_id"], item["source_input_id"]),
    )

    queue_records: list[dict[str, Any]] = []
    for item in projection_items:
        if not item.get("trace_refs"):
            raise ReviewConsumerWiringError("control-loop projection queue item missing trace_refs")
        queue_records.append(
            {
                "queue_record_id": deterministic_id(
                    prefix="qrr",
                    namespace="control_loop_review_queue_record_item",
                    payload={
                        "source_control_loop_projection_ref": control_loop_review_intake_artifact["control_loop_review_intake_id"],
                        "source_queue_item_id": item["queue_item_id"],
                    },
                ),
                "source_queue_item_id": item["queue_item_id"],
                "intake_type": item["intake_type"],
                "priority": item["priority"],
                "severity": item["severity"],
                "blocker_related": bool(item["blocker_related"]),
                "rationale": item["rationale"],
                "trace_refs": item["trace_refs"],
            }
        )

    artifact = {
        "artifact_type": "control_loop_review_queue_record_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "control_loop_review_queue_record_id": deterministic_id(
            prefix="clr",
            namespace="control_loop_review_queue_record_artifact",
            payload={
                "source_control_loop_projection_ref": control_loop_review_intake_artifact["control_loop_review_intake_id"],
                "queue_record_ids": [item["queue_record_id"] for item in queue_records],
            },
        ),
        "source_control_loop_projection_ref": control_loop_review_intake_artifact["control_loop_review_intake_id"],
        "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
        "source_review_path": control_loop_review_intake_artifact["source_review_path"],
        "review_date": control_loop_review_intake_artifact["review_date"],
        "system_scope": control_loop_review_intake_artifact["system_scope"],
        "queue_records": queue_records,
        "escalation_present": bool(control_loop_review_intake_artifact["escalation_present"]),
        "blocker_present": bool(control_loop_review_intake_artifact["blocker_present"]),
        "item_count": len(queue_records),
        "emitted_at": review_projection_bundle_artifact["emitted_at"],
        "non_authoritative_notice": _NON_AUTHORITATIVE_NOTICE,
        "provenance": {
            "adapter": "review_consumer_wiring",
            "consumer_surface": "control_loop_intake_queue",
            "consumption_mode": "projection_only_read_only",
            "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
            "source_control_loop_projection_ref": control_loop_review_intake_artifact["control_loop_review_intake_id"],
        },
    }
    _validate_schema(artifact, "control_loop_review_queue_record_artifact", label="control_loop_review_queue_record_artifact")
    return artifact


def _build_readiness_review_dashboard_artifact(
    review_projection_bundle_artifact: dict[str, Any],
    readiness_review_projection_artifact: dict[str, Any],
) -> dict[str, Any]:
    projection_items = sorted(
        readiness_review_projection_artifact["readiness_items"],
        key=lambda item: (item["readiness_item_id"], item["source_input_id"]),
    )

    dashboard_items: list[dict[str, Any]] = []
    for item in projection_items:
        if not item.get("trace_refs"):
            raise ReviewConsumerWiringError("readiness projection item missing trace_refs")
        dashboard_items.append(
            {
                "dashboard_item_id": deterministic_id(
                    prefix="rdb",
                    namespace="readiness_review_dashboard_item",
                    payload={
                        "source_readiness_projection_ref": readiness_review_projection_artifact["readiness_review_projection_id"],
                        "source_readiness_item_id": item["readiness_item_id"],
                    },
                ),
                "source_readiness_item_id": item["readiness_item_id"],
                "input_type": item["input_type"],
                "priority": item["priority"],
                "severity": item["severity"],
                "affected_systems": item["affected_systems"],
                "rationale": item["rationale"],
                "trace_refs": item["trace_refs"],
            }
        )

    artifact = {
        "artifact_type": "readiness_review_dashboard_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "readiness_review_dashboard_id": deterministic_id(
            prefix="rda",
            namespace="readiness_review_dashboard_artifact",
            payload={
                "source_readiness_projection_ref": readiness_review_projection_artifact["readiness_review_projection_id"],
                "dashboard_item_ids": [item["dashboard_item_id"] for item in dashboard_items],
            },
        ),
        "source_readiness_projection_ref": readiness_review_projection_artifact["readiness_review_projection_id"],
        "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
        "source_review_path": readiness_review_projection_artifact["source_review_path"],
        "review_date": readiness_review_projection_artifact["review_date"],
        "system_scope": readiness_review_projection_artifact["system_scope"],
        "dashboard_items": dashboard_items,
        "blocker_present": bool(readiness_review_projection_artifact["blocker_present"]),
        "escalation_present": bool(readiness_review_projection_artifact["escalation_present"]),
        "counts_by_severity": readiness_review_projection_artifact["counts_by_severity"],
        "counts_by_type": readiness_review_projection_artifact["counts_by_type"],
        "item_count": len(dashboard_items),
        "emitted_at": review_projection_bundle_artifact["emitted_at"],
        "non_authoritative_notice": _NON_AUTHORITATIVE_NOTICE,
        "provenance": {
            "adapter": "review_consumer_wiring",
            "consumer_surface": "readiness_dashboard",
            "consumption_mode": "projection_only_read_only",
            "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
            "source_readiness_projection_ref": readiness_review_projection_artifact["readiness_review_projection_id"],
        },
    }
    _validate_schema(artifact, "readiness_review_dashboard_artifact", label="readiness_review_dashboard_artifact")
    return artifact


def _build_review_consumption_validation_artifact(
    review_projection_bundle_artifact: dict[str, Any],
) -> dict[str, Any]:
    findings = [
        {
            "finding_code": "RIL005-PROJECTION-ONLY-BOUNDARY",
            "status": "pass",
            "detail": "Consumer wiring accepted only RIL-04 projection bundle and projection artifact contracts.",
        },
        {
            "finding_code": "RIL005-READ-ONLY-CONSUMPTION",
            "status": "pass",
            "detail": "Consumer outputs were derived via field passthrough without mutation or enforcement semantics.",
        },
        {
            "finding_code": "RIL005-NON-AUTHORITATIVE",
            "status": "pass",
            "detail": "Signals including enforcement_block/control_escalation are treated as non-authoritative downstream intake signals.",
        },
    ]

    artifact = {
        "artifact_type": "review_consumption_validation_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "review_consumption_validation_id": deterministic_id(
            prefix="rcv",
            namespace="review_consumption_validation_artifact",
            payload={
                "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
                "source_review_path": review_projection_bundle_artifact["source_review_path"],
            },
        ),
        "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
        "source_review_path": review_projection_bundle_artifact["source_review_path"],
        "review_date": review_projection_bundle_artifact["review_date"],
        "system_scope": review_projection_bundle_artifact["system_scope"],
        "intake_boundary_valid": True,
        "read_only_consumption_valid": True,
        "raw_review_access_detected": False,
        "earlier_ril_artifact_access_detected": False,
        "validation_findings": findings,
        "emitted_at": review_projection_bundle_artifact["emitted_at"],
        "non_authoritative_notice": _NON_AUTHORITATIVE_NOTICE,
        "provenance": {
            "adapter": "review_consumer_wiring",
            "consumer_surface": "projection_boundary_validation",
            "consumption_mode": "projection_only_read_only",
            "source_review_projection_bundle_ref": review_projection_bundle_artifact["review_projection_bundle_id"],
        },
    }
    _validate_schema(artifact, "review_consumption_validation_artifact", label="review_consumption_validation_artifact")
    return artifact


def build_review_consumer_outputs(
    review_projection_bundle_artifact: dict[str, Any],
    roadmap_review_projection_artifact: dict[str, Any],
    control_loop_review_intake_artifact: dict[str, Any],
    readiness_review_projection_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Build deterministic RIL-005 read-only consumer outputs from RIL-004 projection inputs only."""

    _validate_projection_boundary(
        review_projection_bundle_artifact,
        roadmap_review_projection_artifact,
        control_loop_review_intake_artifact,
        readiness_review_projection_artifact,
    )

    source_bundle_ref = _require_non_empty(
        review_projection_bundle_artifact.get("review_projection_bundle_id"),
        "review_projection_bundle_id",
    )

    roadmap_view = _build_roadmap_review_view_artifact(
        review_projection_bundle_artifact,
        roadmap_review_projection_artifact,
    )
    control_loop_queue_record = _build_control_loop_review_queue_record_artifact(
        review_projection_bundle_artifact,
        control_loop_review_intake_artifact,
    )
    readiness_dashboard = _build_readiness_review_dashboard_artifact(
        review_projection_bundle_artifact,
        readiness_review_projection_artifact,
    )
    consumption_validation = _build_review_consumption_validation_artifact(review_projection_bundle_artifact)

    bundle = {
        "artifact_type": "review_consumer_output_bundle_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "review_consumer_output_bundle_id": deterministic_id(
            prefix="rco",
            namespace="review_consumer_output_bundle_artifact",
            payload={
                "source_review_projection_bundle_ref": source_bundle_ref,
                "roadmap_review_view_ref": roadmap_view["roadmap_review_view_id"],
                "control_loop_review_queue_record_ref": control_loop_queue_record[
                    "control_loop_review_queue_record_id"
                ],
                "readiness_review_dashboard_ref": readiness_dashboard["readiness_review_dashboard_id"],
                "review_consumption_validation_ref": consumption_validation["review_consumption_validation_id"],
            },
        ),
        "source_review_projection_bundle_ref": source_bundle_ref,
        "source_review_path": review_projection_bundle_artifact["source_review_path"],
        "review_date": review_projection_bundle_artifact["review_date"],
        "system_scope": review_projection_bundle_artifact["system_scope"],
        "roadmap_review_view_ref": roadmap_view["roadmap_review_view_id"],
        "control_loop_review_queue_record_ref": control_loop_queue_record["control_loop_review_queue_record_id"],
        "readiness_review_dashboard_ref": readiness_dashboard["readiness_review_dashboard_id"],
        "review_consumption_validation_ref": consumption_validation["review_consumption_validation_id"],
        "blocker_present": bool(review_projection_bundle_artifact["blocker_present"]),
        "escalation_present": bool(review_projection_bundle_artifact["escalation_present"]),
        "emitted_at": review_projection_bundle_artifact["emitted_at"],
        "non_authoritative_notice": _NON_AUTHORITATIVE_NOTICE,
        "provenance": {
            "adapter": "review_consumer_wiring",
            "consumer_surface": "consumer_output_bundle",
            "consumption_mode": "projection_only_read_only",
            "source_review_projection_bundle_ref": source_bundle_ref,
            "source_consumer_output_ids": {
                "roadmap_review_view_id": roadmap_view["roadmap_review_view_id"],
                "control_loop_review_queue_record_id": control_loop_queue_record[
                    "control_loop_review_queue_record_id"
                ],
                "readiness_review_dashboard_id": readiness_dashboard["readiness_review_dashboard_id"],
                "review_consumption_validation_id": consumption_validation[
                    "review_consumption_validation_id"
                ],
            },
        },
        "roadmap_review_view_artifact": roadmap_view,
        "control_loop_review_queue_record_artifact": control_loop_queue_record,
        "readiness_review_dashboard_artifact": readiness_dashboard,
        "review_consumption_validation_artifact": consumption_validation,
    }

    _validate_schema(bundle, "review_consumer_output_bundle_artifact", label="review_consumer_output_bundle_artifact")
    return bundle


__all__ = ["ReviewConsumerWiringError", "build_review_consumer_outputs"]
