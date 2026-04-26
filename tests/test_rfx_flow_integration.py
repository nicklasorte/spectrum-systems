"""End-to-end test that the RFX flow runs LOOP-01..LOOP-06 in order.

Verifies that no path can reach GOV certification packaging without passing
every guard, and that a valid full bundle proceeds without raising.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_certification_gate import (
    RFXCertificationGateError,
)
from spectrum_systems.modules.runtime.rfx_decision_bridge_guard import (
    RFXDecisionBridgeGuardError,
)
from spectrum_systems.modules.runtime.rfx_flow_integration import (
    assert_rfx_promotion_ready,
)
from spectrum_systems.modules.runtime.rfx_integrity_bundle import (
    RFXIntegrityBundleError,
)
from spectrum_systems.modules.runtime.rfx_route_guard import (
    RFXRouteGuardError,
    build_rfx_tlc_route_artifact,
)


_FULL_RFX_PATH = ["AEX", "RIL", "FRE", "PQX", "EVL", "TPA", "CDE", "SEL", "GOV"]

_ADMISSION = {
    "admission_id": "aex-rfx-flow-001",
    "admission_status": "accepted",
    "execution_type": "repo_write",
}

_HANDOFF = {
    "handoff_id": "tlc-handoff-flow-001",
    "handoff_status": "accepted",
    "target_subsystems": ["TPA", "PQX"],
}

_EVL = {"eval_id": "evl-flow-001", "evaluation_status": "pass"}
_TPA = {"tpa_decision_id": "tpa-flow-001", "discipline_status": "accepted"}
_CDE = {"decision_id": "cde-flow-001", "status": "ready"}
_SEL = {"sel_record_id": "sel-flow-001", "cde_decision_ref": "cde-flow-001"}
_LIN = {"lineage_id": "lin-flow-001", "authenticity": "pass"}
_REP = {"replay_id": "rep-flow-001", "match": True}
# OBS must satisfy LOOP-08 invariants (trace_id, execution_path_coverage,
# artifact_linkage, failure_logs) since LOOP-08 fires on every promotion
# whenever both OBS and SLO are present. SLO must declare its OBS source
# so the rfx_slo_inconsistent_with_obs cross-check passes.
_OBS = {
    "obs_id": "obs-flow-001",
    "trace_id": "trace-flow-001",
    "execution_path_coverage": ["AEX", "PQX", "EVL", "TPA", "CDE", "SEL"],
    "artifact_linkage": ["lin:flow-001", "rep:flow-001"],
    "failure_logs": [],
    "completeness": "pass",
}
_SLO = {"slo_id": "slo-flow-001", "status": "within_budget", "obs_ref": "obs-flow-001"}
_PRA = {"pra_id": "pra-flow-001", "status": "ready"}
_POL = {"pol_id": "pol-flow-001", "status": "active", "in_scope": True}


@pytest.fixture
def route_artifact() -> dict:
    return build_rfx_tlc_route_artifact(
        run_id="rfx-flow-001",
        trace_id="trace-rfx-flow-001",
        aex_admission_id=_ADMISSION["admission_id"],
        intended_path=_FULL_RFX_PATH,
        created_at="2026-04-25T00:00:00Z",
    )


def _full_kwargs(route_artifact: dict, **overrides):
    base = dict(
        route_artifact=route_artifact,
        build_admission_record=_ADMISSION,
        tlc_handoff_record=_HANDOFF,
        evl=_EVL, tpa=_TPA,
        cde=_CDE, sel=_SEL,
        lin=_LIN, rep=_REP,
        obs=_OBS, slo=_SLO,
        pra=_PRA, pol=_POL,
    )
    base.update(overrides)
    return base


def test_full_valid_rfx_flow_passes(route_artifact: dict) -> None:
    # Must not raise
    assert_rfx_promotion_ready(**_full_kwargs(route_artifact))


def test_flow_accepts_unified_status_key_for_evl_and_tpa(route_artifact: dict) -> None:
    """Producers using the LOOP-06-unified ``status`` key must flow through LOOP-03."""
    evl_unified = {"eval_id": "evl-flow-unified", "status": "pass"}
    tpa_unified = {"tpa_decision_id": "tpa-flow-unified", "status": "accepted"}
    # Must not raise
    assert_rfx_promotion_ready(**_full_kwargs(route_artifact, evl=evl_unified, tpa=tpa_unified))


def test_flow_accepts_loop04_sel_alias_through_loop06(route_artifact: dict) -> None:
    """A SEL record using the LOOP-04 alias ``linked_cde_decision_id`` must
    pass both the bridge guard and the certification gate."""
    sel_alias = {
        "sel_record_id": "sel-flow-001",
        "linked_cde_decision_id": "cde-flow-001",
    }
    # Must not raise — alias is accepted by both LOOP-04 and LOOP-06.
    assert_rfx_promotion_ready(**_full_kwargs(route_artifact, sel=sel_alias))


def test_flow_accepts_loop05_replay_alias_through_loop06(route_artifact: dict) -> None:
    """A replay record using the LOOP-05 ``matches`` key must pass both
    the integrity bundle and the certification gate."""
    rep_alias = {"replay_id": "rep-flow-001", "matches": True}
    # Must not raise.
    assert_rfx_promotion_ready(**_full_kwargs(route_artifact, rep=rep_alias))


def test_flow_accepts_loop05_lineage_alias_through_loop06(route_artifact: dict) -> None:
    """A lineage record using the LOOP-05 ``authenticity_result`` alias must
    pass both the integrity bundle and the certification gate."""
    lin_alias = {"lineage_id": "lin-flow-001", "authenticity_result": "pass"}
    # Must not raise.
    assert_rfx_promotion_ready(**_full_kwargs(route_artifact, lin=lin_alias))


def test_flow_blocks_when_aex_admission_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, build_admission_record=None))


def test_flow_blocks_when_route_artifact_is_none() -> None:
    """Malformed entry — None route_artifact must produce a deterministic
    guard error, not crash."""
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_promotion_ready(
            route_artifact=None,
            build_admission_record=_ADMISSION,
            tlc_handoff_record=_HANDOFF,
            evl=_EVL, tpa=_TPA, cde=_CDE, sel=_SEL,
            lin=_LIN, rep=_REP, obs=_OBS, slo=_SLO,
            pra=_PRA, pol=_POL,
        )


@pytest.mark.parametrize("malformed", [[1], "route-string", 42, ("a",)])
def test_flow_blocks_when_route_artifact_is_non_dict(malformed) -> None:
    """A non-dict route_artifact must fail closed at the integration entry
    point with a deterministic guard error, not an AttributeError."""
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_promotion_ready(
            route_artifact=malformed,
            build_admission_record=_ADMISSION,
            tlc_handoff_record=_HANDOFF,
            evl=_EVL, tpa=_TPA, cde=_CDE, sel=_SEL,
            lin=_LIN, rep=_REP, obs=_OBS, slo=_SLO,
            pra=_PRA, pol=_POL,
        )


def test_flow_blocks_when_tlc_handoff_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, tlc_handoff_record=None))


def test_flow_blocks_when_evl_evidence_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_evl_evidence"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, evl=None))


def test_flow_blocks_when_cde_decision_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, cde=None))


def test_flow_blocks_when_cde_decision_is_not_ready(route_artifact: dict) -> None:
    """``not_ready`` passes the LOOP-04 bridge but must block the LOOP-06 gate."""
    not_ready = {**_CDE, "status": "not_ready"}
    with pytest.raises(RFXCertificationGateError, match="rfx_cde_decision_not_ready"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, cde=not_ready))


def test_flow_blocks_when_sel_unlinked(route_artifact: dict) -> None:
    fake_sel = {"sel_record_id": "sel-fake", "enforcement_action": "allow"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, sel=fake_sel))


def test_flow_blocks_when_replay_mismatch(route_artifact: dict) -> None:
    mismatch = {**_REP, "match": False}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, rep=mismatch))


def test_flow_blocks_when_lineage_not_authentic(route_artifact: dict) -> None:
    bad = {**_LIN, "authenticity": "fail"}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_lineage_not_authentic"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, lin=bad))


def test_flow_blocks_when_pra_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pra_evidence"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, pra=None))


def test_flow_blocks_when_pol_absent_in_scope(route_artifact: dict) -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, pol=None))


def test_flow_blocks_when_obs_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_obs"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, obs=None))


def test_flow_blocks_when_slo_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_slo_block"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, slo=None))


# ---------------------------------------------------------------------------
# LOOP-08 default-on: a no-telemetry promotion call must still fire the
# strict OBS-field invariants (regression coverage for Codex P1 finding —
# previously LOOP-08 was gated behind LOOP-07 activation, so a normal
# LOOP-06 promotion path could pass with incomplete OBS fields).
# ---------------------------------------------------------------------------


def test_loop08_fires_without_telemetry_inputs_when_obs_missing_trace_id(route_artifact: dict) -> None:
    from spectrum_systems.modules.runtime.rfx_telemetry_slo_gate import (
        RFXTelemetrySLOError,
    )
    obs_partial = {k: v for k, v in _OBS.items() if k != "trace_id"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, obs=obs_partial))


def test_loop08_fires_when_slo_does_not_declare_obs_source(route_artifact: dict) -> None:
    from spectrum_systems.modules.runtime.rfx_telemetry_slo_gate import (
        RFXTelemetrySLOError,
    )
    independent_slo = {"slo_id": "slo-flow-001", "status": "within_budget"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, slo=independent_slo))


def test_anti_gaming_fires_without_telemetry_inputs_when_obs_logs_inconsistent(
    route_artifact: dict,
) -> None:
    """Anti-gaming guard must catch suppressed signals on the legacy promotion
    path (no recent_failures supplied, but OBS shows failure logs)."""
    from spectrum_systems.modules.runtime.rfx_adversarial_reliability_guard import (
        RFXAdversarialReliabilityError,
    )
    obs_with_logs = {**_OBS, "failure_logs": [{"reason": "drift"}]}
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_suspicious_signal_suppression"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, obs=obs_with_logs))


def test_replay_results_alone_does_not_auto_enable_loop07(route_artifact: dict) -> None:
    """Codex P2 regression: supplying replay_results without window_seconds
    must not auto-enable LOOP-07 (which would hard-block on the missing
    window). The OBS+REP consistency path remains reachable for callers
    who only want LOOP-08 + replay-coverage validation."""
    replays = [{"trace_id": "trace-flow-001", "match": True}]
    # Must not raise — replay_results alone keeps LOOP-07 inactive while
    # LOOP-08 + OBS/REP consistency still run.
    assert_rfx_promotion_ready(**_full_kwargs(route_artifact, replay_results=replays))


def test_recent_failures_alone_still_auto_enables_loop07_and_requires_window(
    route_artifact: dict,
) -> None:
    """Counterpart guarantee: ``recent_failures`` is a reliability-evidence
    input, so it auto-enables LOOP-07 and the missing-window block fires."""
    from spectrum_systems.modules.runtime.rfx_reliability_freeze import (
        RFXReliabilityFreezeError,
    )
    failures = [{"timestamp_seconds": 5.0, "reason_code": "x"}]
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_reliability_state_unknown"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, recent_failures=failures))
