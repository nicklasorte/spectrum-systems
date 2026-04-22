"""Phase 2 Context & Eval tests: CTX source admission, EVL coverage, DAT lineage.

GATE-C compliance tests.
"""

import pytest


# ── CTX Context Admission ─────────────────────────────────────────────────────


class TestContextAdmissionPolicy:
    def setup_method(self):
        from spectrum_systems.modules.ai_workflow.context_admission import ContextAdmissionPolicy
        self.policy = ContextAdmissionPolicy()

    def test_admits_empty_bundle(self):
        """Empty source list is admitted (no sources to reject)."""
        ok, msg = self.policy.admit_context_bundle({"sources": []}, required_tier="HIGH")
        assert ok

    def test_rejects_unknown_source_type(self):
        """Unknown source type with no schema must be rejected."""
        ok, msg = self.policy.admit_context_bundle(
            {"sources": [{"type": "xyzzy_unknown_type_abc", "trust_tier": "HIGH"}]},
            required_tier="HIGH",
        )
        assert not ok
        assert "unknown source type" in msg.lower() or "no schema" in msg.lower()

    def test_rejects_low_tier_in_high_pipeline(self):
        """LOW-tier context in HIGH-tier pipeline must be rejected."""
        ok, msg = self.policy.admit_context_bundle(
            {"sources": [{"type": "context_bundle", "trust_tier": "LOW"}]},
            required_tier="HIGH",
        )
        assert not ok
        assert "LOW" in msg or "below" in msg.lower()

    def test_admits_high_tier_in_high_pipeline(self):
        """HIGH-tier source admitted in HIGH-tier pipeline."""
        ok, msg = self.policy.admit_context_bundle(
            {"sources": [{"type": "transcript_artifact", "trust_tier": "HIGH"}]},
            required_tier="HIGH",
        )
        assert ok

    def test_admits_medium_tier_in_medium_pipeline(self):
        """MEDIUM-tier source admitted in MEDIUM-tier pipeline."""
        ok, msg = self.policy.admit_context_bundle(
            {"sources": [{"type": "context_bundle", "trust_tier": "MEDIUM"}]},
            required_tier="MEDIUM",
        )
        assert ok

    def test_classify_source_returns_correct_tier(self):
        """classify_source returns known tier for known types."""
        assert self.policy.classify_source("transcript") == "HIGH"
        assert self.policy.classify_source("uncertain_extraction") == "LOW"
        assert self.policy.classify_source("nonexistent") == "UNKNOWN"


# ── EVL Stale Fixture Detector ────────────────────────────────────────────────


class TestStaleFixtureDetector:
    def test_returns_list(self):
        """detect_stale_fixtures must return a list."""
        from spectrum_systems.modules.ai_workflow.stale_fixture_detector import detect_stale_fixtures
        result = detect_stale_fixtures()
        assert isinstance(result, list)

    def test_threshold_zero_finds_all_fixtures(self):
        """With threshold=0, all fixtures appear stale."""
        from spectrum_systems.modules.ai_workflow.stale_fixture_detector import detect_stale_fixtures
        all_stale = detect_stale_fixtures(threshold_days=0)
        # Should have at least the 30 test transcripts
        assert len(all_stale) >= 1

    def test_stale_entry_has_required_fields(self):
        """Each stale entry must have fixture, age_days, is_stale."""
        from spectrum_systems.modules.ai_workflow.stale_fixture_detector import detect_stale_fixtures
        stale = detect_stale_fixtures(threshold_days=0)
        if stale:
            entry = stale[0]
            assert "fixture" in entry
            assert "age_days" in entry
            assert entry["is_stale"] is True


# ── DAT Dataset Lineage ───────────────────────────────────────────────────────


class TestDatasetLineage:
    def setup_method(self):
        from spectrum_systems.modules.ai_workflow.dataset_lineage import validate_dataset_lineage
        self.validate = validate_dataset_lineage

    def test_rejects_missing_lineage_fields(self):
        """Dataset without provenance fields must be rejected."""
        ok, msg = self.validate({"dataset_id": "DS-001"})
        assert not ok
        assert "lineage" in msg.lower() or "missing" in msg.lower()

    def test_rejects_partial_lineage(self):
        """Dataset with only some provenance fields must be rejected."""
        ok, msg = self.validate({"dataset_id": "DS-002", "source_url": "http://example.com"})
        assert not ok

    def test_accepts_complete_lineage(self):
        """Dataset with all provenance fields must be accepted."""
        ok, msg = self.validate({
            "dataset_id": "DS-003",
            "source_url": "https://data.example.com/ds",
            "version": "1.2.3",
            "content_hash": "abc123",
            "created_at": "2025-01-01T00:00:00Z",
        })
        assert ok, f"Expected valid, got: {msg}"


# ── EVL Eval Coverage ────────────────────────────────────────────────────────


class TestEvalCoverage:
    def test_rejects_family_with_fewer_than_3_cases(self):
        """Artifact family with < 3 eval cases must fail coverage check."""
        from spectrum_systems.modules.ai_workflow.dataset_lineage import validate_eval_coverage
        ok, errors = validate_eval_coverage(
            "test_family",
            eval_cases=[{"artifact_type": "test_family"}, {"artifact_type": "test_family"}],
            min_cases=3,
        )
        assert not ok
        assert any("3" in e or "≥" in e for e in errors)

    def test_accepts_family_with_sufficient_cases(self):
        """Artifact family with ≥ 3 eval cases must pass coverage check."""
        from spectrum_systems.modules.ai_workflow.dataset_lineage import validate_eval_coverage
        cases = [{"artifact_type": "my_family"}] * 3
        ok, errors = validate_eval_coverage("my_family", cases, min_cases=3)
        assert ok


# ── RT-C Red Team ────────────────────────────────────────────────────────────


class TestRedTeamContextEval:
    def test_rt_c1_unknown_source_rejected(self):
        """RT-C1: UNKNOWN source type must be rejected."""
        from spectrum_systems.modules.ai_workflow.context_admission import ContextAdmissionPolicy
        policy = ContextAdmissionPolicy()
        ok, msg = policy.admit_context_bundle(
            {"sources": [{"type": "totally_unknown_xyz_source", "trust_tier": "HIGH"}]},
            required_tier="HIGH",
        )
        assert not ok

    def test_chx006_low_tier_in_high_pipeline_blocked(self):
        """CHX-006: LOW-tier context in HIGH pipeline blocked via campaign."""
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_context_eval_campaigns
        campaigns = _make_context_eval_campaigns()
        chx006 = next(c for c in campaigns if c.campaign_id == "CHX-006")
        result = chx006.run()
        assert result["passed"], f"CHX-006 failed: {result['message']}"

    def test_chx008_dataset_missing_lineage_blocked(self):
        """CHX-008: Dataset without lineage fields is blocked."""
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_context_eval_campaigns
        campaigns = _make_context_eval_campaigns()
        chx008 = next(c for c in campaigns if c.campaign_id == "CHX-008")
        result = chx008.run()
        assert result["passed"], f"CHX-008 failed: {result['message']}"
