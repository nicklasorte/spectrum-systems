"""Phase 3 Judgment & Policy tests: JDX evidence sufficiency, JSX supersession,
PRX precedent eligibility, POL lifecycle, PRM admissibility.

GATE-J compliance tests.
"""

import pytest


# ── JDX Evidence Sufficiency ─────────────────────────────────────────────────


class TestJudgmentEvidence:
    def setup_method(self):
        from spectrum_systems.modules.governance.judgment import validate_judgment_evidence
        self.validate = validate_judgment_evidence

    def test_rejects_zero_evidence(self):
        ok, msg = self.validate({"id": "JDG-001", "evidence_artifacts": []})
        assert not ok
        assert "≥2" in msg or "2" in msg

    def test_rejects_single_evidence(self):
        ok, msg = self.validate({"id": "JDG-002", "evidence_artifacts": ["E1"]})
        assert not ok

    def test_accepts_two_evidence(self):
        ok, msg = self.validate({"id": "JDG-003", "evidence_artifacts": ["E1", "E2"]})
        assert ok

    def test_accepts_three_evidence(self):
        ok, msg = self.validate({"id": "JDG-004", "evidence_artifacts": ["E1", "E2", "E3"]})
        assert ok


# ── JSX Judgment Store / Supersession ────────────────────────────────────────


class TestJudgmentStore:
    def setup_method(self):
        from spectrum_systems.modules.governance.judgment_store import JudgmentStore
        self.store = JudgmentStore()

    def test_create_judgment_blocks_insufficient_evidence(self):
        with pytest.raises(ValueError, match="Evidence insufficiency"):
            self.store.create_judgment({"id": "J1", "evidence_artifacts": ["E1"]})

    def test_create_and_retrieve_active_judgment(self):
        j = self.store.create_judgment({"id": "J-ACTIVE", "evidence_artifacts": ["E1", "E2"]})
        retrieved = self.store.retrieve_judgment("J-ACTIVE")
        assert retrieved is not None
        assert retrieved["id"] == "J-ACTIVE"

    def test_superseded_judgment_returns_none(self):
        self.store.create_judgment({"id": "J-OLD", "evidence_artifacts": ["E1", "E2"]})
        self.store.supersede_judgment("J-OLD", "J-NEW", "replaced")
        retrieved = self.store.retrieve_judgment("J-OLD")
        assert retrieved is None

    def test_supersession_creates_supersession_record(self):
        self.store.create_judgment({"id": "J-S1", "evidence_artifacts": ["E1", "E2"]})
        sup = self.store.supersede_judgment("J-S1", "J-S2", "reason")
        assert sup["artifact_type"] == "supersession_record"
        assert sup["old_judgment_id"] == "J-S1"

    def test_nonexistent_judgment_returns_none(self):
        result = self.store.retrieve_judgment("NONEXISTENT-99999")
        assert result is None


# ── PRX Precedent Eligibility ─────────────────────────────────────────────────


class TestPrecedentEligibility:
    def setup_method(self):
        from spectrum_systems.modules.governance.precedent import retrieve_precedent
        self.retrieve = retrieve_precedent

    def test_returns_none_for_wrong_class(self):
        prec = {"precedent_id": "P1", "applicable_to_classes": ["class_A"], "content": "x"}
        result = self.retrieve(prec, "class_B")
        assert result is None

    def test_returns_precedent_for_correct_class(self):
        prec = {"precedent_id": "P2", "applicable_to_classes": ["class_X"], "content": "y"}
        result = self.retrieve(prec, "class_X")
        assert result is not None
        assert result["precedent_id"] == "P2"

    def test_returns_none_for_empty_applicable_classes(self):
        prec = {"precedent_id": "P3", "applicable_to_classes": [], "content": "z"}
        result = self.retrieve(prec, "any_class")
        assert result is None


# ── POL Policy Lifecycle ──────────────────────────────────────────────────────


class TestPolicyLifecycle:
    def setup_method(self):
        from spectrum_systems.modules.governance.policy_lifecycle import apply_policy
        self.apply = apply_policy

    def test_blocks_expired_policy(self):
        ok, msg = self.apply({
            "policy_id": "POL-EXP",
            "status": "active",
            "expires_at": "2000-01-01T00:00:00Z",
        })
        assert not ok
        assert "expired" in msg.lower()

    def test_blocks_inactive_policy(self):
        ok, msg = self.apply({
            "policy_id": "POL-INACTIVE",
            "status": "revoked",
            "expires_at": "2099-01-01T00:00:00Z",
        })
        assert not ok
        assert "revoked" in msg or "active" in msg

    def test_allows_active_nonexpired_policy(self):
        ok, msg = self.apply({
            "policy_id": "POL-VALID",
            "status": "active",
            "expires_at": "2099-12-31T23:59:59Z",
        })
        assert ok

    def test_allows_policy_without_expiry(self):
        ok, msg = self.apply({"policy_id": "POL-NO-EXP", "status": "active"})
        assert ok


# ── PRM Prompt Admissibility ─────────────────────────────────────────────────


class TestPromptRegistry:
    def setup_method(self):
        from spectrum_systems.modules.execution.prompt_registry import PromptRegistry
        self.registry = PromptRegistry()

    def test_blocks_unregistered_prompt(self):
        with pytest.raises(ValueError, match="Unregistered prompt"):
            self.registry.get_registered_prompt("UNREGISTERED-99999")

    def test_allows_registered_prompt(self):
        self.registry.register_prompt("P-001", "Hello {{name}}")
        entry = self.registry.get_registered_prompt("P-001")
        assert entry is not None
        assert entry["prompt_id"] == "P-001"

    def test_detects_modified_template(self):
        self.registry.register_prompt("P-002", "Original template")
        valid = self.registry.verify_prompt_integrity("P-002", "Original template")
        invalid = self.registry.verify_prompt_integrity("P-002", "Modified template")
        assert valid
        assert not invalid

    def test_is_registered_returns_false_for_unknown(self):
        assert not self.registry.is_registered("UNKNOWN-XYZ")

    def test_is_registered_returns_true_for_known(self):
        self.registry.register_prompt("P-003", "template text")
        assert self.registry.is_registered("P-003")


# ── RT-J Red Team ────────────────────────────────────────────────────────────


class TestRedTeamJudgment:
    def test_chx003_unregistered_prompt_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_foundation_campaigns
        chx003 = next(c for c in _make_foundation_campaigns() if c.campaign_id == "CHX-003")
        result = chx003.run()
        assert result["passed"], f"CHX-003 failed: {result['message']}"

    def test_chx004_expired_policy_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_foundation_campaigns
        chx004 = next(c for c in _make_foundation_campaigns() if c.campaign_id == "CHX-004")
        result = chx004.run()
        assert result["passed"], f"CHX-004 failed: {result['message']}"

    def test_chx009_superseded_judgment_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_judgment_policy_campaigns
        chx009 = next(c for c in _make_judgment_policy_campaigns() if c.campaign_id == "CHX-009")
        result = chx009.run()
        assert result["passed"], f"CHX-009 failed: {result['message']}"

    def test_chx010_wrong_scope_precedent_blocked(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_judgment_policy_campaigns
        chx010 = next(c for c in _make_judgment_policy_campaigns() if c.campaign_id == "CHX-010")
        result = chx010.run()
        assert result["passed"], f"CHX-010 failed: {result['message']}"
