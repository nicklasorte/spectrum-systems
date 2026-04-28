"""Tests for RFX-14 error-budget governance expansion."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_error_budget_governance import (
    RFXErrorBudgetGovernanceError,
    assert_rfx_error_budget_governance,
)


def test_exhausted_budget_freezes_new_capability() -> None:
    with pytest.raises(RFXErrorBudgetGovernanceError, match="rfx_new_capability_frozen"):
        assert_rfx_error_budget_governance(
            slo_posture={"budget_exhausted": True},
            proposed_work={"work_type": "capability"},
        )


def test_reliability_work_allowed_under_freeze() -> None:
    record = assert_rfx_error_budget_governance(
        slo_posture={"budget_exhausted": True},
        proposed_work={
            "work_type": "reliability",
            "reliability_evidence_refs": ["slo:burn", "obs:trace"],
        },
    )
    assert record["artifact_type"] == "rfx_error_budget_governance_record"
    assert record["eligibility"] == "allowed_reliability_only"
    assert "rfx_reliability_work_allowed" in record["reason_codes"]


def test_missing_budget_posture_blocks() -> None:
    with pytest.raises(RFXErrorBudgetGovernanceError, match="rfx_budget_posture_missing"):
        assert_rfx_error_budget_governance(
            slo_posture=None, proposed_work={"work_type": "capability"}
        )


def test_healthy_budget_allows_normal_progression() -> None:
    record = assert_rfx_error_budget_governance(
        slo_posture={"status": "ok", "budget_exhausted": False},
        proposed_work={"work_type": "capability"},
    )
    assert record["eligibility"] == "allowed"


# ---------------------------------------------------------------------------
# RT-22 red-team: classify feature work as reliability without evidence
# ---------------------------------------------------------------------------


def test_rt22_red_team_reliability_without_evidence_blocks_then_revalidates() -> None:
    with pytest.raises(RFXErrorBudgetGovernanceError, match="rfx_budget_posture_missing"):
        assert_rfx_error_budget_governance(
            slo_posture={"budget_exhausted": True},
            proposed_work={"work_type": "reliability", "reliability_evidence_refs": []},
        )
    record = assert_rfx_error_budget_governance(
        slo_posture={"budget_exhausted": True},
        proposed_work={
            "work_type": "reliability",
            "reliability_evidence_refs": ["slo:burn", "obs:trace"],
        },
    )
    assert record["eligibility"] == "allowed_reliability_only"
