"""Phase 1 Foundation tests: CON registry drift validator, contract enforcer, CHX campaigns.

GATE-F compliance tests — all must pass green.
"""

import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── CON Registry Drift Validator ─────────────────────────────────────────────


class TestRegistryDriftValidator:
    def setup_method(self):
        from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator
        self.validator = RegistryDriftValidator()

    def test_validator_detects_missing_owned_responsibilities(self):
        """Validator must flag systems with no 'owns' responsibilities."""
        is_valid, errors = self.validator.validate_system(
            "TEST-INVALID", {"owns": [], "produces": [], "consumes": []}
        )
        assert not is_valid
        assert any("No 'owns'" in e for e in errors)

    def test_validator_accepts_system_with_owns(self):
        """Validator accepts a system with at least one responsibility."""
        is_valid, errors = self.validator.validate_system(
            "TEST-VALID",
            {"owns": ["some_responsibility"], "produces": [], "consumes": []},
        )
        assert is_valid
        assert errors == []

    def test_validator_detects_missing_schema(self):
        """Validator must flag produces artifacts with no corresponding schema."""
        is_valid, errors = self.validator.validate_system(
            "TEST-SCHEMA-MISSING",
            {
                "owns": ["something"],
                "produces": ["totally_nonexistent_artifact_xyz_abc_99999"],
                "consumes": [],
            },
        )
        assert not is_valid
        assert any("no schema" in e.lower() for e in errors)

    def test_drift_report_emitted_with_correct_shape(self):
        """emit_drift_report must return a registry_drift_report artifact."""
        report = self.validator.emit_drift_report()
        assert report["artifact_type"] == "registry_drift_report"
        assert "systems_checked" in report
        assert "systems_non_compliant" in report
        assert isinstance(report["systems_non_compliant"], list)
        assert isinstance(report["details"], dict)

    def test_drift_report_has_trace_id(self):
        """Drift report must have a non-empty trace_id."""
        report = self.validator.emit_drift_report()
        assert report.get("trace_id"), "trace_id must be present"

    def test_drift_report_checks_real_registry(self):
        """Validator must parse and check the actual system registry."""
        report = self.validator.emit_drift_report()
        assert report["systems_checked"] > 0, "Must find systems in real registry"

    def test_registry_parses_known_systems(self):
        """Registry parser must find canonical systems like AEX, PQX, CDE."""
        known = {"AEX", "PQX", "CDE", "TLC", "GOV"}
        found = set(self.validator.registry.keys())
        overlap = known & found
        assert len(overlap) >= 3, f"Expected canonical systems, found only {found & known}"

    def test_system_with_produces_and_known_schema_is_valid(self):
        """A system that produces an artifact type with a real schema must be valid."""
        # freeze_record.schema.json exists
        is_valid, errors = self.validator.validate_system(
            "TEST-WITH-SCHEMA",
            {"owns": ["release_control"], "produces": ["freeze_record"], "consumes": []},
        )
        assert is_valid, f"Expected valid, got errors: {errors}"


# ── CON Contract Enforcer ─────────────────────────────────────────────────────


class TestContractEnforcer:
    def setup_method(self):
        from spectrum_systems.governance.contract_enforcer import ContractEnforcer
        self.enforcer = ContractEnforcer()

    def test_validate_produces_detects_missing_schema(self):
        """Contract enforcer must detect produces artifact without schema."""
        ok, msg = self.enforcer.validate_produces_contract(
            "SYS-A", "totally_nonexistent_artifact_xyz"
        )
        assert not ok
        assert "Missing schema" in msg

    def test_validate_produces_detects_missing_eval_case(self):
        """Contract enforcer detects produces artifact with schema but no eval cases."""
        ok, msg = self.enforcer.validate_produces_contract("SYS-B", "freeze_record")
        # freeze_record schema exists but no eval cases yet — enforcer correctly flags this
        assert not ok
        assert "eval" in msg.lower() or "case" in msg.lower()

    def test_audit_system_returns_all_valid_for_empty_system(self):
        """Audit of system with no produces/consumes must show all_valid=True."""
        result = self.enforcer.audit_system("EMPTY-SYS", produces=[], consumes=[])
        assert result["all_valid"] is True


# ── CHX Campaign Skeleton ─────────────────────────────────────────────────────


class TestChaosCampaigns:
    def test_chx001_detects_missing_owned_responsibilities(self):
        """CHX-001: System with empty owns must be flagged."""
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_foundation_campaigns
        campaigns = _make_foundation_campaigns()
        chx001 = next(c for c in campaigns if c.campaign_id == "CHX-001")
        result = chx001.run()
        assert result["passed"], f"CHX-001 failed: {result['message']}"

    def test_chx002_detects_missing_schema(self):
        """CHX-002: System producing artifact without schema must be flagged."""
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_foundation_campaigns
        campaigns = _make_foundation_campaigns()
        chx002 = next(c for c in campaigns if c.campaign_id == "CHX-002")
        result = chx002.run()
        assert result["passed"], f"CHX-002 failed: {result['message']}"

    def test_chx005_single_evidence_judgment_rejected(self):
        """CHX-005: Judgment with 1 evidence artifact must be rejected."""
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_foundation_campaigns
        campaigns = _make_foundation_campaigns()
        chx005 = next(c for c in campaigns if c.campaign_id == "CHX-005")
        result = chx005.run()
        assert result["passed"], f"CHX-005 failed: {result['message']}"

    def test_build_all_campaigns_returns_19_campaigns(self):
        """build_all_campaigns must return all 19 CHX campaigns."""
        from spectrum_systems.modules.wpg.redteam_campaigns import build_all_campaigns
        campaigns = build_all_campaigns()
        assert len(campaigns) == 19

    def test_run_campaign_suite_produces_findings_record(self):
        """run_campaign_suite must produce a red_team_findings_record artifact."""
        from spectrum_systems.modules.wpg.redteam_campaigns import (
            build_all_campaigns,
            run_campaign_suite,
        )
        campaigns = build_all_campaigns()
        report = run_campaign_suite(campaigns)
        assert report["artifact_type"] == "red_team_findings_record"
        assert report["campaign_count"] == 19


# ── RT-F Red Team ────────────────────────────────────────────────────────────


class TestRedTeamFoundation:
    """RT-F: Foundation red team scenarios."""

    def test_rt_f1_fake_system_detected(self):
        """RT-F1: Add fake system with missing owns; validator must detect it."""
        from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator
        v = RegistryDriftValidator()
        ok, errors = v.validate_system("FAKE-SYS", {"owns": [], "produces": [], "consumes": []})
        assert not ok
        assert errors

    def test_rt_f2_system_with_missing_schema_detected(self):
        """RT-F2: System producing artifact without schema must be caught."""
        from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator
        v = RegistryDriftValidator()
        ok, errors = v.validate_system(
            "FAKE-SYS-2",
            {"owns": ["x"], "produces": ["fake_missing_artifact_zzz"], "consumes": []},
        )
        assert not ok
        assert any("no schema" in e.lower() for e in errors)

    def test_rt_f3_parser_does_not_cross_section_boundary(self):
        """RT-F3: Registry parser must not capture must_not_do items as produces entries.

        Regression guard for the cross-section-boundary parser bug where _extract_list()
        greedily captured items past the next **section:** header.
        """
        from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator
        v = RegistryDriftValidator()
        # Every parsed system must have produces items that are plain artifact names,
        # not section-header text like '**must_not_do:**'.
        for system_id, system_def in v.registry.items():
            for artifact in system_def.get("produces", []):
                assert "**" not in artifact, (
                    f"{system_id}: produces list contains section marker '{artifact}' — "
                    "parser crossed a **section:** boundary. Fix _extract_list() regex."
                )
                assert artifact == artifact.strip(), (
                    f"{system_id}: artifact name '{artifact}' has leading/trailing whitespace"
                )

    def test_rt_f4_drift_report_has_zero_schema_violations(self):
        """RT-F4: Drift report must show 0 schema-missing violations after all schemas added."""
        from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator
        report = RegistryDriftValidator().emit_drift_report()
        schema_violations = [
            s for s in report["systems_non_compliant"]
            if any("no schema" in e.lower() for e in report["details"].get(s, []))
        ]
        assert not schema_violations, (
            f"Schema violations found — add schemas or fix produces list: {schema_violations}"
        )
