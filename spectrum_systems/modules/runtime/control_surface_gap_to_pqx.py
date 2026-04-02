"""Deterministic control-surface gap to PQX triage work-item adapter (CON-032)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ControlSurfaceGapToPQXError(ValueError):
    """Raised when gap-to-PQX conversion cannot satisfy deterministic fail-closed rules."""


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _required_action_type(gap_type: str, severity: str) -> str:
    if severity == "blocker":
        return "immediate_repair"
    if gap_type == "missing_test":
        return "add_control_surface_tests"
    if gap_type == "invariant_violation":
        return "repair_invariant_enforcement"
    if gap_type in {"enforcement_missing", "obedience_missing"}:
        return "repair_control_surface_wiring"
    raise ControlSurfaceGapToPQXError(f"unsupported gap_type for PQX action mapping: {gap_type}")


def convert_gaps_to_pqx_work_items(gap_result: dict[str, Any]) -> list[dict[str, Any]]:
    schema = load_schema("control_surface_gap_result")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(gap_result), key=lambda err: list(err.absolute_path))
    if errors:
        reason = "; ".join(error.message for error in errors)
        raise ControlSurfaceGapToPQXError(f"gap_result failed schema validation: {reason}")

    if gap_result["status"] == "ok":
        if gap_result["gaps"]:
            raise ControlSurfaceGapToPQXError("gap_result status=ok cannot include gaps")
        return []

    work_items: list[dict[str, Any]] = []
    for gap in gap_result["gaps"]:
        control_surface = gap["control_surface"]
        if not isinstance(control_surface, str) or not control_surface:
            raise ControlSurfaceGapToPQXError("gap.control_surface must be non-empty string")

        action_type = _required_action_type(gap["gap_type"], gap["severity"])
        identity_payload = {
            "gap_id": gap["gap_id"],
            "control_surface": control_surface,
            "action_type": action_type,
            "source_artifact_refs": gap["source_artifact_refs"],
        }
        work_items.append(
            {
                "work_item_id": f"PQX-WORK-{_canonical_hash(identity_payload)}",
                "gap_id": gap["gap_id"],
                "control_surface": control_surface,
                "required_action_type": action_type,
                "severity": gap["severity"],
                "source_artifact_refs": sorted(set(gap["source_artifact_refs"])),
                "trace": {
                    "gap_result_id": gap_result["gap_result_id"],
                    "detected_by": gap["detected_by"],
                    "description": gap["description"],
                },
            }
        )

    deduped = {
        (
            item["gap_id"],
            item["control_surface"],
            item["required_action_type"],
            tuple(item["source_artifact_refs"]),
        ): item
        for item in work_items
    }
    ordered = sorted(deduped.values(), key=lambda item: (item["severity"], item["control_surface"], item["gap_id"]))

    if gap_result["gaps"] and not ordered:
        raise ControlSurfaceGapToPQXError("gap_result has gaps but no PQX work items were generated")

    return ordered
