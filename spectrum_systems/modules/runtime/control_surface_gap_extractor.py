"""Deterministic fail-closed control-surface gap extraction (CON-032)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ControlSurfaceGapExtractionError(ValueError):
    """Raised when control-surface gap extraction cannot be completed safely."""


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        reason = "; ".join(error.message for error in errors)
        raise ControlSurfaceGapExtractionError(f"{label} failed schema validation ({schema_name}): {reason}")


def _require_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ControlSurfaceGapExtractionError(f"{field_name} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ControlSurfaceGapExtractionError(f"{field_name} entries must be non-empty strings")
    return list(value)


def _collect_manifest_surfaces(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise ControlSurfaceGapExtractionError("control_surface_manifest.surfaces must be a non-empty list")

    mapped: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        if not isinstance(surface, dict):
            raise ControlSurfaceGapExtractionError("control_surface_manifest surface entries must be objects")
        surface_id = surface.get("surface_id")
        if not isinstance(surface_id, str) or not surface_id:
            raise ControlSurfaceGapExtractionError("control_surface_manifest surface_id must be non-empty string")
        mapped[surface_id] = surface
    return mapped


def _build_gap(
    *,
    control_surface: str,
    gap_type: str,
    severity: str,
    description: str,
    source_artifact_refs: list[str],
    detected_by: str,
) -> dict[str, Any]:
    normalized_refs = sorted(set(source_artifact_refs))
    if not normalized_refs:
        raise ControlSurfaceGapExtractionError("source_artifact_refs must not be empty")

    key = {
        "control_surface": control_surface,
        "gap_type": gap_type,
        "severity": severity,
        "description": description,
        "source_artifact_refs": normalized_refs,
        "detected_by": detected_by,
    }
    gap_id = f"GAP-{_canonical_hash(key)}"
    return {
        "gap_id": gap_id,
        **key,
    }


def _require_surface_mapping(surface_id: str, mapped_surfaces: dict[str, dict[str, Any]]) -> None:
    if surface_id not in mapped_surfaces:
        raise ControlSurfaceGapExtractionError(f"control surface mapping missing for '{surface_id}'")


def extract_control_surface_gaps(
    manifest: dict[str, Any],
    enforcement_result: dict[str, Any],
    obedience_result: dict[str, Any],
) -> dict[str, Any]:
    """Extract deterministic machine-readable gaps from control-surface artifacts."""
    _validate(manifest, "control_surface_manifest", label="control_surface_manifest")
    _validate(enforcement_result, "control_surface_enforcement_result", label="control_surface_enforcement_result")
    _validate(obedience_result, "control_surface_obedience_result", label="control_surface_obedience_result")

    mapped_surfaces = _collect_manifest_surfaces(manifest)
    manifest_ref = str(obedience_result.get("manifest_ref") or enforcement_result.get("manifest_ref") or "")
    enforcement_ref = str(obedience_result.get("enforcement_result_ref") or "")
    obedience_ref = str(obedience_result.get("trace", {}).get("evidence_refs", {}).get("promotion_decision_ref") or "")

    gaps: list[dict[str, Any]] = []

    missing_tests = _require_string_list(
        manifest.get("gap_signals", {}).get("surfaces_missing_targeted_tests", []),
        field_name="control_surface_manifest.gap_signals.surfaces_missing_targeted_tests",
    )
    for surface_id in sorted(set(missing_tests)):
        _require_surface_mapping(surface_id, mapped_surfaces)
        gaps.append(
            _build_gap(
                control_surface=surface_id,
                gap_type="missing_test",
                severity="medium",
                description=f"Manifest reports missing targeted tests for control surface {surface_id}.",
                source_artifact_refs=[manifest_ref] if manifest_ref else ["control_surface_manifest"],
                detected_by="manifest",
            )
        )

    missing_required_surfaces = _require_string_list(
        enforcement_result.get("missing_required_surfaces", []),
        field_name="control_surface_enforcement_result.missing_required_surfaces",
    )
    for surface_id in sorted(set(missing_required_surfaces)):
        _require_surface_mapping(surface_id, mapped_surfaces)
        gaps.append(
            _build_gap(
                control_surface=surface_id,
                gap_type="enforcement_missing",
                severity="blocker",
                description=f"Enforcement reports required control surface missing: {surface_id}.",
                source_artifact_refs=[enforcement_ref] if enforcement_ref else ["control_surface_enforcement_result"],
                detected_by="enforcement",
            )
        )

    invariant_violations = _require_string_list(
        enforcement_result.get("surfaces_missing_invariants", []),
        field_name="control_surface_enforcement_result.surfaces_missing_invariants",
    )
    for surface_id in sorted(set(invariant_violations)):
        _require_surface_mapping(surface_id, mapped_surfaces)
        gaps.append(
            _build_gap(
                control_surface=surface_id,
                gap_type="invariant_violation",
                severity="high",
                description=f"Enforcement reports missing invariant coverage for {surface_id}.",
                source_artifact_refs=[enforcement_ref] if enforcement_ref else ["control_surface_enforcement_result"],
                detected_by="enforcement",
            )
        )

    missing_obedience_evidence = _require_string_list(
        obedience_result.get("missing_obedience_evidence", []),
        field_name="control_surface_obedience_result.missing_obedience_evidence",
    )
    for evidence_gap in sorted(set(missing_obedience_evidence)):
        surface_id = evidence_gap.split(":", 1)[0]
        _require_surface_mapping(surface_id, mapped_surfaces)
        gaps.append(
            _build_gap(
                control_surface=surface_id,
                gap_type="obedience_missing",
                severity="high",
                description=f"Obedience evidence missing for {evidence_gap}.",
                source_artifact_refs=[obedience_ref] if obedience_ref else ["control_surface_obedience_result"],
                detected_by="obedience",
            )
        )

    surface_results = obedience_result.get("surface_results")
    if not isinstance(surface_results, list):
        raise ControlSurfaceGapExtractionError("control_surface_obedience_result.surface_results must be a list")
    for row in surface_results:
        if not isinstance(row, dict):
            raise ControlSurfaceGapExtractionError("control_surface_obedience_result.surface_results entries must be objects")
        surface_id = row.get("surface_id")
        status = row.get("status")
        if not isinstance(surface_id, str) or not surface_id:
            raise ControlSurfaceGapExtractionError("control_surface_obedience_result.surface_results.surface_id must be non-empty")
        if not isinstance(status, str) or status not in {"PASS", "BLOCK"}:
            raise ControlSurfaceGapExtractionError("control_surface_obedience_result.surface_results.status must be PASS or BLOCK")
        if status == "BLOCK":
            _require_surface_mapping(surface_id, mapped_surfaces)
            gaps.append(
                _build_gap(
                    control_surface=surface_id,
                    gap_type="obedience_missing",
                    severity="blocker",
                    description=f"Obedience result blocked on {surface_id}.",
                    source_artifact_refs=[obedience_ref] if obedience_ref else ["control_surface_obedience_result"],
                    detected_by="obedience",
                )
            )

    deduped = list(
        {
            (
                gap["control_surface"],
                gap["gap_type"],
                gap["severity"],
                gap["description"],
                tuple(gap["source_artifact_refs"]),
                gap["detected_by"],
            ): gap
            for gap in gaps
        }.values()
    )
    ordered_gaps = sorted(deduped, key=lambda item: (item["control_surface"], item["gap_type"], item["severity"], item["gap_id"]))

    status = "gaps_detected" if ordered_gaps else "ok"
    identity_payload = {
        "status": status,
        "gaps": [
            {
                "gap_id": item["gap_id"],
                "control_surface": item["control_surface"],
                "gap_type": item["gap_type"],
                "severity": item["severity"],
            }
            for item in ordered_gaps
        ],
    }
    result = {
        "gap_result_id": f"GAP-{_canonical_hash(identity_payload)}",
        "timestamp": _utc_now(),
        "status": status,
        "gaps": ordered_gaps,
    }

    _validate(result, "control_surface_gap_result", label="control_surface_gap_result")
    return result
