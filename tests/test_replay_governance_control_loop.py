"""Tests for BAA — Replay Governance Control Loop Integration.

Mandatory tests as required by PROMPT BAA:

 1.  Missing trace_id when replay was consumed → schema FAIL
 2.  Inconsistent replay environment → drift flag / indeterminate decision
 3.  Low consistency_sli below rebuild threshold → block (require_rebuild)
 4.  Low consistency_sli below review threshold → require_review
 5.  Replay validation mode independence enforcement
     a. independent mode does not escalate
     b. shared mode with high-severity decision escalates to block
 6.  Replay decision status (replay_decision_status) is set on governed artifact
     a. consistent → pass
     b. drifted → drift
     c. indeterminate → indeterminate
 7.  Replay affects final system_response in control chain
     a. allow governance does not block continuation
     b. block governance blocks continuation
     c. require_review governance stops continuation (not automatic)
     d. replay_decision_status is propagated to control chain replay_governance object
 8.  Observability events emitted for replay lifecycle
 9.  Backward compatibility: absent replay governance skips enforcement
10.  SLI threshold configurable via policy
11.  replay_drift_event emitted when drift detected
12.  Trace + provenance linkage: original_run_id, replay_run_id, replay_artifact_ids
13.  Environment reproducibility context included in artifact
"""
from __future__ import annotations

import logging
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.replay_governance import (  # noqa: E402
    EVENT_REPLAY_COMPLETE,
    EVENT_REPLAY_DRIFT_DETECTED,
    EVENT_REPLAY_START,
    GOVERNANCE_STATUS_INVALID_INPUT,
    GOVERNANCE_STATUS_OK,
    GOVERNANCE_STATUS_POLICY_BLOCKED,
    REPLAY_DECISION_STATUS_DRIFT,
    REPLAY_DECISION_STATUS_INDETERMINATE,
    REPLAY_DECISION_STATUS_PASS,
    REPLAY_STATUS_CONSISTENT,
    REPLAY_STATUS_DRIFTED,
    REPLAY_STATUS_INDETERMINATE,
    REPLAY_VALIDATION_MODE_INDEPENDENT,
    REPLAY_VALIDATION_MODE_SHARED,
    SYSTEM_RESPONSE_ALLOW,
    SYSTEM_RESPONSE_BLOCK,
    SYSTEM_RESPONSE_QUARANTINE,
    SYSTEM_RESPONSE_REQUIRE_REVIEW,
    _DEFAULT_SLI_REBUILD_THRESHOLD,
    _DEFAULT_SLI_REVIEW_THRESHOLD,
    _apply_sli_thresholds,
    _replay_status_to_decision_status,
    build_replay_governance_decision,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_NAME = "replay_governance_decision"


def _load_schema() -> Dict[str, Any]:
    return load_schema(_SCHEMA_NAME)


def _validate(artifact: Dict[str, Any]) -> List[str]:
    schema = _load_schema()
    v = Draft202012Validator(schema, format_checker=FormatChecker())
    return [e.message for e in v.iter_errors(artifact)]


def _make_analysis(
    *,
    status: str = REPLAY_STATUS_CONSISTENT,
    score: float = 1.0,
    analysis_id: str = "analysis-001",
    trace_id: str = "trace-001",
    replay_result_id: str = "replay-run-001",
) -> Dict[str, Any]:
    return {
        "analysis_id": analysis_id,
        "trace_id": trace_id,
        "replay_result_id": replay_result_id,
        "original_decision": {
            "decision_status": "allow",
            "decision_reason_code": "slo_pass",
        },
        "replay_decision": {
            "decision_status": "allow",
            "decision_reason_code": "slo_pass",
        },
        "decision_consistency": {
            "status": status,
            "differences": [],
        },
        "reproducibility_score": score,
        "explanation": "Test artifact.",
        "created_at": "2026-01-01T00:00:00+00:00",
    }


# ===========================================================================
# 1. Missing trace_id when replay was consumed → schema FAIL
# ===========================================================================

class TestMissingTraceId:
    def test_missing_trace_id_fails_schema_when_replay_consumed(self):
        """BAA R2: trace_id REQUIRED when replay_analysis_artifact_id is non-null."""
        analysis = _make_analysis()
        result = build_replay_governance_decision(analysis, run_id="run-1")
        # The builder auto-extracts trace_id from analysis — confirm it's present
        assert "trace_id" in result, "Builder should auto-extract trace_id from analysis"
        assert result["trace_id"] == "trace-001"

        # Now manually remove trace_id to simulate a schema violation
        artifact_without_trace = deepcopy(result)
        del artifact_without_trace["trace_id"]
        errors = _validate(artifact_without_trace)
        assert any("trace_id" in e for e in errors), (
            f"Expected schema error for missing trace_id, got: {errors}"
        )

    def test_trace_id_present_and_valid_passes_schema(self):
        """When trace_id is provided or auto-extracted, schema passes."""
        analysis = _make_analysis(trace_id="trace-xyz")
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["trace_id"] == "trace-xyz"
        errors = _validate(result)
        assert errors == [], errors

    def test_explicit_trace_id_overrides_analysis_trace_id(self):
        """Caller-supplied trace_id takes precedence over analysis trace_id."""
        analysis = _make_analysis(trace_id="trace-from-analysis")
        result = build_replay_governance_decision(
            analysis, run_id="run-1", trace_id="trace-from-caller"
        )
        assert result["trace_id"] == "trace-from-caller"

    def test_trace_id_not_required_when_no_replay(self):
        """trace_id is NOT required when replay was not consumed (null artifact_id)."""
        result = build_replay_governance_decision(None, run_id="run-1")
        # No trace_id in result when no replay consumed
        assert result.get("replay_analysis_artifact_id") is None
        errors = _validate(result)
        assert errors == [], errors


# ===========================================================================
# 2. Inconsistent replay environment → drift / indeterminate
# ===========================================================================

class TestInconsistentEnvironment:
    def test_drifted_analysis_produces_drift_decision_status(self):
        """BAA R6: drifted replay produces replay_decision_status='drift'."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["replay_decision_status"] == REPLAY_DECISION_STATUS_DRIFT

    def test_indeterminate_analysis_produces_indeterminate_decision_status(self):
        """Indeterminate replay produces replay_decision_status='indeterminate'."""
        analysis = _make_analysis(status=REPLAY_STATUS_INDETERMINATE, score=0.7)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["replay_decision_status"] == REPLAY_DECISION_STATUS_INDETERMINATE

    def test_inconsistent_env_with_environment_context_flags_drift(self):
        """BAA R4: environment_context is included when provided; drift still detected."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.4)
        env_ctx = {
            "matlab_release": "R2024b",
            "runtime_version": "Python 3.11.9",
            "platform": "linux-x86_64",
            "seed_rng_state": "42",
        }
        result = build_replay_governance_decision(
            analysis, run_id="run-1", environment_context=env_ctx
        )
        assert result["replay_decision_status"] == REPLAY_DECISION_STATUS_DRIFT
        assert result["environment_context"] == env_ctx
        errors = _validate(result)
        assert errors == [], errors

    def test_drift_event_emitted_when_status_is_drift(self):
        """BAA R5: replay_drift_event is attached to artifact when drift detected."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert "replay_drift_event" in result, (
            "replay_drift_event must be present when replay_decision_status=drift"
        )
        drift_event = result["replay_drift_event"]
        assert drift_event["event_type"] == EVENT_REPLAY_DRIFT_DETECTED
        assert drift_event["run_id"] == "run-1"
        assert drift_event["replay_decision_status"] == REPLAY_DECISION_STATUS_DRIFT

    def test_no_drift_event_when_consistent(self):
        """replay_drift_event must NOT be present when replay is consistent."""
        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert "replay_drift_event" not in result


# ===========================================================================
# 3. Low consistency_sli triggers correct decision (BAA R1)
# ===========================================================================

class TestSliThresholds:
    def test_sli_below_rebuild_threshold_escalates_to_block(self):
        """BAA R1: consistency_sli < rebuild_threshold → block (require_rebuild)."""
        analysis = _make_analysis(
            status=REPLAY_STATUS_CONSISTENT,
            score=_DEFAULT_SLI_REBUILD_THRESHOLD - 0.1,
        )
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_BLOCK, (
            f"Expected block for SLI below rebuild threshold, got: {decision['system_response']}"
        )
        assert decision["severity"] == "critical"

    def test_sli_below_review_threshold_escalates_to_require_review(self):
        """BAA R1: rebuild_threshold <= sli < review_threshold → require_review."""
        sli = (_DEFAULT_SLI_REBUILD_THRESHOLD + _DEFAULT_SLI_REVIEW_THRESHOLD) / 2
        analysis = _make_analysis(
            status=REPLAY_STATUS_CONSISTENT,
            score=sli,
        )
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_REQUIRE_REVIEW, (
            f"Expected require_review for SLI below review threshold, got: {decision['system_response']}"
        )
        assert decision["severity"] == "warning"

    def test_sli_at_or_above_review_threshold_allows(self):
        """SLI at or above review threshold → allow (consistent replay)."""
        analysis = _make_analysis(
            status=REPLAY_STATUS_CONSISTENT,
            score=_DEFAULT_SLI_REVIEW_THRESHOLD,
        )
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_ALLOW

    def test_sli_thresholds_configurable_via_policy(self):
        """BAA R1: SLI thresholds can be overridden in governance policy."""
        custom_policy = {
            "policy_name": "custom_threshold",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_QUARANTINE,
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": False,
            "consistency_sli_rebuild_threshold": 0.3,
            "consistency_sli_review_threshold": 0.6,
        }
        # SLI=0.5 is between custom review threshold (0.3) and rebuild (0.6)
        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT, score=0.5)
        result = build_replay_governance_decision(
            analysis, run_id="run-1", governance_policy=custom_policy
        )
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_REQUIRE_REVIEW

        # SLI=0.25 is below custom rebuild threshold (0.3)
        analysis_low = _make_analysis(status=REPLAY_STATUS_CONSISTENT, score=0.25)
        result_low = build_replay_governance_decision(
            analysis_low, run_id="run-1", governance_policy=custom_policy
        )
        assert result_low["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK

    def test_sli_thresholds_not_applied_to_drifted_replay(self):
        """SLI threshold escalation must NOT further escalate drifted replays."""
        analysis = _make_analysis(
            status=REPLAY_STATUS_DRIFTED,
            score=0.0,  # Well below rebuild threshold
        )
        result = build_replay_governance_decision(analysis, run_id="run-1")
        # Drifted replay uses drift_action (quarantine by default), not block from threshold
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_QUARANTINE
        assert result["decision"]["rationale_code"] == "replay_drifted"

    def test_apply_sli_thresholds_helper_only_escalates_from_allow(self):
        """_apply_sli_thresholds only escalates when base decision is 'allow'."""
        policy = {
            "consistency_sli_rebuild_threshold": 0.5,
            "consistency_sli_review_threshold": 0.8,
        }
        quarantine_decision = {
            "system_response": SYSTEM_RESPONSE_QUARANTINE,
            "severity": "elevated",
            "replay_governed": True,
            "rationale_code": "replay_drifted",
            "rationale": "Drift detected.",
        }
        # Should not escalate quarantine even for very low SLI
        result = _apply_sli_thresholds(
            REPLAY_STATUS_DRIFTED, 0.0, policy, quarantine_decision
        )
        assert result["system_response"] == SYSTEM_RESPONSE_QUARANTINE


# ===========================================================================
# 4. Replay independence enforcement (BAA R3)
# ===========================================================================

class TestReplayIndependence:
    def test_independent_mode_does_not_escalate(self):
        """BAA R3: independent mode has no escalation effect."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        result = build_replay_governance_decision(
            analysis, run_id="run-1",
            replay_validation_mode=REPLAY_VALIDATION_MODE_INDEPENDENT,
        )
        # Independent mode: no additional escalation
        assert result["replay_validation_mode"] == REPLAY_VALIDATION_MODE_INDEPENDENT
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_QUARANTINE
        errors = _validate(result)
        assert errors == [], errors

    def test_shared_mode_with_high_severity_escalates_to_block(self):
        """BAA R3: shared mode + high-severity decision → escalated to block."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        # drifted + default policy = quarantine (elevated severity)
        # shared mode should escalate this to block
        result = build_replay_governance_decision(
            analysis, run_id="run-1",
            replay_validation_mode=REPLAY_VALIDATION_MODE_SHARED,
        )
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK, (
            "Shared mode with elevated/critical severity must escalate to block"
        )
        assert result["replay_validation_mode"] == REPLAY_VALIDATION_MODE_SHARED
        assert "independence not satisfied" in result["decision"]["rationale"].lower()

    def test_shared_mode_with_allow_does_not_escalate(self):
        """Shared mode with allow (consistent, high SLI) does NOT escalate."""
        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        result = build_replay_governance_decision(
            analysis, run_id="run-1",
            replay_validation_mode=REPLAY_VALIDATION_MODE_SHARED,
        )
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_ALLOW

    def test_replay_validation_mode_in_schema(self):
        """replay_validation_mode field is valid in the schema."""
        analysis = _make_analysis()
        result = build_replay_governance_decision(
            analysis, run_id="run-1",
            replay_validation_mode=REPLAY_VALIDATION_MODE_INDEPENDENT,
        )
        errors = _validate(result)
        assert errors == [], errors


# ===========================================================================
# 5. Replay decision status (BAA R6)
# ===========================================================================

class TestReplayDecisionStatus:
    @pytest.mark.parametrize("replay_status,expected_rds", [
        (REPLAY_STATUS_CONSISTENT, REPLAY_DECISION_STATUS_PASS),
        (REPLAY_STATUS_DRIFTED, REPLAY_DECISION_STATUS_DRIFT),
        (REPLAY_STATUS_INDETERMINATE, REPLAY_DECISION_STATUS_INDETERMINATE),
    ])
    def test_replay_status_maps_to_replay_decision_status(
        self, replay_status: str, expected_rds: str
    ):
        """BAA R6: replay_status maps deterministically to replay_decision_status."""
        result = _replay_status_to_decision_status(replay_status)
        assert result == expected_rds

    def test_replay_decision_status_present_in_governed_artifact(self):
        """replay_decision_status is present in governed artifacts."""
        for status, expected in [
            (REPLAY_STATUS_CONSISTENT, REPLAY_DECISION_STATUS_PASS),
            (REPLAY_STATUS_DRIFTED, REPLAY_DECISION_STATUS_DRIFT),
            (REPLAY_STATUS_INDETERMINATE, REPLAY_DECISION_STATUS_INDETERMINATE),
        ]:
            analysis = _make_analysis(status=status, score=1.0)
            result = build_replay_governance_decision(analysis, run_id="run-1")
            assert result.get("replay_decision_status") == expected, (
                f"Expected replay_decision_status={expected} for status={status}"
            )

    def test_replay_decision_status_absent_when_no_replay(self):
        """replay_decision_status is not set when no replay was consumed."""
        result = build_replay_governance_decision(None, run_id="run-1")
        assert "replay_decision_status" not in result

    def test_replay_decision_status_passes_schema(self):
        """Artifact with replay_decision_status passes schema validation."""
        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert "replay_decision_status" in result
        errors = _validate(result)
        assert errors == [], errors


# ===========================================================================
# 6. Replay affects final system_response in control chain (BAA R8)
# ===========================================================================

_TS = "2026-01-01T00:00:00+00:00"


def _slo_enforcement_decision(**overrides: Any) -> Dict[str, Any]:
    """Minimal valid slo_enforcement_decision for control chain tests."""
    base: Dict[str, Any] = {
        "artifact_type": "slo_enforcement_decision",
        "artifact_id": "art-baa-001",
        "stage": "observe",
        "decision_id": "dec-baa-001",
        "decision_status": "allow",
        "enforcement_policy": "default",
        "traceability_integrity_sli": 1.0,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "lineage_valid": True,
        "warnings": [],
        "errors": [],
        "recommended_action": "continue",
        "evaluated_at": _TS,
        "schema_version": "1.0.0",
        "source_decision_id": "dec-baa-001",
        "enforcement_decision_status": "allow",
        "gating_outcome": "proceed",
        "gating_decision_id": "gate-baa-001",
    }
    base.update(overrides)
    return base


def _mock_gating_proceed_baa() -> Dict[str, Any]:
    return {
        "gating_decision": {
            "gating_decision_id": "gate-baa-001",
            "gating_outcome": "proceed",
            "stage": "observe",
            "warnings": [],
            "errors": [],
        },
        "gating_outcome": "proceed",
        "schema_errors": [],
    }


class TestReplayAffectsControlChain:
    """Test that replay governance participates in final control chain decision (BAA R8)."""

    def test_allow_governance_does_not_block_continuation(self):
        """Replay governance=allow does not prevent continuation."""
        from spectrum_systems.modules.runtime.control_chain import run_control_chain
        from spectrum_systems.modules.runtime.decision_gating import STAGE_OBSERVE

        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        rg = build_replay_governance_decision(analysis, run_id="run-001")
        assert rg["decision"]["system_response"] == SYSTEM_RESPONSE_ALLOW

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed_baa(),
        ):
            result = run_control_chain(
                _slo_enforcement_decision(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=rg,
            )

        assert result["continuation_allowed"] is True
        rg_obj = result["control_chain_decision"].get("replay_governance", {})
        assert rg_obj.get("present") is True
        assert rg_obj.get("replay_decision_status") == REPLAY_DECISION_STATUS_PASS

    def test_block_governance_blocks_continuation(self):
        """Replay governance=block prevents continuation regardless of other decisions."""
        from spectrum_systems.modules.runtime.control_chain import run_control_chain
        from spectrum_systems.modules.runtime.decision_gating import STAGE_OBSERVE

        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        block_policy = {
            "policy_name": "strict",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_BLOCK,
            "indeterminate_action": SYSTEM_RESPONSE_BLOCK,
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": False,
        }
        rg = build_replay_governance_decision(
            analysis, run_id="run-001", governance_policy=block_policy
        )
        assert rg["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed_baa(),
        ):
            result = run_control_chain(
                _slo_enforcement_decision(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=rg,
            )

        assert result["continuation_allowed"] is False
        assert result["control_chain_decision"].get("blocking_layer") == "replay_governance"

    def test_require_review_governance_stops_continuation(self):
        """Replay governance=require_review stops automatic continuation."""
        from spectrum_systems.modules.runtime.control_chain import run_control_chain
        from spectrum_systems.modules.runtime.decision_gating import STAGE_OBSERVE

        analysis = _make_analysis(status=REPLAY_STATUS_INDETERMINATE, score=0.5)
        rg = build_replay_governance_decision(analysis, run_id="run-001")
        assert rg["decision"]["system_response"] == SYSTEM_RESPONSE_REQUIRE_REVIEW

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed_baa(),
        ):
            result = run_control_chain(
                _slo_enforcement_decision(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=rg,
            )

        assert result["continuation_allowed"] is False

    def test_replay_decision_status_propagated_to_control_chain(self):
        """BAA R6/R8: replay_decision_status propagates from governance to CC decision."""
        from spectrum_systems.modules.runtime.control_chain import run_control_chain
        from spectrum_systems.modules.runtime.decision_gating import STAGE_OBSERVE

        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        rg = build_replay_governance_decision(analysis, run_id="run-001")
        assert rg.get("replay_decision_status") == REPLAY_DECISION_STATUS_DRIFT

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed_baa(),
        ):
            result = run_control_chain(
                _slo_enforcement_decision(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=rg,
            )

        rg_obj = result["control_chain_decision"].get("replay_governance", {})
        assert rg_obj.get("replay_decision_status") == REPLAY_DECISION_STATUS_DRIFT, (
            "replay_decision_status must be propagated to control chain replay_governance object"
        )


# ===========================================================================
# 7. Observability events (BAA R9)
# ===========================================================================

class TestObservabilityEvents:
    def test_replay_start_and_complete_events_emitted(self, caplog):
        """BAA R9: REPLAY_START and REPLAY_COMPLETE events are emitted."""
        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT)
        with caplog.at_level(logging.DEBUG, logger="spectrum_systems.modules.runtime.replay_governance"):
            build_replay_governance_decision(analysis, run_id="run-1")

        log_messages = [r.message for r in caplog.records]
        assert any(EVENT_REPLAY_START in msg for msg in log_messages), (
            f"Expected {EVENT_REPLAY_START} in log, got: {log_messages}"
        )
        assert any(EVENT_REPLAY_COMPLETE in msg for msg in log_messages), (
            f"Expected {EVENT_REPLAY_COMPLETE} in log, got: {log_messages}"
        )

    def test_replay_drift_detected_event_emitted_on_drift(self, caplog):
        """BAA R9: REPLAY_DRIFT_DETECTED event emitted when drift detected."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        with caplog.at_level(logging.WARNING, logger="spectrum_systems.modules.runtime.replay_governance"):
            build_replay_governance_decision(analysis, run_id="run-1")

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(EVENT_REPLAY_DRIFT_DETECTED in msg for msg in warning_messages), (
            f"Expected {EVENT_REPLAY_DRIFT_DETECTED} warning, got: {warning_messages}"
        )

    def test_no_drift_event_when_consistent(self, caplog):
        """REPLAY_DRIFT_DETECTED must NOT be emitted for consistent replay."""
        analysis = _make_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        with caplog.at_level(logging.WARNING, logger="spectrum_systems.modules.runtime.replay_governance"):
            build_replay_governance_decision(analysis, run_id="run-1")

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert not any(EVENT_REPLAY_DRIFT_DETECTED in msg for msg in warning_messages)


# ===========================================================================
# 8. Backward compatibility (BAA R10)
# ===========================================================================

class TestBackwardCompatibility:
    def test_absent_replay_governance_skips_enforcement(self):
        """BAA R10: If replay governance is absent, no enforcement occurs."""
        result = build_replay_governance_decision(None, run_id="run-1", require_replay=False)
        assert result["decision"]["replay_governed"] is False
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_ALLOW
        assert result.get("replay_analysis_artifact_id") is None
        errors = _validate(result)
        assert errors == [], errors

    def test_absent_replay_governance_passes_schema(self):
        """BAA R10: Artifact without replay governance fields passes schema."""
        result = build_replay_governance_decision(None, run_id="run-1")
        errors = _validate(result)
        assert errors == [], errors

    def test_no_replay_decision_status_when_absent(self):
        """replay_decision_status absent when no replay was consumed."""
        result = build_replay_governance_decision(None, run_id="run-1")
        assert "replay_decision_status" not in result


# ===========================================================================
# 9. Trace + provenance linkage (BAA R2)
# ===========================================================================

class TestTraceProvenance:
    def test_replay_run_id_auto_extracted_from_analysis(self):
        """BAA R2: replay_run_id auto-extracted from analysis.replay_result_id."""
        analysis = _make_analysis(replay_result_id="replay-run-xyz")
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["replay_run_id"] == "replay-run-xyz"

    def test_explicit_replay_run_id_overrides_analysis(self):
        """Caller-supplied replay_run_id takes precedence."""
        analysis = _make_analysis(replay_result_id="replay-from-analysis")
        result = build_replay_governance_decision(
            analysis, run_id="run-1", replay_run_id="replay-from-caller"
        )
        assert result["replay_run_id"] == "replay-from-caller"

    def test_original_run_id_included_when_provided(self):
        """BAA R2: original_run_id is included when provided."""
        analysis = _make_analysis()
        result = build_replay_governance_decision(
            analysis, run_id="run-1", original_run_id="original-run-001"
        )
        assert result["original_run_id"] == "original-run-001"
        errors = _validate(result)
        assert errors == [], errors

    def test_replay_artifact_ids_included_when_provided(self):
        """BAA R2: replay_artifact_ids list included when provided."""
        analysis = _make_analysis()
        artifact_ids = ["artifact-001", "artifact-002"]
        result = build_replay_governance_decision(
            analysis, run_id="run-1", replay_artifact_ids=artifact_ids
        )
        assert result["replay_artifact_ids"] == artifact_ids
        errors = _validate(result)
        assert errors == [], errors

    def test_replay_run_id_required_by_schema_when_replay_consumed(self):
        """replay_run_id is REQUIRED by schema when replay was consumed."""
        analysis = _make_analysis()
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert "replay_run_id" in result

        # Removing replay_run_id with non-null artifact_id should fail schema
        artifact_without_run_id = deepcopy(result)
        del artifact_without_run_id["replay_run_id"]
        errors = _validate(artifact_without_run_id)
        assert any("replay_run_id" in e for e in errors), (
            f"Expected schema error for missing replay_run_id, got: {errors}"
        )


# ===========================================================================
# 10. Environment reproducibility contract (BAA R4)
# ===========================================================================

class TestEnvironmentReproducibility:
    def test_environment_context_valid_schema(self):
        """BAA R4: Full environment_context passes schema validation."""
        analysis = _make_analysis()
        env_ctx = {
            "matlab_release": "R2024b",
            "runtime_version": "Python 3.11.9",
            "platform": "linux-x86_64",
            "seed_rng_state": "12345",
        }
        result = build_replay_governance_decision(
            analysis, run_id="run-1", environment_context=env_ctx
        )
        assert result["environment_context"] == env_ctx
        errors = _validate(result)
        assert errors == [], errors

    def test_environment_context_with_null_seed(self):
        """Null seed_rng_state is valid in environment_context."""
        analysis = _make_analysis()
        env_ctx = {
            "matlab_release": "R2024b",
            "runtime_version": "Python 3.11.9",
            "platform": "linux-x86_64",
            "seed_rng_state": None,
        }
        result = build_replay_governance_decision(
            analysis, run_id="run-1", environment_context=env_ctx
        )
        errors = _validate(result)
        assert errors == [], errors

    def test_environment_context_absent_by_default(self):
        """environment_context is not added to artifact when not provided."""
        analysis = _make_analysis()
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert "environment_context" not in result


# ===========================================================================
# 11. Schema validation coverage (BAA R7)
# ===========================================================================

class TestSchemaUpdates:
    def test_replay_decision_status_enum_enforced(self):
        """BAA R7: Invalid replay_decision_status enum value is rejected."""
        import json
        from pathlib import Path
        schema_path = _REPO_ROOT / "contracts" / "schemas" / "replay_governance_decision.schema.json"
        schema = json.loads(schema_path.read_text())
        v = Draft202012Validator(schema, format_checker=FormatChecker())

        analysis = _make_analysis()
        result = build_replay_governance_decision(analysis, run_id="run-1")
        result["replay_decision_status"] = "invalid_status"
        errors = [e.message for e in v.iter_errors(result)]
        assert any("replay_decision_status" in e or "invalid_status" in e for e in errors)

    def test_slo_control_chain_replay_decision_status_in_schema(self):
        """BAA R7: slo_control_chain_decision schema includes replay_decision_status."""
        import json
        from pathlib import Path
        cc_schema_path = _REPO_ROOT / "contracts" / "schemas" / "slo_control_chain_decision.schema.json"
        cc_schema = json.loads(cc_schema_path.read_text())
        rg_def = cc_schema["$defs"]["replay_governance"]
        assert "replay_decision_status" in rg_def["properties"], (
            "slo_control_chain_decision.schema.json must include replay_decision_status "
            "in replay_governance $def"
        )

    def test_sli_thresholds_valid_in_policy_schema(self):
        """BAA R7: SLI threshold fields valid in governance_policy schema."""
        analysis = _make_analysis()
        policy = {
            "policy_name": "sli_threshold_test",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_QUARANTINE,
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": False,
            "consistency_sli_rebuild_threshold": 0.4,
            "consistency_sli_review_threshold": 0.7,
        }
        result = build_replay_governance_decision(
            analysis, run_id="run-1", governance_policy=policy
        )
        errors = _validate(result)
        assert errors == [], errors

    def test_replay_drift_event_schema_valid(self):
        """BAA R5/R7: replay_drift_event passes schema validation."""
        analysis = _make_analysis(status=REPLAY_STATUS_DRIFTED, score=0.6)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert "replay_drift_event" in result
        errors = _validate(result)
        assert errors == [], errors
