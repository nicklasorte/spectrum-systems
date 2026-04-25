"""RFX LOOP-04 → LOOP-06 red-team campaign (RT-01..RT-06).

Each red-team scenario must:
  - fail deterministically
  - emit machine-readable reason codes
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_certification_gate import (
    RFXCertificationGateError,
    assert_rfx_certification_ready,
)
from spectrum_systems.modules.runtime.rfx_decision_bridge_guard import (
    RFXDecisionBridgeGuardError,
    assert_rfx_cde_sel_decision_bridge,
)
from spectrum_systems.modules.runtime.rfx_integrity_bundle import (
    RFXIntegrityBundleError,
    assert_rfx_integrity_bundle,
)


_EVL = {"eval_id": "evl-rt", "status": "pass"}
_TPA = {"tpa_decision_id": "tpa-rt", "status": "accepted"}
_CDE = {"decision_id": "cde-rt", "status": "ready"}
_SEL = {"sel_record_id": "sel-rt", "cde_decision_ref": "cde-rt"}
_LIN = {"lineage_id": "lin-rt", "authenticity": "pass"}
_REP = {"replay_id": "rep-rt", "match": True}
_OBS = {"obs_id": "obs-rt", "completeness": "pass"}
_SLO = {"slo_id": "slo-rt", "status": "within_budget"}
_PRA = {"pra_id": "pra-rt", "status": "ready"}
_POL = {"pol_id": "pol-rt", "status": "active", "in_scope": True}


def _full_kwargs(**overrides):
    base = dict(
        evl=_EVL, tpa=_TPA, cde=_CDE, sel=_SEL,
        lin=_LIN, rep=_REP, obs=_OBS, slo=_SLO,
        pra=_PRA, pol=_POL,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# RT-01: CDE decision missing → ensure SEL blocked
# ---------------------------------------------------------------------------

def test_rt01_missing_cde_decision_blocks_sel() -> None:
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=None, sel_context=_SEL)


def test_rt01_certification_blocks_when_cde_missing() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_cde_decision"):
        assert_rfx_certification_ready(**_full_kwargs(cde=None))


# ---------------------------------------------------------------------------
# RT-02: Replay mismatch → ensure freeze/block
# ---------------------------------------------------------------------------

def test_rt02_replay_mismatch_freezes_integrity_bundle() -> None:
    mismatch = {**_REP, "match": False}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
        assert_rfx_integrity_bundle(lineage_record=_LIN, replay_record=mismatch)


def test_rt02_replay_mismatch_blocks_certification() -> None:
    mismatch = {**_REP, "match": False}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_replay"):
        assert_rfx_certification_ready(**_full_kwargs(rep=mismatch))


# ---------------------------------------------------------------------------
# RT-03: PRA missing → ensure GOV blocked
# ---------------------------------------------------------------------------

def test_rt03_missing_pra_blocks_gov() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pra_evidence"):
        assert_rfx_certification_ready(**_full_kwargs(pra=None))


def test_rt03_pra_pending_blocks_gov() -> None:
    pending = {**_PRA, "status": "pending"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pra_evidence"):
        assert_rfx_certification_ready(**_full_kwargs(pra=pending))


# ---------------------------------------------------------------------------
# RT-04: POL missing (policy in scope) → ensure GOV blocked
# ---------------------------------------------------------------------------

def test_rt04_missing_pol_when_policy_in_scope_blocks_gov() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
        assert_rfx_certification_ready(**_full_kwargs(pol=None))


def test_rt04_pol_invalid_rollout_state_blocks_gov() -> None:
    bad = {**_POL, "status": "rolled_back"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
        assert_rfx_certification_ready(**_full_kwargs(pol=bad))


# ---------------------------------------------------------------------------
# RT-05: Fake CDE decision without linkage → blocked
# ---------------------------------------------------------------------------

def test_rt05_fake_cde_decision_without_sel_linkage_blocks_bridge() -> None:
    fake_sel = {"sel_record_id": "sel-rt-fake", "enforcement_action": "allow"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=_CDE, sel_context=fake_sel)


def test_rt05_fake_cde_decision_with_mismatched_sel_link_blocks_bridge() -> None:
    fake_sel = {"sel_record_id": "sel-rt-fake", "cde_decision_ref": "cde-other-impostor"}
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=_CDE, sel_context=fake_sel)


def test_rt05_unidentified_cde_decision_rejected() -> None:
    """A fake CDE record without an identifier cannot anchor SEL linkage."""
    unidentified = {"status": "ready"}  # no decision_id
    with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_invalid_cde_decision"):
        assert_rfx_cde_sel_decision_bridge(cde_decision=unidentified, sel_context=_SEL)


# ---------------------------------------------------------------------------
# RT-06: All valid → pass
# ---------------------------------------------------------------------------

def test_rt06_full_valid_flow_passes_all_three_guards() -> None:
    # LOOP-04
    assert_rfx_cde_sel_decision_bridge(cde_decision=_CDE, sel_context=_SEL)
    # LOOP-05
    assert_rfx_integrity_bundle(lineage_record=_LIN, replay_record=_REP)
    # LOOP-06
    assert_rfx_certification_ready(**_full_kwargs())
