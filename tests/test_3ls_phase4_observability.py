"""Phase 4 Observability, Lineage & Replay tests: OBS emitter, LIN verifier,
REP replay gate, ROU route evidence, DRT drift remediation.

GATE-O compliance tests.
"""

import pytest


# ── OBS Completeness ─────────────────────────────────────────────────────────


class TestOBSEmitter:
    def setup_method(self):
        from spectrum_systems.modules.observability.obs_emitter import OBSEmitter
        self.emitter = OBSEmitter()

    def test_emit_produces_obs_record_artifact(self):
        rec = self.emitter.emit_obs_record("TRC-001", ["ART-A"], 100, 50)
        assert rec["artifact_type"] == "obs_record"

    def test_emit_includes_trace_id(self):
        rec = self.emitter.emit_obs_record("TRC-TEST", [], 0, 0)
        assert rec["trace_id"] == "TRC-TEST"

    def test_emit_includes_all_required_fields(self):
        rec = self.emitter.emit_obs_record("TRC-X", ["A1", "A2"], 200, 100)
        assert "artifact_id" in rec
        assert "duration_ms" in rec
        assert "cost_tokens" in rec
        assert rec["duration_ms"] == 200
        assert rec["cost_tokens"] == 100

    def test_raises_on_empty_trace_id(self):
        with pytest.raises(ValueError, match="trace_id"):
            self.emitter.emit_obs_record("", [], 0, 0)

    def test_raises_on_negative_duration(self):
        with pytest.raises(ValueError, match="duration_ms"):
            self.emitter.emit_obs_record("TRC-N", [], -1, 0)


# ── LIN Lineage Verifier ──────────────────────────────────────────────────────


class TestLineageVerifier:
    def setup_method(self):
        from spectrum_systems.modules.lineage.lineage_verifier import verify_lineage_completeness
        self.verify = verify_lineage_completeness

    def test_fails_when_store_unavailable(self):
        ok, errors = self.verify("ART-001", artifact_store=None)
        assert not ok
        assert any("unavailable" in e or "fail-closed" in e for e in errors)

    def test_valid_chain_to_input_artifact(self):
        store = {
            "ART-OUT": {"artifact_type": "pqx_output", "upstream_artifacts": ["ART-IN"]},
            "ART-IN": {"artifact_type": "input_bundle", "upstream_artifacts": []},
        }
        ok, errors = self.verify("ART-OUT", artifact_store=store)
        assert ok, f"Expected complete lineage, got: {errors}"

    def test_detects_missing_upstream_artifact(self):
        store = {
            "ART-OUT": {"artifact_type": "pqx_output", "upstream_artifacts": ["MISSING-ART"]},
        }
        ok, errors = self.verify("ART-OUT", artifact_store=store)
        assert not ok
        assert any("MISSING-ART" in e for e in errors)

    def test_detects_orphaned_artifact_non_input_type(self):
        store = {
            "ART-ORPHAN": {"artifact_type": "some_derived_artifact", "upstream_artifacts": []},
        }
        ok, errors = self.verify("ART-ORPHAN", artifact_store=store)
        assert not ok


# ── REP Replay Gate ──────────────────────────────────────────────────────────


class TestReplayGate:
    def setup_method(self):
        from spectrum_systems.modules.replay.replay_gate import check_replay_determinism
        self.check = check_replay_determinism

    def test_identical_hashes_are_deterministic(self):
        result = self.check("ART-X", ["hash1", "hash1", "hash1"])
        assert result["deterministic"] is True

    def test_different_hashes_detect_divergence(self):
        result = self.check("ART-Y", ["h1", "h2", "h1"])
        assert result["deterministic"] is False
        assert result["hash_variance"] == 2

    def test_empty_hashes_fail_closed(self):
        result = self.check("ART-Z", [])
        assert result["deterministic"] is False


# ── ROU Route Evidence ────────────────────────────────────────────────────────


class TestRouteEvidence:
    def setup_method(self):
        from spectrum_systems.modules.routing.route_evidence import RouteEvidenceEmitter
        self.emitter = RouteEvidenceEmitter()

    def test_emits_route_record(self):
        rec = self.emitter.route_artifact("AEX", "PQX", "ART-001", "normal routing")
        assert rec["artifact_type"] == "route_record"

    def test_route_record_has_all_fields(self):
        rec = self.emitter.route_artifact("TLC", "CDE", "ART-002", "closure routing", "TRC-TEST")
        assert rec["from_system"] == "TLC"
        assert rec["to_system"] == "CDE"
        assert rec["routed_artifact_id"] == "ART-002"
        assert rec["trace_id"] == "TRC-TEST"

    def test_raises_on_missing_reason(self):
        with pytest.raises(ValueError):
            self.emitter.route_artifact("A", "B", "ART-003", "")


# ── DRT Drift Remediation ─────────────────────────────────────────────────────


class TestDriftRemediationEnforcer:
    def setup_method(self):
        from spectrum_systems.drift.drift_remediation_enforcer import DriftRemediationEnforcer
        self.enforcer = DriftRemediationEnforcer()

    def test_proceeds_when_no_drift_signals(self):
        action, report = self.enforcer.check_remediation_deadlines()
        assert action == "PROCEED"

    def test_proceeds_when_drift_has_remediation(self):
        self.enforcer.register_drift_signal("DRF-001", "registry mismatch")
        self.enforcer.register_remediation("DRF-001", {"plan": "update registry"})
        action, _ = self.enforcer.check_remediation_deadlines()
        assert action == "PROCEED"

    def test_freezes_when_execution_limit_exceeded(self):
        self.enforcer.register_drift_signal("DRF-002", "schema mismatch")
        # Exceed execution limit
        for _ in range(3):
            self.enforcer.increment_execution("DRF-002")
        action, report = self.enforcer.check_remediation_deadlines()
        assert action == "FREEZE"


# ── RT-O Red Team ────────────────────────────────────────────────────────────


class TestRedTeamObservability:
    def test_chx011_obs_record_emitted(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_observability_campaigns
        chx011 = next(c for c in _make_observability_campaigns() if c.campaign_id == "CHX-011")
        result = chx011.run()
        assert result["passed"], f"CHX-011 failed: {result['message']}"

    def test_chx012_orphaned_artifact_detected(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_observability_campaigns
        chx012 = next(c for c in _make_observability_campaigns() if c.campaign_id == "CHX-012")
        result = chx012.run()
        assert result["passed"], f"CHX-012 failed: {result['message']}"

    def test_chx013_replay_divergence_detected(self):
        from spectrum_systems.modules.wpg.redteam_campaigns import _make_observability_campaigns
        chx013 = next(c for c in _make_observability_campaigns() if c.campaign_id == "CHX-013")
        result = chx013.run()
        assert result["passed"], f"CHX-013 failed: {result['message']}"
