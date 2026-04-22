"""Phase 7 Final Lock & Certification tests: ENT, PRG, gate rerun, CDE envelope, checkpoint.

GATE-7 compliance tests.
"""

import pytest


# ── ENT Entropy Detector ──────────────────────────────────────────────────────


class TestEntropyDetector:
    def setup_method(self):
        from spectrum_systems.modules.entropy.ent_detector import detect_repeated_corrections
        self.detect = detect_repeated_corrections

    def test_no_corrections_returns_empty(self):
        result = self.detect([])
        assert result == []

    def test_low_count_issues_not_flagged(self):
        corrections = [{"issue_type": "schema_mismatch"}, {"issue_type": "schema_mismatch"}]
        result = self.detect(corrections)
        assert not result  # 2 corrections, threshold is >2

    def test_high_count_issue_flagged(self):
        corrections = [{"issue_type": "registry_drift"}] * 3
        result = self.detect(corrections)
        assert len(result) == 1
        assert result[0]["issue_type"] == "registry_drift"
        assert result[0]["correction_count"] == 3

    def test_recommendation_present(self):
        corrections = [{"issue_type": "eval_gap"}] * 4
        result = self.detect(corrections)
        assert "recommendation" in result[0]
        assert "policy" in result[0]["recommendation"].lower() or "eval" in result[0]["recommendation"].lower()

    def test_multiple_issue_types_tracked_independently(self):
        corrections = [
            {"issue_type": "type_a"}, {"issue_type": "type_a"}, {"issue_type": "type_a"},
            {"issue_type": "type_b"}, {"issue_type": "type_b"},
        ]
        result = self.detect(corrections)
        types = {r["issue_type"] for r in result}
        assert "type_a" in types
        assert "type_b" not in types  # only 2, below threshold


# ── PRG Roadmap Alignment ────────────────────────────────────────────────────


class TestRoadmapAlignment:
    def test_emits_roadmap_alignment_record(self):
        from spectrum_systems.governance.roadmap_alignment import emit_roadmap_alignment_record
        record = emit_roadmap_alignment_record()
        assert record["artifact_type"] == "roadmap_alignment_record"

    def test_record_has_timestamp(self):
        from spectrum_systems.governance.roadmap_alignment import emit_roadmap_alignment_record
        record = emit_roadmap_alignment_record()
        assert record.get("timestamp")

    def test_record_has_roadmap_items_list(self):
        from spectrum_systems.governance.roadmap_alignment import emit_roadmap_alignment_record
        record = emit_roadmap_alignment_record()
        assert isinstance(record["roadmap_items"], list)


# ── Gate Rerun ───────────────────────────────────────────────────────────────


class TestGateRerun:
    def test_rerun_all_gates_returns_report(self):
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        assert report["artifact_type"] == "gate_rerun_report"
        assert "gates" in report
        assert "overall_status" in report

    def test_all_phase_gates_present_in_report(self):
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        expected = {"GATE-F", "GATE-C", "GATE-J", "GATE-O", "GATE-R", "GATE-I"}
        assert expected.issubset(set(report["gates"].keys()))

    def test_all_gates_pass(self):
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        failed_gates = [
            gid for gid, info in report["gates"].items()
            if not info["passed"]
        ]
        assert not failed_gates, f"Gates failed: {failed_gates}"
        assert report["overall_status"] == "GREEN"


# ── CDE Trust Envelope ────────────────────────────────────────────────────────


class TestCDETrustEnvelope:
    def setup_method(self):
        from spectrum_systems.governance.cde_trust_envelope import CDETrustEnvelope
        self.cde = CDETrustEnvelope()

    def test_create_produces_envelope_artifact(self):
        env = self.cde.create_trust_envelope()
        assert env["artifact_type"] == "cde_trust_envelope"

    def test_envelope_has_signature(self):
        env = self.cde.create_trust_envelope()
        assert env.get("signature")
        assert len(env["signature"]) > 10

    def test_envelope_has_bundle_hash(self):
        env = self.cde.create_trust_envelope()
        assert env.get("bundle_hash")
        assert len(env["bundle_hash"]) == 64  # SHA-256 hex

    def test_lock_sets_locked_flag(self):
        env = self.cde.lock_envelope()
        assert env["locked"] is True
        assert env.get("locked_at")

    def test_is_locked_returns_true_after_lock(self):
        self.cde.lock_envelope()
        assert self.cde.is_locked()

    def test_verify_promotion_against_locked_envelope(self):
        self.cde.lock_envelope()
        ok, msg = self.cde.verify_promotion_against_envelope({"artifact_type": "pqx_output"})
        assert ok

    def test_verify_promotion_fails_without_lock(self):
        ok, msg = self.cde.verify_promotion_against_envelope({})
        assert not ok


# ── PRG Checkpoint Review ────────────────────────────────────────────────────


class TestCheckpointReview:
    def setup_method(self):
        from spectrum_systems.governance.checkpoint_review import emit_checkpoint_review_artifact
        self.emit = emit_checkpoint_review_artifact

    def test_emits_checkpoint_review_artifact(self):
        rec = self.emit()
        assert rec["artifact_type"] == "checkpoint_review_artifact"

    def test_all_slis_present(self):
        rec = self.emit()
        expected_slis = {"eval_pass_rate", "lineage_completeness", "replay_determinism", "drift_rate_daily"}
        assert expected_slis.issubset(set(rec["slis"].keys()))

    def test_all_green_when_targets_met(self):
        rec = self.emit(
            eval_pass_rate=1.0,
            lineage_completeness_pct=100.0,
            replay_determinism_pct=100.0,
            drift_rate_daily=0.0,
            unregistered_prompt_count=0,
            expired_policy_count=0,
            cde_envelope_locked=True,
        )
        assert rec["summary"]["overall_status"] == "GREEN"

    def test_red_when_sli_breached(self):
        rec = self.emit(eval_pass_rate=0.80)  # below 95% target
        assert rec["slis"]["eval_pass_rate"]["status"] == "RED"
        assert rec["summary"]["overall_status"] == "RED"

    def test_governance_fields_present(self):
        rec = self.emit()
        gov = rec["governance"]
        assert "no_unregistered_prompts" in gov
        assert "no_expired_policies" in gov
        assert "cde_trust_envelope_locked" in gov


# ── RT-FINAL Comprehensive ────────────────────────────────────────────────────


class TestRTFinalComprehensive:
    """RT-FINAL: All bypass categories tested simultaneously."""

    def test_all_19_campaigns_blocked(self):
        """All 19 chaos scenarios must be blocked end-to-end."""
        from spectrum_systems.modules.wpg.redteam_campaigns import (
            build_all_campaigns,
            run_campaign_suite,
        )
        report = run_campaign_suite(build_all_campaigns())
        failed = [
            cid for cid, r in report["results"].items()
            if not r.get("passed")
        ]
        assert not failed, f"RT-FINAL: campaigns not blocked: {failed}"

    def test_cde_envelope_locks_and_validates(self):
        """CDE trust envelope must lock and validate promotions."""
        from spectrum_systems.governance.cde_trust_envelope import CDETrustEnvelope
        cde = CDETrustEnvelope()
        cde.lock_envelope()
        assert cde.is_locked()
        ok, _ = cde.verify_promotion_against_envelope({"artifact_type": "test"})
        assert ok

    def test_gate_rerun_all_green_before_final_lock(self):
        """Full gate rerun must show GREEN before issuing CDE lock."""
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        assert report["overall_status"] == "GREEN", (
            f"Not all gates green before lock: "
            + str({k: v["passed"] for k, v in report["gates"].items()})
        )

    def test_checkpoint_review_all_green(self):
        """PRG checkpoint review must show all GREEN SLIs."""
        from spectrum_systems.governance.checkpoint_review import emit_checkpoint_review_artifact
        rec = emit_checkpoint_review_artifact(
            eval_pass_rate=1.0,
            lineage_completeness_pct=100.0,
            replay_determinism_pct=100.0,
            drift_rate_daily=0.0,
            cde_envelope_locked=True,
        )
        assert rec["summary"]["overall_status"] == "GREEN"
