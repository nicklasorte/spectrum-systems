"""RFX-N11 — Minimal RFX operator/dashboard surface contract.

Defines and validates the minimal surface that operators need to understand
RFX state: a compact proof summary rather than a raw artifact wall.  The
contract enforces that every operator surface record exposes only the
required compact fields and does not leak raw internal artifact payloads.

This module is a non-owning phase-label support helper. It does not own
operator dashboards or readiness-gate surfaces — canonical ownership is
recorded in ``docs/architecture/system_registry.md``.

Failure prevented: operators drowning in raw artifact output instead of
compact, actionable state summaries; operator tooling that bypasses proof
structure.

Signal improved: operator surface clarity; artifact-wall detection rate.

Reason codes:
  rfx_operator_surface_missing_status    — record lacks a status field
  rfx_operator_surface_missing_reason    — record lacks reason_codes_emitted
  rfx_operator_surface_raw_artifact_leak — record exposes raw internal artifact payload
  rfx_operator_surface_missing_proof_ref — record lacks a proof reference
  rfx_operator_surface_empty             — no records supplied
"""

from __future__ import annotations

from typing import Any

# Fields that indicate a raw internal artifact has leaked into the surface.
_RAW_ARTIFACT_INDICATORS: frozenset[str] = frozenset({
    "cases",
    "violations",
    "entries",
    "items",
    "records",
    "raw_payload",
    "internal_state",
})

# Required fields for a valid operator surface record.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "status",
    "reason_codes_emitted",
    "proof_ref",
)


def validate_rfx_operator_surface(
    *,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate that operator surface records satisfy the minimal compact contract."""
    reason: list[str] = []

    if not records:
        reason.append("rfx_operator_surface_empty")
        return {
            "artifact_type": "rfx_operator_surface_contract_result",
            "schema_version": "1.0.0",
            "reason_codes_emitted": sorted(set(reason)),
            "status": "invalid",
            "signals": {
                "total_records": 0,
                "valid_record_count": 0,
                "artifact_wall_count": 0,
            },
        }

    valid_count = 0
    artifact_wall_count = 0

    for rec in records:
        rec_ok = True
        if not rec.get("status"):
            reason.append("rfx_operator_surface_missing_status")
            rec_ok = False
        if not isinstance(rec.get("reason_codes_emitted"), list):
            reason.append("rfx_operator_surface_missing_reason")
            rec_ok = False
        if not rec.get("proof_ref"):
            reason.append("rfx_operator_surface_missing_proof_ref")
            rec_ok = False
        # Check for raw artifact leakage.
        leaked = _RAW_ARTIFACT_INDICATORS & set(rec.keys())
        if leaked:
            reason.append("rfx_operator_surface_raw_artifact_leak")
            artifact_wall_count += 1
            rec_ok = False
        if rec_ok:
            valid_count += 1

    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_operator_surface_contract_result",
        "schema_version": "1.0.0",
        "reason_codes_emitted": unique_reasons,
        "status": "valid" if not unique_reasons else "invalid",
        "signals": {
            "total_records": len(records),
            "valid_record_count": valid_count,
            "artifact_wall_count": artifact_wall_count,
        },
    }
