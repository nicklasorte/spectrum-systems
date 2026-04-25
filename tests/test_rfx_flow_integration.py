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
_OBS = {"obs_id": "obs-flow-001", "completeness": "pass"}
_SLO = {"slo_id": "slo-flow-001", "status": "within_budget"}
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


def test_flow_blocks_when_aex_admission_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_aex_admission"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, build_admission_record=None))


def test_flow_blocks_when_tlc_handoff_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_pqx_direct_invocation_blocked"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, tlc_handoff_record=None))


def test_flow_blocks_when_evl_evidence_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXRouteGuardError, match="rfx_missing_evl_evidence"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, evl=None))


def test_flow_blocks_when_cde_decision_absent(route_artifact: dict) -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
        assert_rfx_promotion_ready(**_full_kwargs(route_artifact, cde=None))


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
