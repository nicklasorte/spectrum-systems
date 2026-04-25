"""RFX route guard — LOOP-01 through LOOP-03 implementation.

RFX (Review → Fix → eXecute) is a cross-system phase label, not a new system.
Path: RIL → FRE → PQX → EVL → TPA → CDE → SEL → GOV
Required overlays: REP + LIN + OBS + SLO
Required promotion evidence inputs: PRA promotion-readiness artifact, POL policy-posture record.

These guards enforce:
  LOOP-01: explicit phase_label: RFX in TLC route artifacts + AEX admission linkage
  LOOP-02: route lineage presence guard before PQX invocation
  LOOP-03: EVL + TPA evidence gate before CDE/SEL progression

All guards fail closed. Missing artifact = halt. No implicit approvals.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.contracts import validate_artifact


class RFXRouteGuardError(ValueError):
    """Raised when RFX route guard invariants fail closed."""


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# LOOP-01: Explicit phase_label: RFX in TLC route artifacts
# ---------------------------------------------------------------------------

def build_rfx_tlc_route_artifact(
    *,
    run_id: str,
    trace_id: str,
    aex_admission_id: str,
    intended_path: list[str],
    created_at: str,
) -> dict[str, Any]:
    """Build a TLC route artifact annotated with phase_label: RFX.

    RFX is a phase label. This artifact records the label, AEX admission ref,
    and required overlays. TLC is the routing and handoff layer — not an
    execution, closure, or trust-policy decision layer.
    """
    allowed_steps = frozenset(["AEX", "RIL", "FRE", "PQX", "EVL", "TPA", "CDE", "SEL", "GOV", "REP", "LIN", "OBS", "SLO", "PRA", "POL"])
    invalid = [s for s in intended_path if s not in allowed_steps]
    if invalid:
        raise RFXRouteGuardError(
            f"rfx_route_invalid_path: intended_path contains steps outside RFX phase: {invalid}"
        )
    if not isinstance(aex_admission_id, str) or not aex_admission_id.strip():
        raise RFXRouteGuardError("rfx_route_missing_aex_admission_id")

    artifact_id = f"rfx-route-{_hash([run_id, trace_id, aex_admission_id])[:16]}"
    artifact = {
        "artifact_type": "rfx_tlc_route_artifact",
        "schema_version": "1.0.0",
        "artifact_id": artifact_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "phase_label": "RFX",
        "aex_admission_ref": f"build_admission_record:{aex_admission_id}",
        "intended_path": intended_path,
        "overlays": ["LIN", "OBS", "REP", "SLO"],
        "created_at": created_at,
    }
    validate_artifact(artifact, "rfx_tlc_route_artifact")
    return artifact


# ---------------------------------------------------------------------------
# LOOP-01 / LOOP-02: AEX admission linkage guard
# ---------------------------------------------------------------------------

def assert_rfx_aex_admission_present(
    *,
    route_artifact: dict[str, Any],
    build_admission_record: dict[str, Any] | None,
) -> None:
    """Assert AEX admission is present for repo-mutating RFX work.

    Fails closed with rfx_missing_aex_admission if admission record is absent,
    lacks an admission_id, or does not match the route artifact's ref.
    Fails closed with rfx_admission_not_accepted if admission_status != 'accepted'.
    """
    if not isinstance(build_admission_record, dict) or not build_admission_record:
        raise RFXRouteGuardError("rfx_missing_aex_admission: build_admission_record absent")

    admission_id = build_admission_record.get("admission_id")
    if not admission_id:
        raise RFXRouteGuardError("rfx_missing_aex_admission: admission_id absent in build_admission_record")

    expected_ref = f"build_admission_record:{admission_id}"
    if route_artifact.get("aex_admission_ref") != expected_ref:
        raise RFXRouteGuardError(
            f"rfx_admission_ref_mismatch: route_artifact.aex_admission_ref="
            f"{route_artifact.get('aex_admission_ref')!r} does not match expected {expected_ref!r}"
        )

    admission_status = build_admission_record.get("admission_status")
    if admission_status != "accepted":
        raise RFXRouteGuardError(
            f"rfx_admission_not_accepted: admission_status={admission_status!r}"
        )


# ---------------------------------------------------------------------------
# LOOP-02: TLC route completeness / direct PQX lineage guard
# ---------------------------------------------------------------------------

def assert_rfx_pqx_lineage_present(
    *,
    route_artifact: dict[str, Any] | None,
    tlc_handoff_record: dict[str, Any] | None,
) -> None:
    """Assert TLC route lineage is present before PQX invocation for RFX work.

    Direct PQX invocation for repo-mutating RFX work without AEX/TLC lineage
    must fail closed with rfx_pqx_direct_invocation_blocked.
    """
    if not isinstance(route_artifact, dict) or route_artifact.get("phase_label") != "RFX":
        raise RFXRouteGuardError(
            "rfx_pqx_direct_invocation_blocked: missing RFX TLC route artifact — "
            "repo-mutating RFX execution requires AEX/TLC lineage"
        )
    if not isinstance(tlc_handoff_record, dict) or not tlc_handoff_record:
        raise RFXRouteGuardError(
            "rfx_pqx_direct_invocation_blocked: missing TLC handoff record — "
            "PQX cannot execute RFX work without TLC-mediated lineage"
        )
    handoff_status = tlc_handoff_record.get("handoff_status")
    if handoff_status != "accepted":
        raise RFXRouteGuardError(
            f"rfx_pqx_direct_invocation_blocked: "
            f"tlc_handoff_record.handoff_status={handoff_status!r} is not accepted"
        )


# ---------------------------------------------------------------------------
# LOOP-03: EVL + TPA evidence gate before CDE/SEL progression
# ---------------------------------------------------------------------------

def _coerce_first_present(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def assert_rfx_evl_tpa_evidence_present(
    *,
    evl_evidence: dict[str, Any] | None,
    tpa_evidence: dict[str, Any] | None,
) -> None:
    """Assert EVL and TPA evidence are present before CDE/SEL progression.

    Missing EVL or TPA evidence produces deterministic stop reasons.
    Fails closed; all reason codes are collected before raising.

    Status keys are coerced from either the LOOP-03-original names
    (``evaluation_status`` / ``discipline_status``) or the unified
    ``status`` key also accepted by LOOP-06, so producers using either
    schema variant flow through to the certification gate consistently.
    """
    reasons: list[str] = []

    if not isinstance(evl_evidence, dict) or not evl_evidence:
        reasons.append(
            "rfx_missing_evl_evidence: EVL evaluation record absent — CDE/SEL progression blocked"
        )
    else:
        evl_status = _coerce_first_present(evl_evidence, "evaluation_status", "status")
        if evl_status not in {"pass", "conditional_pass"}:
            reasons.append(
                f"rfx_evl_evidence_not_passing: EVL evaluation_status={evl_status!r}"
            )

    if not isinstance(tpa_evidence, dict) or not tpa_evidence:
        reasons.append(
            "rfx_missing_tpa_evidence: TPA adjudication record absent — CDE/SEL progression blocked"
        )
    else:
        tpa_status = _coerce_first_present(tpa_evidence, "discipline_status", "status")
        if tpa_status not in {"accepted", "conditional"}:
            reasons.append(
                f"rfx_tpa_evidence_not_accepted: TPA discipline_status={tpa_status!r}"
            )

    if reasons:
        raise RFXRouteGuardError("; ".join(reasons))


__all__ = [
    "RFXRouteGuardError",
    "build_rfx_tlc_route_artifact",
    "assert_rfx_aex_admission_present",
    "assert_rfx_pqx_lineage_present",
    "assert_rfx_evl_tpa_evidence_present",
]
