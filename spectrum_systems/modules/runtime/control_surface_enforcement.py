"""Deterministic fail-closed control surface manifest enforcement (CON-030)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ControlSurfaceEnforcementError(ValueError):
    """Raised when control surface enforcement cannot be safely evaluated."""


_REQUIRED_SURFACE_POLICY_VERSION = "1.0.0"
_REQUIRED_GOVERNED_SURFACES = [
    "contract_preflight_gate",
    "done_certification_gate",
    "evaluation_control_runtime",
    "replay_governance_gate",
    "sequence_transition_promotion",
    "trust_spine_invariant_validation",
]


def _canonical_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_manifest_from_path(manifest_path: Path) -> Dict[str, Any]:
    if not manifest_path.is_file():
        raise ControlSurfaceEnforcementError(f"manifest file not found: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ControlSurfaceEnforcementError(f"manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ControlSurfaceEnforcementError("manifest payload must be a JSON object")
    return payload


def _validate_manifest(manifest: Dict[str, Any]) -> None:
    schema = load_schema("control_surface_manifest")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda err: list(err.absolute_path))
    if errors:
        reasons = "; ".join(error.message for error in errors)
        raise ControlSurfaceEnforcementError(f"manifest failed schema validation: {reasons}")


def _has_invariant_coverage(surface: Dict[str, Any]) -> bool:
    coverage = surface.get("invariant_coverage", {})
    invariants = coverage.get("invariants_applied", [])
    if not isinstance(invariants, list):
        return False
    return len(invariants) > 0


def _has_test_coverage(surface: Dict[str, Any]) -> bool:
    coverage = surface.get("test_coverage", {})
    status = coverage.get("coverage_status")
    files = coverage.get("covering_test_files", [])
    if not isinstance(files, list) or not files:
        return False
    return status == "covered"


def evaluate_control_surface_enforcement(*, manifest: Dict[str, Any], manifest_ref: str) -> Dict[str, Any]:
    _validate_manifest(manifest)

    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list):
        raise ControlSurfaceEnforcementError("manifest missing surfaces array")

    by_id: Dict[str, Dict[str, Any]] = {}
    for item in surfaces:
        if not isinstance(item, dict):
            raise ControlSurfaceEnforcementError("manifest surface entries must be objects")
        sid = item.get("surface_id")
        if not isinstance(sid, str) or not sid:
            raise ControlSurfaceEnforcementError("surface_id must be non-empty string")
        by_id[sid] = item

    missing_required = sorted([sid for sid in _REQUIRED_GOVERNED_SURFACES if sid not in by_id])
    present_required = [sid for sid in _REQUIRED_GOVERNED_SURFACES if sid in by_id]

    missing_invariants = sorted([sid for sid in present_required if not _has_invariant_coverage(by_id[sid])])
    missing_test_coverage = sorted([sid for sid in present_required if not _has_test_coverage(by_id[sid])])

    blocking_reasons: List[str] = []
    if missing_required:
        blocking_reasons.append("REQUIRED_SURFACES_MISSING")
    if missing_invariants:
        blocking_reasons.append("REQUIRED_SURFACES_INVARIANTS_MISSING")
    if missing_test_coverage:
        blocking_reasons.append("REQUIRED_SURFACES_TEST_COVERAGE_MISSING")

    coverage_summary = {
        "required_surface_count": len(_REQUIRED_GOVERNED_SURFACES),
        "required_surface_present_count": len(present_required),
        "required_surface_invariant_covered_count": len(present_required) - len(missing_invariants),
        "required_surface_test_covered_count": len(present_required) - len(missing_test_coverage),
        "blocking_gaps_present": bool(blocking_reasons),
    }

    identity_payload = {
        "manifest_identity": manifest["deterministic_build_identity"],
        "required_surfaces_evaluated": _REQUIRED_GOVERNED_SURFACES,
        "missing_required_surfaces": missing_required,
        "surfaces_missing_invariants": missing_invariants,
        "surfaces_missing_test_coverage": missing_test_coverage,
    }
    deterministic_enforcement_id = f"cse-{_canonical_hash(identity_payload)[:16]}"

    result = {
        "artifact_type": "control_surface_enforcement_result",
        "schema_version": "1.0.0",
        "manifest_ref": manifest_ref,
        "manifest_identity": manifest["deterministic_build_identity"],
        "enforcement_status": "BLOCK" if blocking_reasons else "PASS",
        "required_surface_policy_version": _REQUIRED_SURFACE_POLICY_VERSION,
        "required_surfaces_evaluated": list(_REQUIRED_GOVERNED_SURFACES),
        "missing_required_surfaces": missing_required,
        "surfaces_missing_invariants": missing_invariants,
        "surfaces_missing_test_coverage": missing_test_coverage,
        "blocking_reasons": blocking_reasons,
        "coverage_summary": coverage_summary,
        "deterministic_enforcement_id": deterministic_enforcement_id,
        "trace": {
            "producer": "spectrum_systems.modules.runtime.control_surface_enforcement",
            "policy_ref": "CON-030.required_surfaces.v1",
            "manifest_schema_version": manifest["schema_version"],
        },
    }

    schema = load_schema("control_surface_enforcement_result")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(result), key=lambda err: list(err.absolute_path))
    if errors:
        reasons = "; ".join(error.message for error in errors)
        raise ControlSurfaceEnforcementError(f"enforcement result failed schema validation: {reasons}")

    return result


def run_control_surface_enforcement(*, manifest_path: Path, manifest_ref: str | None = None) -> Dict[str, Any]:
    manifest = _load_manifest_from_path(manifest_path)
    return evaluate_control_surface_enforcement(
        manifest=manifest,
        manifest_ref=manifest_ref or str(manifest_path.as_posix()),
    )
