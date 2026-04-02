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


_GAP_CATEGORY_VALUES = {
    "missing_manifest_surface",
    "missing_required_test_coverage",
    "missing_required_invariant_coverage",
    "enforcement_block",
    "obedience_block",
    "insufficient_runtime_evidence",
    "trust_spine_contradiction",
    "certification_alignment_gap",
    "malformed_input_artifact",
}

_SEVERITY_VALUES = {"low", "medium", "high", "critical"}
_ACTION_VALUES = {
    "add_test_coverage",
    "add_invariant_coverage",
    "add_runtime_evidence",
    "fix_manifest_declaration",
    "reconcile_certification_inputs",
    "investigate_malformed_artifact",
    "block_promotion",
}
_DECISION_VALUES = {"ALLOW", "WARN", "BLOCK"}


def _require_object(instance: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(instance, dict):
        raise ControlSurfaceGapExtractionError(f"{label} must be a JSON object")
    return instance


def _require_enum(value: Any, *, label: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise ControlSurfaceGapExtractionError(f"{label} must be one of {sorted(allowed)}")
    normalized = value.strip()
    if normalized not in allowed:
        raise ControlSurfaceGapExtractionError(f"{label} must be one of {sorted(allowed)}")
    return normalized


def _surface_ids(manifest: dict[str, Any]) -> set[str]:
    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list):
        raise ControlSurfaceGapExtractionError("control_surface_manifest.surfaces must be a list")
    values: set[str] = set()
    for item in surfaces:
        if not isinstance(item, dict):
            raise ControlSurfaceGapExtractionError("control_surface_manifest surface entries must be objects")
        sid = item.get("surface_id")
        if not isinstance(sid, str) or not sid.strip():
            raise ControlSurfaceGapExtractionError("control_surface_manifest surface_id must be a non-empty string")
        values.add(sid)
    return values


def _build_packet_gap(
    *,
    surface_name: str,
    gap_category: str,
    severity: str,
    blocking: bool,
    observed_condition: str,
    expected_condition: str,
    evidence_ref: str,
    source_artifact_type: str,
    source_artifact_ref: str,
    suggested_action: str,
) -> dict[str, Any]:
    canonical = {
        "surface_name": surface_name,
        "gap_category": gap_category,
        "severity": severity,
        "blocking": blocking,
        "observed_condition": observed_condition,
        "expected_condition": expected_condition,
        "evidence_ref": evidence_ref,
        "source_artifact_type": source_artifact_type,
        "source_artifact_ref": source_artifact_ref,
        "suggested_action": suggested_action,
    }
    deterministic_identity = f"csg-{_canonical_hash(canonical)[:24]}"
    return {
        "gap_id": deterministic_identity,
        **canonical,
        "deterministic_identity": deterministic_identity,
    }


def extract_control_surface_gap_packet(
    *,
    manifest: dict[str, Any],
    enforcement_result: dict[str, Any],
    obedience_result: dict[str, Any],
    trust_spine_result: dict[str, Any],
    done_certification_record: dict[str, Any],
    generated_at: str,
    trace_id: str,
    policy_id: str = "CON-034.control_surface_gap_extraction.v1",
    governing_ref: str = "docs/roadmaps/system_roadmap.md#con-034",
) -> dict[str, Any]:
    """Extract deterministic control-surface gaps into a governed packet artifact."""
    _validate(manifest, "control_surface_manifest", label="control_surface_manifest")
    _validate(enforcement_result, "control_surface_enforcement_result", label="control_surface_enforcement_result")
    _validate(obedience_result, "control_surface_obedience_result", label="control_surface_obedience_result")
    _validate(done_certification_record, "done_certification_record", label="done_certification_record")

    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ControlSurfaceGapExtractionError("generated_at must be a non-empty RFC3339 timestamp")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ControlSurfaceGapExtractionError("trace_id must be a non-empty string")

    surfaces = _surface_ids(manifest)
    manifest_ref = str(enforcement_result.get("manifest_ref") or obedience_result.get("manifest_ref") or "control_surface_manifest")
    enforcement_ref = str(obedience_result.get("enforcement_result_ref") or "control_surface_enforcement_result")
    obedience_ref = str(obedience_result.get("trace", {}).get("evidence_refs", {}).get("invariant_result_ref") or "control_surface_obedience_result")
    trust_ref = str(trust_spine_result.get("artifact_refs", {}).get("invariant_result_ref") or done_certification_record.get("input_refs", {}).get("trust_spine_evidence_cohesion_result_ref") or "trust_spine_result")
    cert_ref = "done_certification_record"

    gaps: list[dict[str, Any]] = []

    for sid in sorted(enforcement_result.get("missing_required_surfaces", [])):
        if sid not in surfaces:
            raise ControlSurfaceGapExtractionError(f"enforcement references unknown surface: {sid}")
        gaps.append(
            _build_packet_gap(
                surface_name=sid,
                gap_category="missing_manifest_surface",
                severity="critical",
                blocking=True,
                observed_condition=f"required surface {sid} absent from manifest-evaluated set",
                expected_condition="all required surfaces must be declared and evaluated",
                evidence_ref=enforcement_ref,
                source_artifact_type="control_surface_enforcement_result",
                source_artifact_ref=enforcement_ref,
                suggested_action="fix_manifest_declaration",
            )
        )

    for sid in sorted(enforcement_result.get("surfaces_missing_test_coverage", [])):
        if sid not in surfaces:
            raise ControlSurfaceGapExtractionError(f"enforcement references unknown surface: {sid}")
        gaps.append(
            _build_packet_gap(
                surface_name=sid,
                gap_category="missing_required_test_coverage",
                severity="high",
                blocking=True,
                observed_condition=f"required test coverage missing for {sid}",
                expected_condition="required surfaces must provide covered test_coverage",
                evidence_ref=enforcement_ref,
                source_artifact_type="control_surface_enforcement_result",
                source_artifact_ref=enforcement_ref,
                suggested_action="add_test_coverage",
            )
        )

    for sid in sorted(enforcement_result.get("surfaces_missing_invariants", [])):
        if sid not in surfaces:
            raise ControlSurfaceGapExtractionError(f"enforcement references unknown surface: {sid}")
        gaps.append(
            _build_packet_gap(
                surface_name=sid,
                gap_category="missing_required_invariant_coverage",
                severity="critical",
                blocking=True,
                observed_condition=f"required invariant coverage missing for {sid}",
                expected_condition="required surfaces must declare invariant coverage",
                evidence_ref=enforcement_ref,
                source_artifact_type="control_surface_enforcement_result",
                source_artifact_ref=enforcement_ref,
                suggested_action="add_invariant_coverage",
            )
        )

    if _require_enum(enforcement_result.get("enforcement_status"), label="enforcement_status", allowed={"PASS", "BLOCK"}) == "BLOCK":
        gaps.append(
            _build_packet_gap(
                surface_name="control_surface_enforcement",
                gap_category="enforcement_block",
                severity="critical",
                blocking=True,
                observed_condition="enforcement_status=BLOCK",
                expected_condition="enforcement_status=PASS",
                evidence_ref=enforcement_ref,
                source_artifact_type="control_surface_enforcement_result",
                source_artifact_ref=enforcement_ref,
                suggested_action="block_promotion",
            )
        )

    if _require_enum(obedience_result.get("overall_decision"), label="overall_decision", allowed={"ALLOW", "BLOCK"}) == "BLOCK":
        gaps.append(
            _build_packet_gap(
                surface_name="control_surface_obedience",
                gap_category="obedience_block",
                severity="critical",
                blocking=True,
                observed_condition="control-surface runtime obedience decision is BLOCK",
                expected_condition="control-surface runtime obedience decision is ALLOW",
                evidence_ref=obedience_ref,
                source_artifact_type="control_surface_obedience_result",
                source_artifact_ref=obedience_ref,
                suggested_action="add_runtime_evidence",
            )
        )

    missing_obedience = obedience_result.get("missing_obedience_evidence")
    if not isinstance(missing_obedience, list):
        raise ControlSurfaceGapExtractionError("control_surface_obedience_result.missing_obedience_evidence must be a list")
    if missing_obedience:
        gaps.append(
            _build_packet_gap(
                surface_name="control_surface_obedience",
                gap_category="insufficient_runtime_evidence",
                severity="critical",
                blocking=True,
                observed_condition="missing_obedience_evidence contains unresolved entries",
                expected_condition="all required runtime obedience evidence is present",
                evidence_ref=obedience_ref,
                source_artifact_type="control_surface_obedience_result",
                source_artifact_ref=obedience_ref,
                suggested_action="add_runtime_evidence",
            )
        )

    trust = _require_object(trust_spine_result, label="trust_spine_result")
    trust_overall = trust.get("overall_decision")
    trust_blocking_reasons = trust.get("blocking_reasons")
    if trust_overall is not None and _require_enum(trust_overall, label="trust_spine_result.overall_decision", allowed={"ALLOW", "BLOCK"}) == "BLOCK":
        gaps.append(
            _build_packet_gap(
                surface_name="trust_spine",
                gap_category="trust_spine_contradiction",
                severity="critical",
                blocking=True,
                observed_condition="trust-spine result overall_decision=BLOCK",
                expected_condition="trust-spine result overall_decision=ALLOW",
                evidence_ref=trust_ref,
                source_artifact_type=str(trust.get("artifact_type") or "trust_spine_result"),
                source_artifact_ref=trust_ref,
                suggested_action="reconcile_certification_inputs",
            )
        )
    elif trust.get("passed") is False:
        gaps.append(
            _build_packet_gap(
                surface_name="trust_spine",
                gap_category="trust_spine_contradiction",
                severity="critical",
                blocking=True,
                observed_condition="trust-spine invariant passed=false",
                expected_condition="trust-spine invariant passed=true",
                evidence_ref=trust_ref,
                source_artifact_type=str(trust.get("artifact_type") or "trust_spine_result"),
                source_artifact_ref=trust_ref,
                suggested_action="reconcile_certification_inputs",
            )
        )

    if trust_blocking_reasons is not None and not isinstance(trust_blocking_reasons, list):
        raise ControlSurfaceGapExtractionError("trust_spine_result.blocking_reasons must be a list when provided")

    final_status = _require_enum(done_certification_record.get("final_status"), label="done_certification_record.final_status", allowed={"PASSED", "FAILED"})
    cert_blocking = done_certification_record.get("blocking_reasons")
    if not isinstance(cert_blocking, list):
        raise ControlSurfaceGapExtractionError("done_certification_record.blocking_reasons must be a list")

    upstream_block = any(gap["blocking"] for gap in gaps)
    if final_status == "PASSED" and upstream_block:
        gaps.append(
            _build_packet_gap(
                surface_name="done_certification_gate",
                gap_category="certification_alignment_gap",
                severity="critical",
                blocking=True,
                observed_condition="done certification passed while upstream control-surface evidence is blocking",
                expected_condition="certification status aligns with upstream blocking evidence",
                evidence_ref=cert_ref,
                source_artifact_type="done_certification_record",
                source_artifact_ref=cert_ref,
                suggested_action="reconcile_certification_inputs",
            )
        )
    if final_status == "FAILED" and not cert_blocking:
        gaps.append(
            _build_packet_gap(
                surface_name="done_certification_gate",
                gap_category="malformed_input_artifact",
                severity="critical",
                blocking=True,
                observed_condition="final_status=FAILED with empty blocking_reasons",
                expected_condition="failed certification records must include blocking reasons",
                evidence_ref=cert_ref,
                source_artifact_type="done_certification_record",
                source_artifact_ref=cert_ref,
                suggested_action="investigate_malformed_artifact",
            )
        )

    deduped = list({gap["deterministic_identity"]: gap for gap in gaps}.values())
    ordered_gaps = sorted(deduped, key=lambda item: (item["surface_name"], item["gap_category"], item["gap_id"]))

    gap_count = len(ordered_gaps)
    blocking_gap_count = len([gap for gap in ordered_gaps if gap["blocking"]])

    overall_decision = "ALLOW"
    if blocking_gap_count > 0:
        overall_decision = "BLOCK"
    elif gap_count > 0:
        overall_decision = "WARN"

    next_actions = sorted({gap["suggested_action"] for gap in ordered_gaps})
    evidence_refs = sorted({gap["evidence_ref"] for gap in ordered_gaps})

    identity_payload = {
        "manifest_identity": manifest.get("deterministic_build_identity"),
        "enforcement_id": enforcement_result.get("deterministic_enforcement_id"),
        "obedience_id": obedience_result.get("deterministic_obedience_id"),
        "trace_id": trace_id,
        "gap_identities": [gap["deterministic_identity"] for gap in ordered_gaps],
        "overall_decision": overall_decision,
    }
    artifact_id = f"csgp-{_canonical_hash(identity_payload)[:24]}"

    packet = {
        "artifact_type": "control_surface_gap_packet",
        "artifact_id": artifact_id,
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "trace_id": trace_id.strip(),
        "policy_id": policy_id,
        "governing_ref": governing_ref,
        "overall_decision": overall_decision,
        "summary": "No control-surface gaps detected." if gap_count == 0 else f"Detected {gap_count} control-surface gap(s).",
        "evaluated_surfaces": sorted(surfaces),
        "gap_count": gap_count,
        "blocking_gap_count": blocking_gap_count,
        "gaps": ordered_gaps,
        "evidence_refs": evidence_refs,
        "next_governance_actions": next_actions,
    }

    _validate(packet, "control_surface_gap_packet", label="control_surface_gap_packet")
    return packet
