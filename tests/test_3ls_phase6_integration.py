"""Phase 6 Integration tests: CRS cross-system consistency, MGV merge governance,
CHX campaign suite, full-stack integration slice.

GATE-I compliance tests.
"""

import pytest


# ── CRS Cross-System Consistency ─────────────────────────────────────────────


class TestCrossSystemConsistency:
    def setup_method(self):
        from spectrum_systems.modules.governance.cross_system_consistency import CrossSystemConsistencyChecker
        self.checker = CrossSystemConsistencyChecker()

    def test_compatible_versions_pass(self):
        ok, msg = self.checker.check_schema_version_compatibility("1.0", "1.0", ["1.0"])
        assert ok

    def test_incompatible_version_detected(self):
        ok, msg = self.checker.check_schema_version_compatibility("2.0", "1.0", ["2.0"])
        assert not ok
        assert "mismatch" in msg.lower() or "not in" in msg.lower()

    def test_empty_accepted_versions_blocks_all(self):
        ok, msg = self.checker.check_schema_version_compatibility("1.0", "1.0", [])
        assert not ok

    def test_audit_with_no_pairs_is_clean(self):
        audit = self.checker.emit_cross_system_audit(artifact_pairs=[])
        assert audit["artifact_type"] == "cross_system_audit_record"
        assert audit["incompatibilities"] == []

    def test_audit_detects_incompatible_pair(self):
        pairs = [{
            "consuming": {
                "artifact_id": "C1",
                "schema_version": "2.0",
                "$accepted_upstream_versions": ["2.0"],
            },
            "upstream": {
                "artifact_id": "U1",
                "schema_version": "1.0",
            },
        }]
        audit = self.checker.emit_cross_system_audit(artifact_pairs=pairs)
        assert len(audit["incompatibilities"]) == 1

    def test_audit_passes_compatible_pair(self):
        pairs = [{
            "consuming": {
                "artifact_id": "C2",
                "schema_version": "1.0",
                "$accepted_upstream_versions": ["1.0"],
            },
            "upstream": {
                "artifact_id": "U2",
                "schema_version": "1.0",
            },
        }]
        audit = self.checker.emit_cross_system_audit(artifact_pairs=pairs)
        assert audit["incompatibilities"] == []


# ── MGV Merge Governance Authority ───────────────────────────────────────────


class TestMergeGovernanceAuthority:
    def setup_method(self):
        from spectrum_systems.governance.merge_governance_authority import MergeGovernanceAuthority
        self.mgv = MergeGovernanceAuthority()

    def test_self_authorize_always_returns_false(self):
        ok, decision = self.mgv.self_authorize("feat", "main")
        assert not ok

    def test_authorize_without_cde_reviewer_blocked(self):
        ok, decision = self.mgv.authorize_merge(
            "feat", "main", ["ART-001"],
            gate_verifier=lambda _: True,
            cde_reviewer=None,
        )
        assert not ok
        assert any("CDE" in c for c in decision["conditions"])

    def test_authorize_with_all_gates_and_cde_allowed(self):
        ok, decision = self.mgv.authorize_merge(
            "feat", "main", ["ART-001"],
            gate_verifier=lambda _: True,
            cde_reviewer=lambda _: True,
        )
        assert ok

    def test_authorize_blocked_when_gate_fails(self):
        ok, decision = self.mgv.authorize_merge(
            "feat", "main", ["ART-FAIL"],
            gate_verifier=lambda _: False,
            cde_reviewer=lambda _: True,
        )
        assert not ok
        assert any("gates not verified" in c for c in decision["conditions"])

    def test_authorize_blocked_when_cde_rejects(self):
        ok, decision = self.mgv.authorize_merge(
            "feat", "main", ["ART-OK"],
            gate_verifier=lambda _: True,
            cde_reviewer=lambda _: False,
        )
        assert not ok
        assert any("CDE rejected" in c for c in decision["conditions"])


# ── CHX Campaign Integration ──────────────────────────────────────────────────


class TestCHXIntegrationCampaigns:
    def test_chx017_schema_version_mismatch_detected(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_integration_campaigns
        chx017 = next(c for c in _make_integration_campaigns() if c.campaign_id == "CHX-017")
        result = chx017.run()
        assert result["passed"], f"CHX-017 failed: {result['message']}"

    def test_chx018_multi_system_failures_all_fire(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_integration_campaigns
        chx018 = next(c for c in _make_integration_campaigns() if c.campaign_id == "CHX-018")
        result = chx018.run()
        assert result["passed"], f"CHX-018 failed: {result['message']}"

    def test_chx019_mgv_self_auth_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_integration_campaigns
        chx019 = next(c for c in _make_integration_campaigns() if c.campaign_id == "CHX-019")
        result = chx019.run()
        assert result["passed"], f"CHX-019 failed: {result['message']}"


# ── Full-Stack Integration Slice ──────────────────────────────────────────────


class TestEndToEndIntegration:
    """RT-INT1: End-to-end integration test — all gates in sequence."""

    def test_admission_to_promotion_happy_path(self):
        """Full-stack happy path: admit → execute → eval → promote."""
        # Step 1: Context admission
        from spectrum_systems.modules.ai_workflow.context_admission import ContextAdmissionPolicy
        policy = ContextAdmissionPolicy()
        ok, msg = policy.admit_context_bundle(
            {"sources": [{"type": "transcript", "trust_tier": "HIGH"}]},
            required_tier="HIGH",
        )
        assert ok, f"Admission failed: {msg}"

        # Step 2: OBS record emission
        from spectrum_systems.modules.observability.obs_emitter import OBSEmitter
        obs = OBSEmitter().emit_obs_record("TRC-E2E-001", ["ART-E2E-OUT"], 150, 75)
        assert obs["artifact_type"] == "obs_record"

        # Step 3: Lineage verification
        from spectrum_systems.modules.lineage.lineage_verifier import verify_lineage_completeness
        store = {
            "ART-E2E-OUT": {"artifact_type": "pqx_output", "upstream_artifacts": ["ART-E2E-IN"]},
            "ART-E2E-IN": {"artifact_type": "input_bundle", "upstream_artifacts": []},
        }
        ok, errors = verify_lineage_completeness("ART-E2E-OUT", artifact_store=store)
        assert ok, f"Lineage incomplete: {errors}"

        # Step 4: Replay determinism
        from spectrum_systems.modules.replay.replay_gate import check_replay_determinism
        result = check_replay_determinism("ART-E2E-OUT", ["stable_hash", "stable_hash"])
        assert result["deterministic"]

        # Step 5: Canary and promotion
        from spectrum_systems.modules.release.release_semantics import ReleaseSemanticsGate
        gate = ReleaseSemanticsGate()
        gate.emit_canary_record("ART-E2E-OUT", "100%")
        ok, msg = gate.require_canary_before_promotion("ART-E2E-OUT")
        assert ok, f"Promotion blocked: {msg}"

    def test_all_19_campaigns_pass(self):
        """All 19 CHX campaigns must pass (RT Round 1 + Round 2)."""
        from spectrum_systems.modules.wpg.redteam_campaigns import (
            build_all_campaigns,
            run_campaign_suite,
        )
        campaigns = build_all_campaigns()
        report = run_campaign_suite(campaigns)
        failed = [
            cid for cid, res in report["results"].items()
            if not res.get("passed")
        ]
        assert not failed, f"Failed campaigns: {failed}"
