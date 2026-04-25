"""RFX certification evidence completeness guard — LOOP-06 implementation.

This module is a non-owning presence check used during the RFX phase.
It does not assign or transfer canonical responsibilities; canonical
mappings are declared in the system registry. The guard verifies that the
certification evidence package supplied to it contains every required
contribution before promotion can be considered.

Required contributions in the evidence package:
  evaluation evidence, trust-policy evidence, closure-decision evidence,
  enforcement-linkage evidence, lineage evidence, replay evidence,
  telemetry-completeness evidence, posture evidence, promotion-readiness
  input, and policy-posture input (when policy is in scope).

All failure modes are deterministic and emit machine-readable reason codes.
Missing artifact = halt. Implicit certification is not permitted.
"""

from __future__ import annotations

from typing import Any


class RFXCertificationGateError(ValueError):
    """Raised when the RFX certification evidence completeness guard fails closed."""


_VALID_EVL_STATUSES = frozenset({"pass", "conditional_pass"})
_VALID_TPA_STATUSES = frozenset({"accepted", "conditional"})
_VALID_CDE_STATUSES = frozenset({"ready", "not_ready"})
_VALID_PRA_STATUS = "ready"
_VALID_POL_STATUSES = frozenset({"active", "canary", "approved"})
_POL_SCOPE_TRUE_VALUES = frozenset({True, "true", "True", "in_scope", "required"})


def _is_nonempty_dict(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj)


def _policy_in_scope(pol: dict[str, Any] | None) -> bool:
    """Determine whether the policy-posture input is required for this RFX path.

    The guard fails closed by default. Policy is treated as in scope unless
    the caller explicitly opts out via the ``policy_in_scope=False`` keyword
    on :func:`assert_rfx_certification_ready`. This means:

      - an absent or empty input record yields ``True`` (in scope), so the
        gate raises ``rfx_missing_pol_evidence`` instead of silently passing;
      - a non-empty input record yields ``True`` (in scope);
      - an input record with ``policy_in_scope=False`` still yields ``True``
        because the explicit override is owned by the caller's keyword
        argument, not the artifact contents.

    Callers that genuinely need to skip POL evidence must pass
    ``policy_in_scope=False`` to :func:`assert_rfx_certification_ready`.
    """
    return True


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
    """Verify the certification evidence package contains every required contribution.

    This guard does not issue closure, trust, policy, lineage, replay, or
    certification decisions. It only confirms that each required contribution
    is present and in an acceptable state, then fails closed with
    deterministic, machine-readable reason codes when something is missing or
    invalid. Canonical responsibilities for the contributing signals stay with
    the systems declared in the system registry.

    Args:
      evl: evaluation evidence record; status must be ``pass`` or ``conditional_pass``.
      tpa: trust-policy adjudication record; status must be ``accepted`` or ``conditional``.
      cde: closure-decision record (status ``ready`` or ``not_ready``).
      sel: enforcement-linkage record referencing the closure-decision artifact.
      lin: lineage evidence record; authenticity must be ``pass``.
      rep: replay evidence record; ``match`` must be ``True``.
      obs: telemetry-completeness record.
      slo: posture record; required by default.
      pra: promotion-readiness input; status must be ``ready``.
      pol: policy-posture input; required when policy is in scope.
      policy_in_scope: explicit toggle for the policy-posture requirement.
        Defaults to ``None``, which fails closed: the guard treats policy as
        in scope and requires a valid POL input. Callers that genuinely have
        no policy in scope must pass ``policy_in_scope=False`` explicitly.
        Passing ``True`` is equivalent to the default and is supported for
        readability at call sites.
      slo_required: when True (default), the posture record must be present.

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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
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
            "certification evidence package incomplete"
        )
    elif _is_nonempty_dict(slo):
        slo_status = slo.get("status", slo.get("posture"))
        if slo_status in {"freeze", "block", "burn"}:
            reasons.append(
                f"rfx_slo_block: SLO status={slo_status!r} blocks certification "
                "evidence package"
            )

    # PRA ------------------------------------------------------------------
    if not _is_nonempty_dict(pra):
        reasons.append(
            "rfx_missing_pra_evidence: PRA promotion-readiness artifact absent — "
            "certification evidence package incomplete"
        )
    else:
        pra_status = pra.get("status")
        if pra_status != _VALID_PRA_STATUS:
            reasons.append(
                f"rfx_pra_not_ready: PRA status={pra_status!r} is not "
                f"{_VALID_PRA_STATUS!r}"
            )

    # POL ------------------------------------------------------------------
    # Fail closed by default: when the caller does not explicitly declare
    # ``policy_in_scope=False`` the guard treats policy as in scope and
    # requires the policy-posture input. This keeps RT-04 (POL missing while
    # policy is in scope) deterministic regardless of whether the caller
    # passes a POL artifact or omits it.
    pol_required = True if policy_in_scope is None else bool(policy_in_scope)
    if pol_required:
        if not _is_nonempty_dict(pol):
            reasons.append(
                "rfx_missing_pol_evidence: POL policy posture absent while "
                "policy is in scope — certification evidence package incomplete"
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
