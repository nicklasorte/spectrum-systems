"""Deterministic control-surface gap packet to PQX triage adapter (CON-035)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ControlSurfaceGapToPQXError(ValueError):
    """Raised when gap-to-PQX conversion cannot satisfy deterministic fail-closed rules."""


_SURFACE_IMPORTANCE = {
    "control_surface_manifest": 0,
    "control_surface_enforcement": 1,
    "control_surface_obedience": 2,
    "trust_spine_evidence_cohesion": 3,
}


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _gap_decision_rank(gap: dict[str, Any]) -> int:
    decision = "BLOCK" if bool(gap.get("blocking")) else "WARN"
    return {"BLOCK": 0, "WARN": 1, "ALLOW": 2}[decision]


def _surface_rank(gap: dict[str, Any]) -> int:
    return _SURFACE_IMPORTANCE.get(str(gap.get("surface_name") or ""), 99)


def sort_packet_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort packet gaps deterministically using governed ordering rules."""

    return sorted(gaps, key=lambda item: (_gap_decision_rank(item), _surface_rank(item), item["gap_id"]))


def convert_gap_packet_to_pqx_work_items(gap_packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a validated control_surface_gap_packet into deterministic PQX work items."""

    schema = load_schema("control_surface_gap_packet")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(gap_packet), key=lambda err: list(err.absolute_path))
    if errors:
        reason = "; ".join(error.message for error in errors)
        raise ControlSurfaceGapToPQXError(f"gap_packet failed schema validation: {reason}")

    gaps = gap_packet["gaps"]
    ordered_gaps = sort_packet_gaps(gaps)

    work_items: list[dict[str, Any]] = []
    for gap in ordered_gaps:
        identity_payload = {
            "gap_id": gap["gap_id"],
            "surface_name": gap["surface_name"],
            "gap_category": gap["gap_category"],
            "suggested_action": gap["suggested_action"],
            "source_artifact_ref": gap["source_artifact_ref"],
        }
        work_items.append(
            {
                "work_item_id": f"PQX-WORK-{_canonical_hash(identity_payload)}",
                "gap_id": gap["gap_id"],
                "surface_name": gap["surface_name"],
                "gap_category": gap["gap_category"],
                "blocking": gap["blocking"],
                "severity": gap["severity"],
                "required_action_type": gap["suggested_action"],
                "source_artifact_ref": gap["source_artifact_ref"],
                "trace": {
                    "artifact_id": gap_packet["artifact_id"],
                    "overall_decision": gap_packet["overall_decision"],
                    "observed_condition": gap["observed_condition"],
                    "expected_condition": gap["expected_condition"],
                },
            }
        )

    if gap_packet["gaps"] and not work_items:
        raise ControlSurfaceGapToPQXError("gap_packet has gaps but no PQX work items were generated")

    return work_items


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
    """Legacy control_surface_gap_result converter retained for compatibility callers."""

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
