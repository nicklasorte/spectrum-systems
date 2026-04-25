"""Tests for RFX LOOP-04, LOOP-05, LOOP-06 gates and RT campaign.

LOOP-04: CDE -> SEL decision bridge guard.
LOOP-05: LIN + REP integrity bundle.
LOOP-06: GOV certification hard gate (EVL+TPA+CDE+SEL+LIN+REP+OBS+SLO+PRA+POL).

The red-team campaign (RT-01..RT-06) verifies fail-closed behavior end-to-end.
"""
from __future__ import annotations

from typing import Any

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


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CDE_READY: dict[str, Any] = {
    "decision_id": "cde-rfx-001",
    "status": "ready",
    "rationale": "All upstream evidence valid",
}

_SEL_LINKED: dict[str, Any] = {
    "enforcement_id": "sel-rfx-001",
    "cde_decision_ref": "cde_decision:cde-rfx-001",
    "action": "allow",
}

_LIN_VALID: dict[str, Any] = {
    "lineage_id": "lin-rfx-001",
    "authenticity": "pass",
}

_REP_VALID: dict[str, Any] = {
    "replay_id": "rep-rfx-001",
    "match": True,
}

_EVL_PASS: dict[str, Any] = {
    "eval_id": "evl-rfx-001",
    "status": "pass",
}

_TPA_ACCEPTED: dict[str, Any] = {
    "tpa_decision_id": "tpa-rfx-001",
    "status": "accepted",
}

_OBS_COMPLETE: dict[str, Any] = {
    "trace_id": "obs-rfx-001",
    "telemetry_complete": True,
}

_SLO_OK: dict[str, Any] = {
    "slo_id": "slo-rfx-001",
    "status": "ok",
}

_PRA_READY: dict[str, Any] = {
    "pra_id": "pra-rfx-001",
    "status": "ready",
}

_POL_ACTIVE: dict[str, Any] = {
    "pol_id": "pol-rfx-001",
    "status": "active",
    "policy_in_scope": True,
}


def _full_evidence_kwargs() -> dict[str, Any]:
    return {
        "evl": dict(_EVL_PASS),
        "tpa": dict(_TPA_ACCEPTED),
        "cde": dict(_CDE_READY),
        "sel": dict(_SEL_LINKED),
        "lin": dict(_LIN_VALID),
        "rep": dict(_REP_VALID),
        "obs": dict(_OBS_COMPLETE),
        "slo": dict(_SLO_OK),
        "pra": dict(_PRA_READY),
        "pol": dict(_POL_ACTIVE),
    }


# ---------------------------------------------------------------------------
# LOOP-04: CDE -> SEL decision bridge
# ---------------------------------------------------------------------------

class TestLoop04DecisionBridge:
    def test_cde_absent_blocks(self) -> None:
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision=None, sel_context=_SEL_LINKED
            )

    def test_cde_empty_blocks(self) -> None:
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision={}, sel_context=_SEL_LINKED
            )

    def test_cde_invalid_status_blocks(self) -> None:
        bad = {**_CDE_READY, "status": "maybe"}
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_invalid_cde_decision"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision=bad, sel_context=_SEL_LINKED
            )

    def test_sel_context_absent_blocks(self) -> None:
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_sel_context"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision=_CDE_READY, sel_context=None
            )

    def test_sel_not_linked_blocks(self) -> None:
        unlinked = {"enforcement_id": "sel-x", "action": "allow"}
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision=_CDE_READY, sel_context=unlinked
            )

    def test_sel_linked_by_id_passes(self) -> None:
        linked_by_id = {
            "enforcement_id": "sel-y",
            "cde_decision_id": "cde-rfx-001",
            "action": "allow",
        }
        # Must not raise
        assert_rfx_cde_sel_decision_bridge(
            cde_decision=_CDE_READY, sel_context=linked_by_id
        )

    def test_valid_chain_passes(self) -> None:
        # Must not raise
        assert_rfx_cde_sel_decision_bridge(
            cde_decision=_CDE_READY, sel_context=_SEL_LINKED
        )

    def test_not_ready_status_is_valid_decision(self) -> None:
        not_ready = {**_CDE_READY, "status": "not_ready"}
        # Must not raise — both ready and not_ready are explicit decisions
        assert_rfx_cde_sel_decision_bridge(
            cde_decision=not_ready, sel_context=_SEL_LINKED
        )


# ---------------------------------------------------------------------------
# LOOP-05: LIN + REP integrity bundle
# ---------------------------------------------------------------------------

class TestLoop05IntegrityBundle:
    def test_missing_lineage_blocks(self) -> None:
        with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_lineage"):
            assert_rfx_integrity_bundle(
                lineage_record=None, replay_record=_REP_VALID
            )

    def test_empty_lineage_blocks(self) -> None:
        with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_lineage"):
            assert_rfx_integrity_bundle(
                lineage_record={}, replay_record=_REP_VALID
            )

    def test_broken_lineage_authenticity_blocks(self) -> None:
        broken = {**_LIN_VALID, "authenticity": "fail"}
        with pytest.raises(RFXIntegrityBundleError, match="rfx_lineage_not_authentic"):
            assert_rfx_integrity_bundle(
                lineage_record=broken, replay_record=_REP_VALID
            )

    def test_missing_replay_blocks(self) -> None:
        with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_replay"):
            assert_rfx_integrity_bundle(
                lineage_record=_LIN_VALID, replay_record=None
            )

    def test_replay_mismatch_blocks(self) -> None:
        mismatched = {**_REP_VALID, "match": False}
        with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
            assert_rfx_integrity_bundle(
                lineage_record=_LIN_VALID, replay_record=mismatched
            )

    def test_replay_truthy_nonbool_still_blocks(self) -> None:
        # match must be strictly True. Truthy strings should not pass.
        truthy = {**_REP_VALID, "match": "yes"}
        with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
            assert_rfx_integrity_bundle(
                lineage_record=_LIN_VALID, replay_record=truthy
            )

    def test_valid_bundle_passes(self) -> None:
        # Must not raise
        assert_rfx_integrity_bundle(
            lineage_record=_LIN_VALID, replay_record=_REP_VALID
        )


# ---------------------------------------------------------------------------
# LOOP-06: GOV certification hard gate
# ---------------------------------------------------------------------------

class TestLoop06CertificationGate:
    def test_full_valid_set_passes(self) -> None:
        # Must not raise
        assert_rfx_certification_ready(**_full_evidence_kwargs())

    @pytest.mark.parametrize(
        "missing_key, reason_code",
        [
            ("evl", "rfx_missing_evl_evidence"),
            ("tpa", "rfx_missing_tpa_evidence"),
            ("cde", "rfx_missing_cde_decision"),
            ("sel", "rfx_missing_sel_link"),
            ("lin", "rfx_missing_lineage"),
            ("rep", "rfx_missing_replay"),
            ("obs", "rfx_missing_obs"),
            ("slo", "rfx_slo_block"),
            ("pra", "rfx_missing_pra_evidence"),
            ("pol", "rfx_missing_pol_evidence"),
        ],
    )
    def test_each_missing_artifact_blocks(self, missing_key: str, reason_code: str) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs[missing_key] = None
        # POL is only required when policy_in_scope; force scope on for this test.
        if missing_key == "pol":
            with pytest.raises(RFXCertificationGateError, match=reason_code):
                assert_rfx_certification_ready(policy_in_scope=True, **kwargs)
        else:
            with pytest.raises(RFXCertificationGateError, match=reason_code):
                assert_rfx_certification_ready(**kwargs)

    def test_evl_failing_status_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["evl"] = {**_EVL_PASS, "status": "fail"}
        with pytest.raises(RFXCertificationGateError, match="rfx_evl_evidence_not_passing"):
            assert_rfx_certification_ready(**kwargs)

    def test_evl_conditional_pass_passes(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["evl"] = {**_EVL_PASS, "status": "conditional_pass"}
        assert_rfx_certification_ready(**kwargs)

    def test_tpa_blocked_status_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["tpa"] = {**_TPA_ACCEPTED, "status": "blocked"}
        with pytest.raises(RFXCertificationGateError, match="rfx_tpa_evidence_not_accepted"):
            assert_rfx_certification_ready(**kwargs)

    def test_tpa_conditional_passes(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["tpa"] = {**_TPA_ACCEPTED, "status": "conditional"}
        assert_rfx_certification_ready(**kwargs)

    def test_cde_invalid_status_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["cde"] = {**_CDE_READY, "status": "approved"}
        with pytest.raises(RFXCertificationGateError, match="rfx_invalid_cde_decision"):
            assert_rfx_certification_ready(**kwargs)

    def test_sel_unlinked_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["sel"] = {"enforcement_id": "sel-x", "action": "allow"}
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_sel_link"):
            assert_rfx_certification_ready(**kwargs)

    def test_lineage_not_authentic_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["lin"] = {**_LIN_VALID, "authenticity": "fail"}
        with pytest.raises(RFXCertificationGateError, match="rfx_lineage_not_authentic"):
            assert_rfx_certification_ready(**kwargs)

    def test_replay_mismatch_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["rep"] = {**_REP_VALID, "match": False}
        with pytest.raises(RFXCertificationGateError, match="rfx_replay_mismatch"):
            assert_rfx_certification_ready(**kwargs)

    def test_obs_incomplete_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["obs"] = {"trace_id": "obs-x", "telemetry_complete": False}
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_obs"):
            assert_rfx_certification_ready(**kwargs)

    def test_slo_freeze_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["slo"] = {**_SLO_OK, "status": "freeze"}
        with pytest.raises(RFXCertificationGateError, match="rfx_slo_block"):
            assert_rfx_certification_ready(**kwargs)

    def test_pra_not_ready_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pra"] = {**_PRA_READY, "status": "draft"}
        with pytest.raises(RFXCertificationGateError, match="rfx_pra_not_ready"):
            assert_rfx_certification_ready(**kwargs)

    def test_pol_inactive_blocks(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = {**_POL_ACTIVE, "status": "draft"}
        with pytest.raises(RFXCertificationGateError, match="rfx_pol_not_active"):
            assert_rfx_certification_ready(**kwargs)

    def test_pol_canary_passes(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = {**_POL_ACTIVE, "status": "canary"}
        assert_rfx_certification_ready(**kwargs)

    def test_pol_approved_passes(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = {**_POL_ACTIVE, "status": "approved"}
        assert_rfx_certification_ready(**kwargs)

    def test_pol_optional_when_policy_out_of_scope(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = None
        # Must not raise when caller explicitly declares policy out of scope
        assert_rfx_certification_ready(policy_in_scope=False, **kwargs)

    def test_pol_required_explicitly_overrides_inference(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = None
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
            assert_rfx_certification_ready(policy_in_scope=True, **kwargs)

    def test_pol_missing_with_default_scope_fails_closed(self) -> None:
        """Default scope = None must fail closed when POL is omitted (RT-04 hardening)."""
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = None
        # No ``policy_in_scope`` keyword — default is ``None``, which the
        # guard now treats as "policy is in scope" so missing POL raises.
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
            assert_rfx_certification_ready(**kwargs)

    def test_pol_empty_dict_with_default_scope_fails_closed(self) -> None:
        """An empty POL artifact with default scope must also fail closed."""
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = {}
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
            assert_rfx_certification_ready(**kwargs)


# ---------------------------------------------------------------------------
# Red-team campaign — RT-01 through RT-06
# ---------------------------------------------------------------------------

class TestRedTeamCampaign:
    """RT vectors: each must fail deterministically with machine-readable codes."""

    # RT-01: CDE decision missing -> SEL must be blocked.
    def test_rt01_cde_missing_blocks_sel(self) -> None:
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision=None, sel_context=_SEL_LINKED
            )

    # RT-02: Replay mismatch -> certification candidate frozen/blocked.
    def test_rt02_replay_mismatch_freezes_certification(self) -> None:
        mismatched = {**_REP_VALID, "match": False}
        with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
            assert_rfx_integrity_bundle(
                lineage_record=_LIN_VALID, replay_record=mismatched
            )
        # Also verify GOV-level gate blocks deterministically.
        kwargs = _full_evidence_kwargs()
        kwargs["rep"] = mismatched
        with pytest.raises(RFXCertificationGateError, match="rfx_replay_mismatch"):
            assert_rfx_certification_ready(**kwargs)

    # RT-03: PRA missing -> GOV blocked.
    def test_rt03_pra_missing_blocks_gov(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pra"] = None
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pra_evidence"):
            assert_rfx_certification_ready(**kwargs)

    # RT-04: POL missing while policy is in scope -> GOV blocked. The default
    # ``policy_in_scope=None`` must also fail closed so callers cannot bypass
    # POL enforcement by omitting both keywords.
    def test_rt04_pol_missing_when_policy_in_scope_blocks_gov(self) -> None:
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = None
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
            assert_rfx_certification_ready(policy_in_scope=True, **kwargs)

    def test_rt04_default_scope_pol_missing_fails_closed(self) -> None:
        """RT-04 hardening: default scope must fail closed when POL is omitted."""
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = None
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
            assert_rfx_certification_ready(**kwargs)

    # RT-05: Fake/forged CDE decision without SEL linkage -> blocked at bridge.
    def test_rt05_fake_cde_without_linkage_blocks(self) -> None:
        forged_cde = {"decision_id": "cde-forged-999", "status": "ready"}
        unlinked_sel = {
            "enforcement_id": "sel-attacker",
            "cde_decision_ref": "cde_decision:cde-other-001",
            "action": "allow",
        }
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_sel_not_linked_to_cde"):
            assert_rfx_cde_sel_decision_bridge(
                cde_decision=forged_cde, sel_context=unlinked_sel
            )
        # Also verify GOV-level gate refuses the forged linkage.
        kwargs = _full_evidence_kwargs()
        kwargs["cde"] = forged_cde
        kwargs["sel"] = unlinked_sel
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_sel_link"):
            assert_rfx_certification_ready(**kwargs)

    # RT-06: Full valid evidence bundle -> all guards pass.
    def test_rt06_all_valid_passes_all_guards(self) -> None:
        # LOOP-04
        assert_rfx_cde_sel_decision_bridge(
            cde_decision=_CDE_READY, sel_context=_SEL_LINKED
        )
        # LOOP-05
        assert_rfx_integrity_bundle(
            lineage_record=_LIN_VALID, replay_record=_REP_VALID
        )
        # LOOP-06
        assert_rfx_certification_ready(**_full_evidence_kwargs())


# ---------------------------------------------------------------------------
# Authority/responsibility invariants — RFX must remain a phase label.
# ---------------------------------------------------------------------------

class TestAuthorityInvariants:
    """Verify CDE/TPA/GOV authority boundaries are not redefined by these guards."""

    def test_cde_remains_decision_authority_via_explicit_status(self) -> None:
        # The bridge guard does not synthesize a CDE decision; it requires one.
        with pytest.raises(RFXDecisionBridgeGuardError, match="rfx_missing_cde_decision"):
            assert_rfx_cde_sel_decision_bridge(cde_decision=None, sel_context=_SEL_LINKED)

    def test_gov_only_certifies_completeness(self) -> None:
        # GOV does not decide readiness — it requires the CDE decision artifact.
        kwargs = _full_evidence_kwargs()
        kwargs["cde"] = None
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_cde_decision"):
            assert_rfx_certification_ready(**kwargs)

    def test_tpa_remains_policy_authority_via_required_pol_input(self) -> None:
        # POL (policy posture) is a required input when in scope; GOV does not
        # synthesize a policy posture.
        kwargs = _full_evidence_kwargs()
        kwargs["pol"] = None
        with pytest.raises(RFXCertificationGateError, match="rfx_missing_pol_evidence"):
            assert_rfx_certification_ready(policy_in_scope=True, **kwargs)
