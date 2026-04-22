"""Phase 5 Release, Security & Budget tests: REL semantics, SEC guardrail, CAP enforcement.

GATE-R compliance tests.
"""

import pytest


# ── REL Release Semantics ─────────────────────────────────────────────────────


class TestReleaseSemanticsGate:
    def setup_method(self):
        from spectrum_systems.modules.release.release_semantics import ReleaseSemanticsGate
        self.gate = ReleaseSemanticsGate()

    def test_blocks_promotion_without_canary(self):
        ok, msg = self.gate.require_canary_before_promotion("ART-NO-CANARY")
        assert not ok
        assert "canary" in msg.lower()

    def test_allows_promotion_after_canary(self):
        self.gate.emit_canary_record("ART-WITH-CANARY", "5% traffic")
        ok, msg = self.gate.require_canary_before_promotion("ART-WITH-CANARY")
        assert ok

    def test_emits_canary_record_with_correct_fields(self):
        rec = self.gate.emit_canary_record("ART-CAN", "10%")
        assert rec["artifact_type"] == "canary_record"
        assert rec["source_artifact"] == "ART-CAN"
        assert rec["canary_scope"] == "10%"
        assert rec["status"] == "running"

    def test_emits_freeze_record_with_reason(self):
        rec = self.gate.emit_freeze_record("ART-FRZ", "slo_breach")
        assert rec["artifact_type"] == "freeze_record"
        assert "slo_breach" in rec["reason_codes"]

    def test_emits_rollback_record(self):
        rec = self.gate.emit_rollback_record("ART-RBK", ["revert_step_1", "revert_step_2"])
        assert rec["artifact_type"] == "rollback_record"
        assert rec["rolled_back_artifact"] == "ART-RBK"
        assert len(rec["revert_steps"]) == 2

    def test_failed_canary_blocks_promotion(self):
        rec = self.gate.emit_canary_record("ART-FAIL-CAN", "1%")
        rec["status"] = "failed"  # simulate canary failure
        self.gate._canary_records["ART-FAIL-CAN"] = rec
        ok, msg = self.gate.require_canary_before_promotion("ART-FAIL-CAN")
        assert not ok
        assert "failed" in msg.lower()


# ── SEC Guardrail ─────────────────────────────────────────────────────────────


class TestSecGuardrail:
    def setup_method(self):
        from spectrum_systems.modules.security.sec_guardrail import get_security_approval
        self.get_approval = get_security_approval

    def test_high_risk_without_approval_blocked(self):
        ok, report = self.get_approval("ART-HR", "HIGH", approvals={})
        assert not ok
        assert "SEL approval" in report.get("reason", "")

    def test_high_risk_with_approval_allowed(self):
        approvals = {"ART-HR-OK": {"status": "approved", "approval_id": "APR-001"}}
        ok, report = self.get_approval("ART-HR-OK", "HIGH", approvals=approvals)
        assert ok

    def test_low_risk_requires_no_approval(self):
        ok, report = self.get_approval("ART-LOW", "LOW", approvals={})
        assert ok

    def test_medium_risk_requires_no_approval(self):
        ok, report = self.get_approval("ART-MED", "MEDIUM", approvals={})
        assert ok

    def test_high_risk_with_pending_approval_blocked(self):
        approvals = {"ART-HR-PEND": {"status": "pending", "approval_id": "APR-002"}}
        ok, report = self.get_approval("ART-HR-PEND", "HIGH", approvals=approvals)
        assert not ok


# ── CAP Budget Enforcement ────────────────────────────────────────────────────


class TestBudgetEnforcement:
    def setup_method(self):
        from spectrum_systems.modules.budget.cap_enforcer import check_budget_compliance
        self.check = check_budget_compliance

    def test_within_budget_allowed(self):
        ok, report = self.check("fam_a", actual_cost=50, budget_cost=100,
                                 actual_latency_p99=200, budget_latency_ms=500)
        assert ok

    def test_cost_overage_blocked(self):
        ok, report = self.check("fam_b", actual_cost=200, budget_cost=100,
                                 actual_latency_p99=100, budget_latency_ms=500)
        assert not ok
        assert not report["cost"]["within_budget"]

    def test_latency_overage_blocked(self):
        ok, report = self.check("fam_c", actual_cost=50, budget_cost=100,
                                 actual_latency_p99=1000, budget_latency_ms=500)
        assert not ok
        assert not report["latency_p99_ms"]["within_budget"]

    def test_both_overages_blocked(self):
        ok, report = self.check("fam_d", actual_cost=999, budget_cost=10,
                                 actual_latency_p99=9999, budget_latency_ms=100)
        assert not ok

    def test_report_contains_required_keys(self):
        ok, report = self.check("fam_e", 1, 100, 1, 1000)
        assert "cost" in report
        assert "latency_p99_ms" in report
        assert "overall_within_budget" in report


# ── RT-R Red Team ────────────────────────────────────────────────────────────


class TestRedTeamReleaseBudget:
    def test_chx014_cost_budget_exceeded_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_release_budget_campaigns
        chx014 = next(c for c in _make_release_budget_campaigns() if c.campaign_id == "CHX-014")
        result = chx014.run()
        assert result["passed"], f"CHX-014 failed: {result['message']}"

    def test_chx015_skip_canary_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_release_budget_campaigns
        chx015 = next(c for c in _make_release_budget_campaigns() if c.campaign_id == "CHX-015")
        result = chx015.run()
        assert result["passed"], f"CHX-015 failed: {result['message']}"

    def test_chx016_high_risk_without_approval_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_release_budget_campaigns
        chx016 = next(c for c in _make_release_budget_campaigns() if c.campaign_id == "CHX-016")
        result = chx016.run()
        assert result["passed"], f"CHX-016 failed: {result['message']}"
