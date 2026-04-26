"""RFX flow integration helper — wires LOOP-01..LOOP-08 guards in order.

RFX path (canonical):

    RIL → FRE → PQX → EVL → TPA → CDE
        → assert_rfx_cde_sel_decision_bridge   (LOOP-04)
        → assert_rfx_integrity_bundle          (LOOP-05)
        → assert_rfx_certification_ready       (LOOP-06)
        → assert_rfx_reliability_posture       (LOOP-07)
        → assert_rfx_telemetry_slo_eligible    (LOOP-08)
        → assert_rfx_observability_replay_consistency  (OBS+REP cross-check)
        → assert_rfx_adversarial_reliability_guard     (anti-gaming guard)
        → SEL enforcement step
        → GOV certification record

This module composes the existing guards as a non-owning phase-label support
helper. It does not introduce or redefine roles; canonical roles are recorded
in ``docs/architecture/system_registry.md``.

LOOP-07 / LOOP-08 / OBS+REP / anti-gaming inputs are optional kwargs on
:func:`assert_rfx_promotion_ready` so existing LOOP-01..LOOP-06 callers keep
working. Callers that supply ``recent_failures`` / ``replay_results`` /
``window_seconds`` activate LOOP-07; LOOP-08 always runs when both OBS and
SLO are present (they are required by LOOP-06 anyway).
"""

from __future__ import annotations

from typing import Any

from spectrum_systems.modules.runtime.rfx_adversarial_reliability_guard import (
    assert_rfx_adversarial_reliability_guard,
)
from spectrum_systems.modules.runtime.rfx_certification_gate import (
    assert_rfx_certification_ready,
)
from spectrum_systems.modules.runtime.rfx_decision_bridge_guard import (
    assert_rfx_cde_sel_decision_bridge,
)
from spectrum_systems.modules.runtime.rfx_failure_profile import (
    RFXFailureProfileThresholds,
)
from spectrum_systems.modules.runtime.rfx_integrity_bundle import (
    assert_rfx_integrity_bundle,
)
from spectrum_systems.modules.runtime.rfx_observability_replay_consistency import (
    assert_rfx_observability_replay_consistency,
)
from spectrum_systems.modules.runtime.rfx_reliability_freeze import (
    assert_rfx_reliability_posture,
)
from spectrum_systems.modules.runtime.rfx_route_guard import (
    assert_rfx_aex_admission_present,
    assert_rfx_evl_tpa_evidence_present,
    assert_rfx_pqx_lineage_present,
)
from spectrum_systems.modules.runtime.rfx_telemetry_slo_gate import (
    assert_rfx_telemetry_slo_eligible,
)


def assert_rfx_promotion_ready(
    *,
    route_artifact: dict[str, Any] | None,
    build_admission_record: dict[str, Any] | None,
    tlc_handoff_record: dict[str, Any] | None,
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
    recent_failures: list[dict[str, Any]] | None = None,
    replay_results: list[dict[str, Any]] | None = None,
    window_seconds: int | None = None,
    reliability_thresholds: RFXFailureProfileThresholds | None = None,
    enforce_loop07: bool | None = None,
    enforce_loop08: bool | None = None,
    enforce_obs_rep_consistency: bool | None = None,
    enforce_anti_gaming: bool | None = None,
) -> None:
    """Run all RFX guards in canonical order, fail-closed at the first break.

    LOOP-01..LOOP-03 ensure routing/admission/lineage and EVL+TPA evidence.
    LOOP-04 bridges CDE → SEL. LOOP-05 enforces LIN+REP integrity. LOOP-06
    enforces the GOV certification hard gate including PRA and POL.
    LOOP-07 enforces the reliability-freeze guard (instability, replay drift,
    burst/recurring failures, increasing failure trend). LOOP-08 enforces
    telemetry-derived SLO eligibility, the OBS+REP consistency cross-check,
    and the adversarial-reliability anti-gaming guard.

    LOOP-07/08 inputs are activated when ``recent_failures``,
    ``replay_results``, and ``window_seconds`` are supplied or when the
    explicit ``enforce_loop07`` / ``enforce_loop08`` flags are set. The
    OBS+REP consistency and anti-gaming guards default-on whenever telemetry
    inputs are supplied, and can be opted into / out of explicitly.

    No path may reach GOV certification packaging without passing every guard.
    """
    # LOOP-01 / LOOP-02: AEX admission + TLC route lineage
    assert_rfx_aex_admission_present(
        route_artifact=route_artifact,
        build_admission_record=build_admission_record,
    )
    assert_rfx_pqx_lineage_present(
        route_artifact=route_artifact,
        tlc_handoff_record=tlc_handoff_record,
    )

    # LOOP-03: EVL + TPA evidence before CDE/SEL progression
    assert_rfx_evl_tpa_evidence_present(evl_evidence=evl, tpa_evidence=tpa)

    # LOOP-04: CDE → SEL decision bridge
    assert_rfx_cde_sel_decision_bridge(cde_decision=cde, sel_context=sel)

    # LOOP-05: LIN + REP integrity bundle
    assert_rfx_integrity_bundle(lineage_record=lin, replay_record=rep)

    # LOOP-06: GOV certification hard gate (includes PRA + POL)
    assert_rfx_certification_ready(
        evl=evl, tpa=tpa, cde=cde, sel=sel,
        lin=lin, rep=rep, obs=obs, slo=slo,
        pra=pra, pol=pol,
    )

    # LOOP-07: reliability freeze guard. Auto-activates only when the caller
    # supplies inputs that actually require a time window — ``recent_failures``
    # or ``window_seconds``. ``replay_results`` alone is part of the OBS+REP
    # consistency surface and does NOT auto-enable LOOP-07, so callers who
    # only want LOOP-08 + OBS/REP can supply replay rows without being
    # hard-blocked on a missing window. Explicit ``enforce_loop07=True`` still
    # forces activation (and still requires ``window_seconds``).
    activate_loop07 = (
        enforce_loop07
        if enforce_loop07 is not None
        else (recent_failures is not None or window_seconds is not None)
    )
    if activate_loop07:
        if window_seconds is None:
            # Without a window we cannot evaluate density, slope, or rate —
            # fail closed rather than guess. Match
            # ``assert_rfx_reliability_posture``'s contract by attaching a
            # freeze propagation record so callers that inspect
            # ``exc.freeze_record`` still receive deterministic
            # PQX/CDE/GOV/SEL freeze signals.
            from spectrum_systems.modules.runtime.rfx_freeze_propagation import (
                propagate_rfx_freeze,
            )
            from spectrum_systems.modules.runtime.rfx_reliability_freeze import (
                RFXReliabilityFreezeError,
            )
            reason = (
                "rfx_reliability_state_unknown: window_seconds is required "
                "when LOOP-07 reliability evidence is supplied"
            )
            raise RFXReliabilityFreezeError(
                reason,
                freeze_record=propagate_rfx_freeze(
                    reason_codes=["rfx_reliability_state_unknown"],
                    downstream_targets=[],
                ),
            )
        assert_rfx_reliability_posture(
            recent_failures=recent_failures,
            replay_results=replay_results,
            window_seconds=window_seconds,
            slo=slo,
            thresholds=reliability_thresholds,
        )

    # LOOP-08: telemetry-enforced SLO eligibility. Default-on whenever both
    # OBS and SLO are present (LOOP-06 already requires both, so this fires
    # on every promotion path). The strict OBS-field invariants
    # (trace_id / execution_path_coverage / artifact_linkage / failure_logs)
    # and the SLO-derived-from-OBS cross-check are stricter than LOOP-06's
    # OBS completeness check, and per PRD must enforce on every promotion —
    # not only when LOOP-07 telemetry evidence is supplied.
    activate_loop08 = (
        enforce_loop08
        if enforce_loop08 is not None
        else bool(obs) and bool(slo)
    )
    if activate_loop08:
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=slo)

    # OBS + REP cross-consistency. Default-on whenever both OBS and a replay
    # corpus are supplied; the cross-check requires both halves and runs
    # independently of LOOP-07 activation so a caller that explicitly opts
    # into LOOP-08 (without LOOP-07 telemetry) still gets replay coverage.
    activate_obs_rep = (
        enforce_obs_rep_consistency
        if enforce_obs_rep_consistency is not None
        else (replay_results is not None and obs is not None)
    )
    if activate_obs_rep:
        assert_rfx_observability_replay_consistency(
            obs=obs, replay_results=replay_results
        )

    # Anti-gaming guard. Default-on whenever OBS or SLO is present so SLO
    # ok-band claims with no OBS evidence (or with suppressed failure
    # signals) are caught regardless of LOOP-07 activation.
    activate_anti_gaming = (
        enforce_anti_gaming
        if enforce_anti_gaming is not None
        else (obs is not None or slo is not None)
    )
    if activate_anti_gaming:
        assert_rfx_adversarial_reliability_guard(
            recent_failures=recent_failures,
            replay_results=replay_results,
            obs=obs,
            slo=slo,
        )


__all__ = ["assert_rfx_promotion_ready"]
