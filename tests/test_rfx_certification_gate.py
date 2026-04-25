"""Tests for the RFX GOV certification hard gate (LOOP-06)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_certification_gate import (
    RFXCertificationGateError,
    assert_rfx_certification_ready,
)


_EVL = {"eval_id": "evl-rfx-001", "status": "pass"}
_TPA = {"tpa_decision_id": "tpa-rfx-001", "status": "accepted"}
_CDE = {"decision_id": "cde-rfx-001", "status": "ready"}
_SEL = {"sel_record_id": "sel-rfx-001", "cde_decision_ref": "cde-rfx-001"}
_LIN = {"lineage_id": "lin-rfx-001", "authenticity": "pass"}
_REP = {"replay_id": "rep-rfx-001", "match": True}
_OBS = {"obs_id": "obs-rfx-001", "completeness": "pass"}
_SLO = {"slo_id": "slo-rfx-001", "status": "within_budget"}
_PRA = {"pra_id": "pra-rfx-001", "status": "ready"}
_POL = {"pol_id": "pol-rfx-001", "status": "active", "in_scope": True}


def _kwargs(**overrides):
    base = dict(
        evl=_EVL, tpa=_TPA, cde=_CDE, sel=_SEL,
        lin=_LIN, rep=_REP, obs=_OBS, slo=_SLO,
        pra=_PRA, pol=_POL,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Each missing artifact → block
# ---------------------------------------------------------------------------

def test_missing_evl_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_evl_evidence"):
        assert_rfx_certification_ready(**_kwargs(evl=None))


def test_evl_failing_status_blocks_certification() -> None:
    failing = {**_EVL, "status": "fail"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_evl_evidence"):
        assert_rfx_certification_ready(**_kwargs(evl=failing))


def test_missing_tpa_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_tpa_evidence"):
        assert_rfx_certification_ready(**_kwargs(tpa=None))


def test_tpa_blocked_status_blocks_certification() -> None:
    blocked = {**_TPA, "status": "blocked"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_tpa_evidence"):
        assert_rfx_certification_ready(**_kwargs(tpa=blocked))


def test_missing_cde_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_cde_decision"):
        assert_rfx_certification_ready(**_kwargs(cde=None))


def test_cde_invalid_status_blocks_certification() -> None:
    bad = {**_CDE, "status": "in_progress"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_cde_decision"):
        assert_rfx_certification_ready(**_kwargs(cde=bad))


def test_missing_sel_link_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_sel_link"):
        assert_rfx_certification_ready(**_kwargs(sel=None))


def test_sel_without_link_blocks_certification() -> None:
    unlinked = {"sel_record_id": "sel-rfx-001"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_sel_link"):
        assert_rfx_certification_ready(**_kwargs(sel=unlinked))


def test_missing_lineage_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_lineage"):
        assert_rfx_certification_ready(**_kwargs(lin=None))


def test_lineage_not_authentic_blocks_certification() -> None:
    bad = {**_LIN, "authenticity": "fail"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_lineage"):
        assert_rfx_certification_ready(**_kwargs(lin=bad))


def test_missing_replay_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_replay"):
        assert_rfx_certification_ready(**_kwargs(rep=None))


def test_replay_mismatch_blocks_certification() -> None:
    bad = {**_REP, "match": False}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_replay"):
        assert_rfx_certification_ready(**_kwargs(rep=bad))


def test_missing_obs_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_obs"):
        assert_rfx_certification_ready(**_kwargs(obs=None))


def test_obs_incomplete_blocks_certification() -> None:
    bad = {**_OBS, "completeness": "incomplete"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_obs"):
        assert_rfx_certification_ready(**_kwargs(obs=bad))


def test_missing_slo_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_slo_block"):
        assert_rfx_certification_ready(**_kwargs(slo=None))


def test_slo_burning_blocks_certification() -> None:
    bad = {**_SLO, "status": "over_budget"}
    with pytest.raises(RFXCertificationGateError, match="rfx_slo_block"):
        assert_rfx_certification_ready(**_kwargs(slo=bad))


# ---------------------------------------------------------------------------
# PRA / POL specific checks
# ---------------------------------------------------------------------------

def test_missing_pra_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pra_evidence"):
        assert_rfx_certification_ready(**_kwargs(pra=None))


def test_pra_not_ready_blocks_certification() -> None:
    pending = {**_PRA, "status": "pending"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pra_evidence"):
        assert_rfx_certification_ready(**_kwargs(pra=pending))


def test_missing_pol_when_in_scope_blocks_certification() -> None:
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
        assert_rfx_certification_ready(**_kwargs(pol=None))


def test_pol_invalid_status_blocks_certification() -> None:
    bad = {**_POL, "status": "deprecated"}
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
        assert_rfx_certification_ready(**_kwargs(pol=bad))


def test_pol_canary_status_passes() -> None:
    canary = {**_POL, "status": "canary"}
    # Must not raise
    assert_rfx_certification_ready(**_kwargs(pol=canary))


def test_pol_approved_status_passes() -> None:
    approved = {**_POL, "status": "approved"}
    # Must not raise
    assert_rfx_certification_ready(**_kwargs(pol=approved))


def test_pol_explicitly_out_of_scope_passes() -> None:
    out_of_scope = {"pol_id": "pol-noop", "in_scope": False}
    # Must not raise — caller has explicitly indicated policy is not in scope.
    assert_rfx_certification_ready(**_kwargs(pol=out_of_scope))


# ---------------------------------------------------------------------------
# Aggregated failures
# ---------------------------------------------------------------------------

def test_all_missing_aggregates_all_reason_codes() -> None:
    with pytest.raises(RFXCertificationGateError) as exc_info:
        assert_rfx_certification_ready(
            evl=None, tpa=None, cde=None, sel=None,
            lin=None, rep=None, obs=None, slo=None,
            pra=None, pol=None,
        )
    msg = str(exc_info.value)
    for code in (
        "rfx_missing_evl_evidence",
        "rfx_missing_tpa_evidence",
        "rfx_missing_cde_decision",
        "rfx_missing_sel_link",
        "rfx_missing_lineage",
        "rfx_missing_replay",
        "rfx_missing_obs",
        "rfx_slo_block",
        "rfx_missing_pra_evidence",
        "rfx_missing_pol_evidence",
    ):
        assert code in msg, f"expected reason code {code!r} in aggregated failure"


# ---------------------------------------------------------------------------
# Valid full set
# ---------------------------------------------------------------------------

def test_valid_full_evidence_set_passes() -> None:
    # Must not raise
    assert_rfx_certification_ready(**_kwargs())


def test_conditional_pass_evl_passes() -> None:
    cond = {**_EVL, "status": "conditional_pass"}
    # Must not raise
    assert_rfx_certification_ready(**_kwargs(evl=cond))


def test_conditional_tpa_passes() -> None:
    cond = {**_TPA, "status": "conditional"}
    # Must not raise
    assert_rfx_certification_ready(**_kwargs(tpa=cond))
