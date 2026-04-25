"""RFX GOV certification hard gate — LOOP-06.

Canonical roles for certification packaging, closure, and trust/policy are
recorded in ``docs/architecture/system_registry.md``; this module does not
restate or redefine them. The gate verifies that the full evidence bundle
required for a certification record is present and individually valid before
the canonical certification step may proceed.

Required evidence (fail-closed when missing or invalid):
  - EVL (evaluation evidence)
  - TPA (trust/policy adjudication)
  - CDE (closure decision)
  - SEL (linkage to enforcement record)
  - LIN (lineage record)
  - REP (replay record)
  - OBS (observability/telemetry completeness)
  - SLO (service-level objective posture, when required)
  - PRA (promotion-readiness artifact)
  - POL (policy posture, when policy is in scope)

Required status checks:
  - EVL.status in {"pass", "conditional_pass"}
  - TPA.status in {"accepted", "conditional"}
  - PRA.status == "ready"
  - POL.status in {"active", "canary", "approved"} when policy is in scope

Failure reason codes are deterministic and machine-readable. All failures are
collected and emitted before raising so callers receive a complete picture.
"""

from __future__ import annotations

from typing import Any


class RFXCertificationGateError(ValueError):
    """Raised when the RFX GOV certification hard gate fails closed."""


_EVL_PASSING = frozenset({"pass", "conditional_pass"})
_TPA_PASSING = frozenset({"accepted", "conditional"})
_POL_PASSING = frozenset({"active", "canary", "approved"})
_CDE_VALID = frozenset({"ready", "not_ready"})


def _is_present(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _coerce_status(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _policy_in_scope(pol: dict[str, Any] | None) -> bool:
    """Determine whether POL evidence is required for this RFX run.

    POL is considered in scope when either:
      - the POL record is provided (callers indicate scope by supplying POL), or
      - the POL record carries an explicit ``in_scope`` boolean set to True.
    Callers may also signal "policy not in scope" by passing ``pol=None`` and
    ``slo`` indicating no policy-affecting state — but the safest default is to
    require POL whenever any POL record is supplied.
    """
    if not isinstance(pol, dict):
        return False
    explicit = pol.get("in_scope")
    if isinstance(explicit, bool):
        return explicit
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
) -> None:
    """Assert the RFX GOV certification hard gate.

    Certification may not be issued unless every required artifact is present
    and individually valid. Canonical roles are recorded in
    ``docs/architecture/system_registry.md`` and are not restated here.

    Fails closed by aggregating all reason codes and raising one combined
    :class:`RFXCertificationGateError` with semicolon-separated codes.
    """
    reasons: list[str] = []

    # --- EVL evidence ----------------------------------------------------
    if not _is_present(evl):
        reasons.append(
            "rfx_missing_evl_evidence: EVL evaluation record absent — GOV certification withheld"
        )
    else:
        evl_status = _coerce_status(evl, "status", "evaluation_status")
        if evl_status not in _EVL_PASSING:
            reasons.append(
                f"rfx_missing_evl_evidence: EVL status={evl_status!r} "
                f"not in {sorted(_EVL_PASSING)!r}"
            )

    # --- TPA adjudication ------------------------------------------------
    if not _is_present(tpa):
        reasons.append(
            "rfx_missing_tpa_evidence: TPA adjudication record absent — GOV certification withheld"
        )
    else:
        tpa_status = _coerce_status(tpa, "status", "discipline_status")
        if tpa_status not in _TPA_PASSING:
            reasons.append(
                f"rfx_missing_tpa_evidence: TPA status={tpa_status!r} "
                f"not in {sorted(_TPA_PASSING)!r}"
            )

    # --- CDE closure decision -------------------------------------------
    if not _is_present(cde):
        reasons.append(
            "rfx_missing_cde_decision: CDE closure decision absent — GOV cannot certify"
        )
    else:
        cde_status = _coerce_status(cde, "status")
        if cde_status not in _CDE_VALID:
            reasons.append(
                f"rfx_missing_cde_decision: CDE status={cde_status!r} "
                f"not in {sorted(_CDE_VALID)!r}"
            )

    # --- SEL linkage ----------------------------------------------------
    if not _is_present(sel):
        reasons.append(
            "rfx_missing_sel_link: SEL enforcement linkage absent — GOV cannot certify"
        )
    else:
        link = _coerce_status(sel, "cde_decision_ref", "cde_decision_id", "decision_ref")
        if not isinstance(link, str) or not link.strip():
            reasons.append(
                "rfx_missing_sel_link: SEL record does not reference a CDE decision"
            )

    # --- LIN lineage ----------------------------------------------------
    if not _is_present(lin):
        reasons.append(
            "rfx_missing_lineage: LIN lineage record absent — GOV cannot certify"
        )
    else:
        authenticity = _coerce_status(lin, "authenticity", "authenticity_status")
        if authenticity != "pass":
            reasons.append(
                f"rfx_missing_lineage: lineage authenticity={authenticity!r} not 'pass'"
            )

    # --- REP replay -----------------------------------------------------
    if not _is_present(rep):
        reasons.append(
            "rfx_missing_replay: REP replay record absent — GOV cannot certify"
        )
    else:
        match = _coerce_status(rep, "match", "replay_match")
        if match is not True:
            reasons.append(
                f"rfx_missing_replay: replay match={match!r} is not True"
            )

    # --- OBS telemetry --------------------------------------------------
    if not _is_present(obs):
        reasons.append(
            "rfx_missing_obs: OBS telemetry completeness record absent — GOV cannot certify"
        )
    else:
        obs_completeness = _coerce_status(obs, "completeness", "telemetry_completeness", "status")
        if obs_completeness not in {"pass", "complete", True}:
            reasons.append(
                f"rfx_missing_obs: OBS completeness={obs_completeness!r} not 'pass'/'complete'"
            )

    # --- SLO posture ----------------------------------------------------
    if not _is_present(slo):
        reasons.append(
            "rfx_slo_block: SLO posture record absent — GOV cannot certify"
        )
    else:
        slo_status = _coerce_status(slo, "status", "posture")
        if slo_status not in {"pass", "ok", "within_budget", "acceptable"}:
            reasons.append(
                f"rfx_slo_block: SLO posture={slo_status!r} is not acceptable for progression"
            )

    # --- PRA promotion-readiness ----------------------------------------
    if not _is_present(pra):
        reasons.append(
            "rfx_missing_pra_evidence: PRA promotion-readiness artifact absent — "
            "GOV certification withheld"
        )
    else:
        pra_status = _coerce_status(pra, "status", "promotion_readiness_status")
        if pra_status != "ready":
            reasons.append(
                f"rfx_missing_pra_evidence: PRA status={pra_status!r} is not 'ready'"
            )

    # --- POL policy posture (when in scope) -----------------------------
    if _policy_in_scope(pol):
        assert pol is not None  # for type-checkers; _policy_in_scope guarantees dict
        pol_status = _coerce_status(pol, "status", "policy_posture", "rollout_state")
        if pol_status not in _POL_PASSING:
            reasons.append(
                f"rfx_missing_pol_evidence: POL status={pol_status!r} "
                f"not in {sorted(_POL_PASSING)!r}"
            )
    else:
        # Policy is in scope by default unless the caller explicitly indicates
        # otherwise via ``pol={"in_scope": False, ...}``. A bare ``None`` means
        # the caller has not supplied policy evidence, which is fail-closed
        # whenever policy could affect the RFX path.
        if pol is None:
            reasons.append(
                "rfx_missing_pol_evidence: POL policy posture absent — "
                "policy in scope by default; supply POL or set in_scope=False explicitly"
            )

    if reasons:
        raise RFXCertificationGateError("; ".join(reasons))


__all__ = [
    "RFXCertificationGateError",
    "assert_rfx_certification_ready",
]
