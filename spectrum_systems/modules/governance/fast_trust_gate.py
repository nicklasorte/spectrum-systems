"""OC-16..18: Fast trust gate manifest loader and run summary builder.

The fast trust gate is a smaller, high-signal subset of the full pytest
suite. It enumerates the seams the gate MUST cover:

    registry_validation, authority_shape_preflight, proof_intake,
    bottleneck_classifier, closure_packet, dashboard_projection,
    work_selection, trust_regression_pack

The manifest defines selectors (pytest nodes, scripts, or module
callables). The runner consumes the manifest, executes each selector,
and emits a fast_trust_gate_run summary. The runner is non-owning:
verdicts are observations, not control or enforcement.

This module provides:

  * :func:`load_fast_trust_gate_manifest` — load and validate manifest
  * :func:`audit_fast_trust_gate_coverage` — verify a manifest covers
    every required seam (used by red-team coverage tests)
  * :func:`build_fast_trust_gate_run_summary` — given a sequence of
    seam results, derive an overall ``ok`` / ``failed`` / ``unknown``
    summary plus per-seam reason codes.

Module is non-owning. Canonical authority unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


REQUIRED_SEAMS = (
    "registry_validation",
    "authority_shape_preflight",
    "proof_intake",
    "bottleneck_classifier",
    "closure_packet",
    "dashboard_projection",
    "work_selection",
    "trust_regression_pack",
)


CANONICAL_REASON_CODES = frozenset(
    {
        "FAST_TRUST_GATE_OK",
        "FAST_TRUST_GATE_SEAM_MISSING",
        "FAST_TRUST_GATE_SEAM_FAILED",
        "FAST_TRUST_GATE_SEAM_UNKNOWN",
        "FAST_TRUST_GATE_INSUFFICIENT_COVERAGE",
        "FAST_TRUST_GATE_SUFFICIENT",
    }
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = (
    REPO_ROOT / "contracts" / "governance" / "fast_trust_gate_manifest.json"
)


class FastTrustGateError(ValueError):
    """Raised when the fast trust gate cannot be deterministically built."""


def load_fast_trust_gate_manifest(
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the fast trust gate manifest from disk."""
    p = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    if not p.exists():
        raise FastTrustGateError(f"manifest file not found: {p}")
    text = p.read_text(encoding="utf-8")
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FastTrustGateError(f"invalid manifest JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise FastTrustGateError("manifest must be a JSON object")
    if manifest.get("artifact_type") != "fast_trust_gate_manifest":
        raise FastTrustGateError("manifest artifact_type mismatch")
    return manifest


def audit_fast_trust_gate_coverage(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """Verify the manifest covers every required seam.

    Returns a dict with ``coverage_status`` (``sufficient`` /
    ``insufficient``) and ``missing_seams`` (list).
    """
    seams = manifest.get("required_seams") or []
    declared = set(seams) if isinstance(seams, list) else set()
    selectors_list = manifest.get("selectors") or []
    declared_in_selectors = set()
    if isinstance(selectors_list, list):
        for sel in selectors_list:
            if isinstance(sel, Mapping):
                seam = sel.get("seam")
                if isinstance(seam, str):
                    declared_in_selectors.add(seam)
    missing = [s for s in REQUIRED_SEAMS if s not in declared]
    missing_selectors = [s for s in REQUIRED_SEAMS if s not in declared_in_selectors]

    if missing or missing_selectors:
        return {
            "coverage_status": "insufficient",
            "reason_code": "FAST_TRUST_GATE_INSUFFICIENT_COVERAGE",
            "missing_seams": missing,
            "missing_selectors": missing_selectors,
        }
    return {
        "coverage_status": "sufficient",
        "reason_code": "FAST_TRUST_GATE_SUFFICIENT",
        "missing_seams": [],
        "missing_selectors": [],
    }


def build_fast_trust_gate_run_summary(
    *,
    run_id: str,
    audit_timestamp: str,
    manifest: Mapping[str, Any],
    seam_results: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build a run summary from the manifest and seam results.

    Each ``seam_results`` entry is a mapping with at least ``seam``,
    ``status`` (``ok`` / ``failed`` / ``unknown``), and optional
    ``reason_code`` and ``selector``.

    The summary status is:
      * ``failed`` if any seam reported ``failed``
      * ``unknown`` if any seam reported ``unknown`` and none failed
      * ``ok`` only when every required seam reports ``ok``
      * ``failed`` when any required seam is missing from results
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise FastTrustGateError("run_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise FastTrustGateError("audit_timestamp must be a non-empty string")

    coverage = audit_fast_trust_gate_coverage(manifest)
    if coverage["coverage_status"] == "insufficient":
        return {
            "artifact_type": "fast_trust_gate_run",
            "schema_version": "1.0.0",
            "run_id": run_id,
            "audit_timestamp": audit_timestamp,
            "manifest_id": manifest.get("manifest_id", ""),
            "overall_status": "failed",
            "sufficiency": "insufficient",
            "reason_code": "FAST_TRUST_GATE_INSUFFICIENT_COVERAGE",
            "seam_results": [],
            "missing_seams": coverage["missing_seams"],
            "non_authority_assertions": [
                "preparatory_only",
                "not_control_authority",
                "not_enforcement_authority",
            ],
        }

    by_seam: Dict[str, Mapping[str, Any]] = {}
    for r in seam_results:
        if not isinstance(r, Mapping):
            continue
        seam = r.get("seam")
        if isinstance(seam, str):
            by_seam[seam] = r

    out: List[Dict[str, Any]] = []
    saw_failed = False
    saw_unknown = False
    missing: List[str] = []

    for seam in REQUIRED_SEAMS:
        r = by_seam.get(seam)
        if r is None:
            out.append(
                {
                    "seam": seam,
                    "status": "unknown",
                    "reason_code": "FAST_TRUST_GATE_SEAM_MISSING",
                }
            )
            missing.append(seam)
            saw_failed = True
            continue
        status = r.get("status")
        reason = r.get("reason_code")
        if status == "ok":
            out.append(
                {
                    "seam": seam,
                    "status": "ok",
                    "reason_code": "FAST_TRUST_GATE_OK",
                    "selector": r.get("selector"),
                }
            )
        elif status == "failed":
            saw_failed = True
            out.append(
                {
                    "seam": seam,
                    "status": "failed",
                    "reason_code": reason or "FAST_TRUST_GATE_SEAM_FAILED",
                    "selector": r.get("selector"),
                }
            )
        else:
            saw_unknown = True
            out.append(
                {
                    "seam": seam,
                    "status": "unknown",
                    "reason_code": reason or "FAST_TRUST_GATE_SEAM_UNKNOWN",
                    "selector": r.get("selector"),
                }
            )

    if saw_failed:
        overall = "failed"
        reason_code = "FAST_TRUST_GATE_SEAM_FAILED"
    elif saw_unknown:
        overall = "unknown"
        reason_code = "FAST_TRUST_GATE_SEAM_UNKNOWN"
    else:
        overall = "ok"
        reason_code = "FAST_TRUST_GATE_OK"

    sufficiency = "sufficient" if not missing else "insufficient"

    return {
        "artifact_type": "fast_trust_gate_run",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "audit_timestamp": audit_timestamp,
        "manifest_id": manifest.get("manifest_id", ""),
        "overall_status": overall,
        "sufficiency": sufficiency,
        "reason_code": reason_code,
        "seam_results": out,
        "missing_seams": missing,
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_enforcement_authority",
        ],
    }
