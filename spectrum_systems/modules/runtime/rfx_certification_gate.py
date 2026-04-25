"""RFX certification hard gate — LOOP-06 implementation.

GOV is the certification packaging authority. CDE remains the decision
authority and TPA remains the trust/policy authority. GOV does NOT decide
readiness — it only certifies that the full evidence bundle is present and
valid.

Required evidence for certification:
  EVL, TPA, CDE, SEL, LIN, REP, OBS, SLO, PRA, POL (when policy in scope).

All failures are deterministic and emit machine-readable reason codes.
Missing artifact = halt. No implicit certification.
"""

from __future__ import annotations

from typing import Any


class RFXCertificationGateError(ValueError):
    """Raised when GOV certification hard-gate invariants fail closed."""


_VALID_EVL_STATUSES = frozenset({"pass", "conditional_pass"})
_VALID_TPA_STATUSES = frozenset({"accepted", "conditional"})
_VALID_CDE_STATUSES = frozenset({"ready", "not_ready"})
_VALID_PRA_STATUS = "ready"
_VALID_POL_STATUSES = frozenset({"active", "canary", "approved"})
_POL_SCOPE_TRUE_VALUES = frozenset({True, "true", "True", "in_scope", "required"})


def _is_nonempty_dict(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj)


def _policy_in_scope(pol: dict[str, Any] | None) -> bool:
    """Determine whether POL evidence is required for this RFX path.

    POL is required when:
      - the caller passes a non-empty POL artifact (treated as in scope), OR
      - the POL artifact explicitly marks ``in_scope`` / ``required``.

    Absent POL is treated as in-scope only when the caller signals so via the
    artifact's own ``policy_in_scope`` field. Callers MUST pass the POL
    artifact when policy is in scope; the gate fails closed if it is missing.
    """
    if not isinstance(pol, dict):
        return False
    scope_field = pol.get("policy_in_scope")
    if scope_field in _POL_SCOPE_TRUE_VALUES:
        return True
    return bool(pol)


def assert_rfx_certification_ready(
    *,
    evl: dict[str, Any] | None,
    tpa: dict[str, Any] | None,
    cde: dict[str, Any] | None,
    sel: dict[str, Any] | None,
    lin: dict[str, Any] | None,
    rep: dict[str, Any] | None,
    obs: dict[str, Any] | None,
    slo: dict[str, Any] | None,
    pra: dict[str, Any] | None,
    pol: dict[str, Any] | None,
    policy_in_scope: bool | None = None,
    slo_required: bool = True,
) -> None:
    """Assert the full certification evidence bundle is present and valid.

    GOV does NOT decide readiness. This guard checks completeness and
    validity of the contributing evidence and fails closed with deterministic,
    machine-readable reason codes.

    Args:
      evl: EVL evaluation evidence; status must be ``pass`` or ``conditional_pass``.
      tpa: TPA adjudication record; status must be ``accepted`` or ``conditional``.
      cde: CDE closure decision (CDE is the decision authority).
      sel: SEL enforcement record linked to the CDE decision.
      lin: LIN lineage record; authenticity must be ``pass``.
      rep: REP replay record; ``match`` must be ``True``.
      obs: OBS telemetry completeness record.
      slo: SLO posture record; required by default.
      pra: PRA promotion-readiness artifact; status must be ``ready``.
      pol: POL policy posture; required when policy is in scope.
      policy_in_scope: explicit override controlling POL requirement. When
        ``None``, scope is inferred from ``pol`` (any non-empty POL artifact,
        or one carrying ``policy_in_scope`` truthy, is treated as in scope).
      slo_required: when True (default), SLO posture must be present.

    Reason codes (one per missing/invalid contribution, all collected before
    raising):
      rfx_missing_evl_evidence, rfx_evl_evidence_not_passing,
      rfx_missing_tpa_evidence, rfx_tpa_evidence_not_accepted,
      rfx_missing_cde_decision, rfx_invalid_cde_decision,
      rfx_missing_sel_link,
      rfx_missing_lineage, rfx_lineage_not_authentic,
      rfx_missing_replay, rfx_replay_mismatch,
      rfx_missing_obs,
      rfx_slo_block,
      rfx_missing_pra_evidence, rfx_pra_not_ready,
      rfx_missing_pol_evidence, rfx_pol_not_active.
    """
    reasons: list[str] = []

    # EVL ------------------------------------------------------------------
    if not _is_nonempty_dict(evl):
        reasons.append(
            "rfx_missing_evl_evidence: EVL evaluation record absent — "
            "GOV certification withheld"
        )
    else:
        evl_status = evl.get("status", evl.get("evaluation_status"))
        if evl_status not in _VALID_EVL_STATUSES:
            reasons.append(
                f"rfx_evl_evidence_not_passing: EVL status={evl_status!r} "
                f"not in {sorted(_VALID_EVL_STATUSES)}"
            )

    # TPA ------------------------------------------------------------------
    if not _is_nonempty_dict(tpa):
        reasons.append(
            "rfx_missing_tpa_evidence: TPA adjudication record absent — "
            "GOV certification withheld"
        )
    else:
        tpa_status = tpa.get("status", tpa.get("discipline_status"))
        if tpa_status not in _VALID_TPA_STATUSES:
            reasons.append(
                f"rfx_tpa_evidence_not_accepted: TPA status={tpa_status!r} "
                f"not in {sorted(_VALID_TPA_STATUSES)}"
            )

    # CDE ------------------------------------------------------------------
    if not _is_nonempty_dict(cde):
        reasons.append(
            "rfx_missing_cde_decision: CDE closure decision absent — "
            "GOV certification withheld"
        )
    else:
        cde_status = cde.get("status")
        if cde_status not in _VALID_CDE_STATUSES:
            reasons.append(
                f"rfx_invalid_cde_decision: CDE status={cde_status!r} "
                f"not in {sorted(_VALID_CDE_STATUSES)}"
            )

    # SEL ------------------------------------------------------------------
    if not _is_nonempty_dict(sel):
        reasons.append(
            "rfx_missing_sel_link: SEL enforcement record absent — "
            "GOV certification withheld"
        )
    else:
        cde_decision_id = cde.get("decision_id") if _is_nonempty_dict(cde) else None
        sel_cde_ref = sel.get("cde_decision_ref")
        sel_cde_id = sel.get("cde_decision_id")
        expected_ref = (
            f"cde_decision:{cde_decision_id}"
            if isinstance(cde_decision_id, str) and cde_decision_id
            else None
        )
        linked_by_ref = (
            expected_ref is not None
            and isinstance(sel_cde_ref, str)
            and sel_cde_ref == expected_ref
        )
        linked_by_id = (
            isinstance(cde_decision_id, str)
            and cde_decision_id
            and isinstance(sel_cde_id, str)
            and sel_cde_id == cde_decision_id
        )
        if not (linked_by_ref or linked_by_id):
            reasons.append(
                "rfx_missing_sel_link: SEL record does not reference the CDE "
                f"decision (expected cde_decision_ref={expected_ref!r} or "
                f"cde_decision_id={cde_decision_id!r})"
            )

    # LIN ------------------------------------------------------------------
    if not _is_nonempty_dict(lin):
        reasons.append(
            "rfx_missing_lineage: LIN lineage record absent — "
            "GOV certification withheld"
        )
    else:
        authenticity = lin.get("authenticity")
        if authenticity != "pass":
            reasons.append(
                f"rfx_lineage_not_authentic: lineage authenticity={authenticity!r} "
                "is not 'pass'"
            )

    # REP ------------------------------------------------------------------
    if not _is_nonempty_dict(rep):
        reasons.append(
            "rfx_missing_replay: REP replay record absent — "
            "GOV certification withheld"
        )
    else:
        replay_match = rep.get("match")
        if replay_match is not True:
            reasons.append(
                f"rfx_replay_mismatch: replay match={replay_match!r} is not True"
            )

    # OBS ------------------------------------------------------------------
    if not _is_nonempty_dict(obs):
        reasons.append(
            "rfx_missing_obs: OBS telemetry completeness record absent — "
            "GOV certification withheld"
        )
    else:
        obs_complete = obs.get("telemetry_complete", obs.get("complete"))
        if obs_complete is not True:
            reasons.append(
                f"rfx_missing_obs: OBS telemetry_complete={obs_complete!r} "
                "is not True"
            )

    # SLO ------------------------------------------------------------------
    if slo_required and not _is_nonempty_dict(slo):
        reasons.append(
            "rfx_slo_block: SLO posture record absent — "
            "GOV certification withheld"
        )
    elif _is_nonempty_dict(slo):
        slo_status = slo.get("status", slo.get("posture"))
        if slo_status in {"freeze", "block", "burn"}:
            reasons.append(
                f"rfx_slo_block: SLO status={slo_status!r} blocks certification"
            )

    # PRA ------------------------------------------------------------------
    if not _is_nonempty_dict(pra):
        reasons.append(
            "rfx_missing_pra_evidence: PRA promotion-readiness artifact absent — "
            "GOV certification withheld"
        )
    else:
        pra_status = pra.get("status")
        if pra_status != _VALID_PRA_STATUS:
            reasons.append(
                f"rfx_pra_not_ready: PRA status={pra_status!r} is not "
                f"{_VALID_PRA_STATUS!r}"
            )

    # POL ------------------------------------------------------------------
    pol_required = (
        _policy_in_scope(pol) if policy_in_scope is None else bool(policy_in_scope)
    )
    if pol_required:
        if not _is_nonempty_dict(pol):
            reasons.append(
                "rfx_missing_pol_evidence: POL policy posture absent while "
                "policy is in scope — GOV certification withheld"
            )
        else:
            pol_status = pol.get("status")
            if pol_status not in _VALID_POL_STATUSES:
                reasons.append(
                    f"rfx_pol_not_active: POL status={pol_status!r} not in "
                    f"{sorted(_VALID_POL_STATUSES)}"
                )

    if reasons:
        raise RFXCertificationGateError("; ".join(reasons))


__all__ = [
    "RFXCertificationGateError",
    "assert_rfx_certification_ready",
]
