"""Tests for BY — Replay Governance Gate (replay_governance.py).

Covers:
 1.  Schema tests
     a. Valid replay governance decision passes schema
     b. Extra fields rejected
     c. Invalid enums rejected
     d. Missing required fields rejected
     e. artifact_type const constraint enforced

 2.  Decision logic tests
     a. consistent replay → allow / info / replay_consistent
     b. drifted replay + default policy → quarantine / elevated / replay_drifted
     c. drifted replay + block policy → block / critical / replay_drifted
     d. indeterminate replay + default policy → require_review / warning / replay_indeterminate
     e. indeterminate replay + block policy → block / warning / replay_indeterminate
     f. missing replay when not required → allow / replay_governed=False / replay_not_required
     g. missing replay when required (caller flag) → missing_replay_action enforced
     h. missing replay when required (policy flag) → missing_replay_action enforced
     i. malformed replay artifact (not a dict) → block
     j. malformed replay artifact (missing analysis_id) → block
     k. unknown replay status → block / replay_unknown_status
     l. replay SLI out of range (> 1) → block
     m. replay SLI out of range (< 0) → block
     n. replay SLI non-numeric → block

 3.  Control chain integration tests
     a. replay governance allow does not escalate final control decision
     b. replay governance require_review escalates allow → continuation=False
     c. replay governance quarantine escalates allow → continuation=False
     d. replay governance block escalates any weaker response → continuation=False
     e. replay governance escalated fields visible in control chain decision
     f. publish/promotion path prevented when replay governance says quarantine
     g. automatic execution prevented when replay governance says require_review

 4.  merge_system_responses tests
     a. empty list → block (fail closed)
     b. all allow → allow
     c. allow + require_review → require_review
     d. allow + quarantine → quarantine
     e. any block → block
     f. unknown value → block
     g. precedence: block > quarantine > require_review > allow

 5.  Regression / compatibility tests
     a. systems without replay continue to work (replay None, not required)
     b. invalid replay never silently downgrades to allow
     c. governance policy validation catches bad drift_action
     d. governance policy validation catches bad indeterminate_action
     e. governance policy validation catches bad missing_replay_action
     f. governance policy validation catches non-bool require_replay

 6.  Query helpers
     a. should_block_from_replay_governance
     b. should_require_review_from_replay_governance
     c. should_quarantine_from_replay_governance

 7.  Summary
     a. summarize_replay_governance_decision returns correct fields
     b. escalation flag is True when not allow
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.replay_governance import (  # noqa: E402
    GOVERNANCE_STATUS_INVALID_INPUT,
    GOVERNANCE_STATUS_OK,
    GOVERNANCE_STATUS_POLICY_BLOCKED,
    REPLAY_STATUS_CONSISTENT,
    REPLAY_STATUS_DRIFTED,
    REPLAY_STATUS_INDETERMINATE,
    SYSTEM_RESPONSE_ALLOW,
    SYSTEM_RESPONSE_BLOCK,
    SYSTEM_RESPONSE_QUARANTINE,
    SYSTEM_RESPONSE_REQUIRE_REVIEW,
    InvalidReplayGovernanceInputError,
    ReplayGovernancePolicyError,
    _derive_replay_governance_decision,
    _validate_governance_policy,
    _validate_replay_analysis,
    build_replay_governance_decision,
    merge_system_responses,
    should_block_from_replay_governance,
    should_quarantine_from_replay_governance,
    should_require_review_from_replay_governance,
    summarize_replay_governance_decision,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_NAME = "replay_governance_decision"


def _load_governance_schema() -> Dict[str, Any]:
    return load_schema(_SCHEMA_NAME)


def _validate_against_schema(artifact: Dict[str, Any]) -> list:
    schema = _load_governance_schema()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [e.message for e in validator.iter_errors(artifact)]


def _make_replay_analysis(
    *,
    status: str = REPLAY_STATUS_CONSISTENT,
    score: float = 1.0,
    analysis_id: str = "analysis-001",
) -> Dict[str, Any]:
    """Build a minimal valid replay_decision_analysis dict."""
    return {
        "analysis_id": analysis_id,
        "trace_id": "trace-001",
        "replay_result_id": "replay-001",
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


def _make_governance_artifact(
    *,
    system_response: str = SYSTEM_RESPONSE_ALLOW,
    replay_status: Optional[str] = REPLAY_STATUS_CONSISTENT,
    sli: Optional[float] = 1.0,
    rationale_code: str = "replay_consistent",
    gov_status: str = GOVERNANCE_STATUS_OK,
    replay_governed: bool = True,
) -> Dict[str, Any]:
    """Build a minimal valid replay_governance_decision artifact."""
    return {
        "artifact_type": "replay_governance_decision",
        "schema_version": "1.0.0",
        "replay_analysis_artifact_id": "analysis-001",
        "run_id": "run-001",
        "evaluated_at": "2026-01-01T00:00:00+00:00",
        "replay_status": replay_status,
        "replay_consistency_sli": sli,
        "governance_policy": {
            "policy_name": "default_replay_governance",
            "policy_version": "1.0.0",
            "drift_action": "quarantine",
            "indeterminate_action": "require_review",
            "missing_replay_action": "allow",
            "require_replay": False,
        },
        "decision": {
            "system_response": system_response,
            "severity": "info",
            "replay_governed": replay_governed,
            "rationale_code": rationale_code,
            "rationale": "Test rationale.",
        },
        "enforcement_reason": {
            "summary": "Test summary.",
            "details": ["detail1"],
        },
        "status": gov_status,
    }


# ===========================================================================
# 1. Schema tests
# ===========================================================================


class TestSchema:
    def test_valid_artifact_passes_schema(self):
        artifact = _make_governance_artifact()
        errors = _validate_against_schema(artifact)
        assert errors == [], errors

    def test_extra_fields_rejected(self):
        artifact = _make_governance_artifact()
        artifact["unexpected_field"] = "extra"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_invalid_system_response_enum_rejected(self):
        artifact = _make_governance_artifact()
        artifact["decision"]["system_response"] = "proceed"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_invalid_status_enum_rejected(self):
        artifact = _make_governance_artifact()
        artifact["status"] = "unknown_status"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_missing_run_id_rejected(self):
        artifact = _make_governance_artifact()
        del artifact["run_id"]
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_missing_artifact_type_rejected(self):
        artifact = _make_governance_artifact()
        del artifact["artifact_type"]
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_artifact_type_const_enforced(self):
        artifact = _make_governance_artifact()
        artifact["artifact_type"] = "wrong_type"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_invalid_rationale_code_rejected(self):
        artifact = _make_governance_artifact()
        artifact["decision"]["rationale_code"] = "made_up_code"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_invalid_severity_rejected(self):
        artifact = _make_governance_artifact()
        artifact["decision"]["severity"] = "catastrophic"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_sli_out_of_range_rejected(self):
        artifact = _make_governance_artifact(sli=1.5)
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_drift_action_enum_enforced(self):
        artifact = _make_governance_artifact()
        artifact["governance_policy"]["drift_action"] = "ignore"
        errors = _validate_against_schema(artifact)
        assert len(errors) > 0

    def test_replay_status_null_allowed(self):
        artifact = _make_governance_artifact(replay_status=None, sli=None)
        artifact["replay_analysis_artifact_id"] = None
        errors = _validate_against_schema(artifact)
        assert errors == [], errors

    def test_trace_id_optional(self):
        artifact = _make_governance_artifact()
        assert "trace_id" not in artifact
        errors = _validate_against_schema(artifact)
        assert errors == []
        artifact["trace_id"] = "trace-abc"
        errors = _validate_against_schema(artifact)
        assert errors == []


# ===========================================================================
# 2. Decision logic tests
# ===========================================================================


class TestDecisionLogic:
    def test_consistent_replay_allows(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_ALLOW
        assert decision["severity"] == "info"
        assert decision["replay_governed"] is True
        assert decision["rationale_code"] == "replay_consistent"
        assert result["status"] == GOVERNANCE_STATUS_OK

    def test_drifted_replay_default_policy_quarantines(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_QUARANTINE
        assert decision["severity"] == "elevated"
        assert decision["replay_governed"] is True
        assert decision["rationale_code"] == "replay_drifted"
        assert result["status"] == GOVERNANCE_STATUS_POLICY_BLOCKED

    def test_drifted_replay_block_policy_blocks(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        block_policy = {
            "policy_name": "strict",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_BLOCK,
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": False,
        }
        result = build_replay_governance_decision(
            analysis, run_id="run-1", governance_policy=block_policy
        )
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_BLOCK
        assert decision["severity"] == "critical"
        assert decision["rationale_code"] == "replay_drifted"

    def test_indeterminate_replay_default_policy_requires_review(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_INDETERMINATE, score=0.5)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_REQUIRE_REVIEW
        assert decision["severity"] == "warning"
        assert decision["replay_governed"] is True
        assert decision["rationale_code"] == "replay_indeterminate"

    def test_indeterminate_replay_stricter_policy_blocks(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_INDETERMINATE, score=0.5)
        strict_policy = {
            "policy_name": "strict",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_BLOCK,
            "indeterminate_action": SYSTEM_RESPONSE_BLOCK,
            "missing_replay_action": SYSTEM_RESPONSE_BLOCK,
            "require_replay": False,
        }
        result = build_replay_governance_decision(
            analysis, run_id="run-1", governance_policy=strict_policy
        )
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK

    def test_missing_replay_not_required_allows(self):
        result = build_replay_governance_decision(None, run_id="run-1", require_replay=False)
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_ALLOW
        assert decision["replay_governed"] is False
        assert decision["rationale_code"] == "replay_not_required"
        assert result["status"] == GOVERNANCE_STATUS_OK

    def test_missing_replay_require_replay_caller_applies_missing_action(self):
        result = build_replay_governance_decision(None, run_id="run-1", require_replay=True)
        decision = result["decision"]
        assert decision["rationale_code"] == "replay_missing_required"
        # Default policy missing_replay_action=allow
        assert decision["system_response"] == SYSTEM_RESPONSE_ALLOW

    def test_missing_replay_policy_require_replay_applies_missing_action(self):
        policy = {
            "policy_name": "require_replay_policy",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_QUARANTINE,
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": SYSTEM_RESPONSE_BLOCK,
            "require_replay": True,
        }
        result = build_replay_governance_decision(
            None, run_id="run-1", governance_policy=policy
        )
        decision = result["decision"]
        assert decision["rationale_code"] == "replay_missing_required"
        assert decision["system_response"] == SYSTEM_RESPONSE_BLOCK

    def test_malformed_replay_not_dict_blocks(self):
        result = build_replay_governance_decision("not_a_dict", run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_BLOCK
        assert decision["rationale_code"] == "replay_invalid_artifact"
        assert result["status"] == GOVERNANCE_STATUS_INVALID_INPUT

    def test_malformed_replay_missing_analysis_id_blocks(self):
        analysis = _make_replay_analysis()
        del analysis["analysis_id"]
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_BLOCK
        assert decision["rationale_code"] == "replay_invalid_artifact"

    def test_unknown_replay_status_blocks(self):
        analysis = _make_replay_analysis()
        analysis["decision_consistency"]["status"] = "totally_unknown"
        result = build_replay_governance_decision(analysis, run_id="run-1")
        decision = result["decision"]
        assert decision["system_response"] == SYSTEM_RESPONSE_BLOCK
        assert decision["rationale_code"] == "replay_invalid_artifact"

    def test_replay_sli_out_of_range_high_blocks(self):
        analysis = _make_replay_analysis(score=1.5)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK
        assert result["decision"]["rationale_code"] == "replay_invalid_artifact"

    def test_replay_sli_out_of_range_low_blocks(self):
        analysis = _make_replay_analysis(score=-0.1)
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK

    def test_replay_sli_non_numeric_blocks(self):
        analysis = _make_replay_analysis()
        analysis["reproducibility_score"] = "high"
        result = build_replay_governance_decision(analysis, run_id="run-1")
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK

    def test_result_passes_schema_validation(self):
        for status, score in [
            (REPLAY_STATUS_CONSISTENT, 1.0),
            (REPLAY_STATUS_DRIFTED, 0.0),
            (REPLAY_STATUS_INDETERMINATE, 0.5),
        ]:
            analysis = _make_replay_analysis(status=status, score=score)
            result = build_replay_governance_decision(analysis, run_id="run-1")
            errors = _validate_against_schema(result)
            assert errors == [], f"Schema errors for {status}: {errors}"

    def test_trace_id_propagated(self):
        analysis = _make_replay_analysis()
        result = build_replay_governance_decision(
            analysis, run_id="run-1", trace_id="trace-xyz"
        )
        assert result.get("trace_id") == "trace-xyz"

    def test_evaluated_at_override(self):
        analysis = _make_replay_analysis()
        ts = "2025-06-15T10:00:00+00:00"
        result = build_replay_governance_decision(
            analysis, run_id="run-1", evaluated_at=ts
        )
        assert result["evaluated_at"] == ts


# ===========================================================================
# 3. Merge system responses tests
# ===========================================================================


class TestMergeSystemResponses:
    def test_empty_list_blocks(self):
        assert merge_system_responses([]) == SYSTEM_RESPONSE_BLOCK

    def test_all_allow_stays_allow(self):
        assert merge_system_responses([SYSTEM_RESPONSE_ALLOW, SYSTEM_RESPONSE_ALLOW]) == SYSTEM_RESPONSE_ALLOW

    def test_allow_plus_require_review(self):
        assert (
            merge_system_responses([SYSTEM_RESPONSE_ALLOW, SYSTEM_RESPONSE_REQUIRE_REVIEW])
            == SYSTEM_RESPONSE_REQUIRE_REVIEW
        )

    def test_allow_plus_quarantine(self):
        assert (
            merge_system_responses([SYSTEM_RESPONSE_ALLOW, SYSTEM_RESPONSE_QUARANTINE])
            == SYSTEM_RESPONSE_QUARANTINE
        )

    def test_any_block_wins(self):
        responses = [
            SYSTEM_RESPONSE_ALLOW,
            SYSTEM_RESPONSE_REQUIRE_REVIEW,
            SYSTEM_RESPONSE_BLOCK,
        ]
        assert merge_system_responses(responses) == SYSTEM_RESPONSE_BLOCK

    def test_unknown_value_blocks(self):
        assert merge_system_responses([SYSTEM_RESPONSE_ALLOW, "proceed"]) == SYSTEM_RESPONSE_BLOCK

    def test_precedence_order(self):
        assert (
            merge_system_responses([
                SYSTEM_RESPONSE_QUARANTINE,
                SYSTEM_RESPONSE_REQUIRE_REVIEW,
                SYSTEM_RESPONSE_ALLOW,
            ])
            == SYSTEM_RESPONSE_QUARANTINE
        )

    def test_block_beats_quarantine(self):
        assert (
            merge_system_responses([SYSTEM_RESPONSE_QUARANTINE, SYSTEM_RESPONSE_BLOCK])
            == SYSTEM_RESPONSE_BLOCK
        )


# ===========================================================================
# 4. Query helpers
# ===========================================================================


class TestQueryHelpers:
    def test_should_block(self):
        artifact = _make_governance_artifact(system_response=SYSTEM_RESPONSE_BLOCK)
        assert should_block_from_replay_governance(artifact) is True
        artifact2 = _make_governance_artifact(system_response=SYSTEM_RESPONSE_ALLOW)
        assert should_block_from_replay_governance(artifact2) is False

    def test_should_require_review(self):
        artifact = _make_governance_artifact(system_response=SYSTEM_RESPONSE_REQUIRE_REVIEW)
        assert should_require_review_from_replay_governance(artifact) is True
        artifact2 = _make_governance_artifact(system_response=SYSTEM_RESPONSE_ALLOW)
        assert should_require_review_from_replay_governance(artifact2) is False

    def test_should_quarantine(self):
        artifact = _make_governance_artifact(system_response=SYSTEM_RESPONSE_QUARANTINE)
        assert should_quarantine_from_replay_governance(artifact) is True
        artifact2 = _make_governance_artifact(system_response=SYSTEM_RESPONSE_ALLOW)
        assert should_quarantine_from_replay_governance(artifact2) is False


# ===========================================================================
# 5. Summary
# ===========================================================================


class TestSummary:
    def test_summarize_returns_required_fields(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        artifact = build_replay_governance_decision(analysis, run_id="run-1")
        summary = summarize_replay_governance_decision(artifact)

        assert "replay_governance_response" in summary
        assert "replay_governance_rationale_code" in summary
        assert "replay_status" in summary
        assert "replay_consistency_sli" in summary
        assert "replay_governance_escalated_final_decision" in summary
        assert summary["replay_governance_response"] == SYSTEM_RESPONSE_QUARANTINE
        assert summary["replay_status"] == REPLAY_STATUS_DRIFTED

    def test_escalation_flag_true_when_not_allow(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        artifact = build_replay_governance_decision(analysis, run_id="run-1")
        summary = summarize_replay_governance_decision(artifact)
        assert summary["replay_governance_escalated_final_decision"] is True

    def test_escalation_flag_false_when_allow(self):
        analysis = _make_replay_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        artifact = build_replay_governance_decision(analysis, run_id="run-1")
        summary = summarize_replay_governance_decision(artifact)
        assert summary["replay_governance_escalated_final_decision"] is False


# ===========================================================================
# 6. Regression / compatibility
# ===========================================================================


class TestRegressionCompat:
    def test_no_replay_no_require_passes_through(self):
        result = build_replay_governance_decision(None, run_id="run-1")
        assert result["decision"]["system_response"] == SYSTEM_RESPONSE_ALLOW
        assert result["decision"]["replay_governed"] is False

    def test_invalid_replay_never_allows(self):
        bad_analysis = {"broken": True}
        result = build_replay_governance_decision(bad_analysis, run_id="run-1")
        assert result["decision"]["system_response"] != SYSTEM_RESPONSE_ALLOW

    def test_policy_validation_bad_drift_action(self):
        bad_policy = {
            "policy_name": "bad",
            "policy_version": "1.0.0",
            "drift_action": "ignore",
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": False,
        }
        with pytest.raises(ReplayGovernancePolicyError):
            _validate_governance_policy(bad_policy)

    def test_policy_validation_bad_indeterminate_action(self):
        bad_policy = {
            "policy_name": "bad",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_QUARANTINE,
            "indeterminate_action": "monitor",
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": False,
        }
        with pytest.raises(ReplayGovernancePolicyError):
            _validate_governance_policy(bad_policy)

    def test_policy_validation_bad_missing_replay_action(self):
        bad_policy = {
            "policy_name": "bad",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_QUARANTINE,
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": "skip",
            "require_replay": False,
        }
        with pytest.raises(ReplayGovernancePolicyError):
            _validate_governance_policy(bad_policy)

    def test_policy_validation_non_bool_require_replay(self):
        bad_policy = {
            "policy_name": "bad",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_QUARANTINE,
            "indeterminate_action": SYSTEM_RESPONSE_REQUIRE_REVIEW,
            "missing_replay_action": SYSTEM_RESPONSE_ALLOW,
            "require_replay": "yes",
        }
        with pytest.raises(ReplayGovernancePolicyError):
            _validate_governance_policy(bad_policy)

    def test_validate_replay_analysis_raises_on_non_dict(self):
        with pytest.raises(InvalidReplayGovernanceInputError):
            _validate_replay_analysis("not_a_dict")

    def test_validate_replay_analysis_raises_on_missing_analysis_id(self):
        analysis = _make_replay_analysis()
        del analysis["analysis_id"]
        with pytest.raises(InvalidReplayGovernanceInputError):
            _validate_replay_analysis(analysis)

    def test_validate_replay_analysis_raises_on_bad_status(self):
        analysis = _make_replay_analysis()
        analysis["decision_consistency"]["status"] = "bogus"
        with pytest.raises(InvalidReplayGovernanceInputError):
            _validate_replay_analysis(analysis)

    def test_validate_replay_analysis_raises_on_score_gt_1(self):
        analysis = _make_replay_analysis(score=2.0)
        with pytest.raises(InvalidReplayGovernanceInputError):
            _validate_replay_analysis(analysis)


# ===========================================================================
# 7. Control chain integration tests
# ===========================================================================


class TestControlChainIntegration:
    """Integration tests that exercise the replay governance wiring in
    run_control_chain().  These tests mock the lower-level enforcement and
    gating steps so we can control their outputs precisely."""

    def _make_slo_evaluation(self) -> Dict[str, Any]:
        """Build a minimal slo_evaluation artifact accepted by control_chain."""
        return {
            "artifact_type": "slo_evaluation",
            "artifact_id": "art-001",
            "stage": "recommend",
            "schema_version": "1.0.0",
            "run_id": "run-001",
            "policy": "default",
            "slos": [],
            "overall_status": "pass",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "evaluated_at": "2026-01-01T00:00:00+00:00",
        }

    def test_allow_governance_does_not_escalate(self):
        from unittest.mock import patch, MagicMock
        from spectrum_systems.modules.runtime.control_chain import run_control_chain

        consistent_analysis = _make_replay_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        gov_artifact = build_replay_governance_decision(
            consistent_analysis, run_id="run-1"
        )
        assert gov_artifact["decision"]["system_response"] == SYSTEM_RESPONSE_ALLOW

        # Build an enforcement-only input that would normally continue
        enf_artifact = {
            "artifact_type": "slo_enforcement_decision",
            "artifact_id": "art-001",
            "stage": "recommend",
            "decision_id": "dec-001",
            "decision_status": "allow",
            "enforcement_policy": "default",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "recommended_action": "continue",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
            "source_decision_id": "dec-001",
            "enforcement_decision_status": "allow",
            "gating_outcome": "proceed",
            "gating_decision_id": "gate-001",
        }

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
        ) as mock_gating:
            mock_gating.return_value = {
                "gating_decision": {
                    "gating_decision_id": "gate-001",
                    "gating_outcome": "proceed",
                    "stage": "recommend",
                    "warnings": [],
                    "errors": [],
                },
                "gating_outcome": "proceed",
                "schema_errors": [],
            }
            result = run_control_chain(
                enf_artifact,
                input_kind="enforcement",
                replay_governance_decision=gov_artifact,
            )

        assert result["continuation_allowed"] is True
        assert result["replay_governance_result"] is gov_artifact

    def test_require_review_governance_prevents_continuation(self):
        from unittest.mock import patch
        from spectrum_systems.modules.runtime.control_chain import run_control_chain

        indeterminate_analysis = _make_replay_analysis(
            status=REPLAY_STATUS_INDETERMINATE, score=0.5
        )
        gov_artifact = build_replay_governance_decision(
            indeterminate_analysis, run_id="run-1"
        )
        assert gov_artifact["decision"]["system_response"] == SYSTEM_RESPONSE_REQUIRE_REVIEW

        enf_artifact = {
            "artifact_type": "slo_enforcement_decision",
            "artifact_id": "art-001",
            "stage": "recommend",
            "decision_id": "dec-001",
            "decision_status": "allow",
            "enforcement_policy": "default",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "recommended_action": "continue",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
            "source_decision_id": "dec-001",
            "enforcement_decision_status": "allow",
            "gating_outcome": "proceed",
            "gating_decision_id": "gate-001",
        }

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
        ) as mock_gating:
            mock_gating.return_value = {
                "gating_decision": {
                    "gating_decision_id": "gate-001",
                    "gating_outcome": "proceed",
                    "stage": "recommend",
                    "warnings": [],
                    "errors": [],
                },
                "gating_outcome": "proceed",
                "schema_errors": [],
            }
            result = run_control_chain(
                enf_artifact,
                input_kind="enforcement",
                replay_governance_decision=gov_artifact,
            )

        # require_review must prevent automatic continuation
        assert result["continuation_allowed"] is False

    def test_quarantine_governance_prevents_continuation(self):
        from unittest.mock import patch
        from spectrum_systems.modules.runtime.control_chain import run_control_chain

        drifted_analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        gov_artifact = build_replay_governance_decision(drifted_analysis, run_id="run-1")
        assert gov_artifact["decision"]["system_response"] == SYSTEM_RESPONSE_QUARANTINE

        enf_artifact = {
            "artifact_type": "slo_enforcement_decision",
            "artifact_id": "art-001",
            "stage": "recommend",
            "decision_id": "dec-001",
            "decision_status": "allow",
            "enforcement_policy": "default",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "recommended_action": "continue",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
            "source_decision_id": "dec-001",
            "enforcement_decision_status": "allow",
            "gating_outcome": "proceed",
            "gating_decision_id": "gate-001",
        }

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
        ) as mock_gating:
            mock_gating.return_value = {
                "gating_decision": {
                    "gating_decision_id": "gate-001",
                    "gating_outcome": "proceed",
                    "stage": "recommend",
                    "warnings": [],
                    "errors": [],
                },
                "gating_outcome": "proceed",
                "schema_errors": [],
            }
            result = run_control_chain(
                enf_artifact,
                input_kind="enforcement",
                replay_governance_decision=gov_artifact,
            )

        assert result["continuation_allowed"] is False

    def test_block_governance_halts_execution(self):
        from unittest.mock import patch
        from spectrum_systems.modules.runtime.control_chain import run_control_chain

        drifted_analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        block_policy = {
            "policy_name": "strict",
            "policy_version": "1.0.0",
            "drift_action": SYSTEM_RESPONSE_BLOCK,
            "indeterminate_action": SYSTEM_RESPONSE_BLOCK,
            "missing_replay_action": SYSTEM_RESPONSE_BLOCK,
            "require_replay": False,
        }
        gov_artifact = build_replay_governance_decision(
            drifted_analysis, run_id="run-1", governance_policy=block_policy
        )
        assert gov_artifact["decision"]["system_response"] == SYSTEM_RESPONSE_BLOCK

        enf_artifact = {
            "artifact_type": "slo_enforcement_decision",
            "artifact_id": "art-001",
            "stage": "recommend",
            "decision_id": "dec-001",
            "decision_status": "allow",
            "enforcement_policy": "default",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "recommended_action": "continue",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
            "source_decision_id": "dec-001",
            "enforcement_decision_status": "allow",
            "gating_outcome": "proceed",
            "gating_decision_id": "gate-001",
        }

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
        ) as mock_gating:
            mock_gating.return_value = {
                "gating_decision": {
                    "gating_decision_id": "gate-001",
                    "gating_outcome": "proceed",
                    "stage": "recommend",
                    "warnings": [],
                    "errors": [],
                },
                "gating_outcome": "proceed",
                "schema_errors": [],
            }
            result = run_control_chain(
                enf_artifact,
                input_kind="enforcement",
                replay_governance_decision=gov_artifact,
            )

        assert result["continuation_allowed"] is False

    def test_governance_fields_visible_in_result(self):
        from unittest.mock import patch
        from spectrum_systems.modules.runtime.control_chain import run_control_chain

        drifted_analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        gov_artifact = build_replay_governance_decision(drifted_analysis, run_id="run-1")

        enf_artifact = {
            "artifact_type": "slo_enforcement_decision",
            "artifact_id": "art-001",
            "stage": "recommend",
            "decision_id": "dec-001",
            "decision_status": "allow",
            "enforcement_policy": "default",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "recommended_action": "continue",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
            "source_decision_id": "dec-001",
            "enforcement_decision_status": "allow",
            "gating_outcome": "proceed",
            "gating_decision_id": "gate-001",
        }

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
        ) as mock_gating:
            mock_gating.return_value = {
                "gating_decision": {
                    "gating_decision_id": "gate-001",
                    "gating_outcome": "proceed",
                    "stage": "recommend",
                    "warnings": [],
                    "errors": [],
                },
                "gating_outcome": "proceed",
                "schema_errors": [],
            }
            result = run_control_chain(
                enf_artifact,
                input_kind="enforcement",
                replay_governance_decision=gov_artifact,
            )

        cc = result["control_chain_decision"]
        assert "replay_governance" in cc
        rg = cc["replay_governance"]
        assert rg["present"] is True
        assert rg["replay_governed"] is True
        assert rg["system_response"] == SYSTEM_RESPONSE_QUARANTINE
        assert "rationale_code" in rg
        assert "escalated_final_decision" in rg
        assert result["replay_governance_summary"] is not None

    def test_no_governance_when_no_replay(self):
        """Systems without replay governance continue to work normally."""
        from unittest.mock import patch
        from spectrum_systems.modules.runtime.control_chain import run_control_chain

        enf_artifact = {
            "artifact_type": "slo_enforcement_decision",
            "artifact_id": "art-001",
            "stage": "recommend",
            "decision_id": "dec-001",
            "decision_status": "allow",
            "enforcement_policy": "default",
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
            "warnings": [],
            "errors": [],
            "recommended_action": "continue",
            "evaluated_at": "2026-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
            "source_decision_id": "dec-001",
            "enforcement_decision_status": "allow",
            "gating_outcome": "proceed",
            "gating_decision_id": "gate-001",
        }

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
        ) as mock_gating:
            mock_gating.return_value = {
                "gating_decision": {
                    "gating_decision_id": "gate-001",
                    "gating_outcome": "proceed",
                    "stage": "recommend",
                    "warnings": [],
                    "errors": [],
                },
                "gating_outcome": "proceed",
                "schema_errors": [],
            }
            # No replay_governance_decision provided
            result = run_control_chain(enf_artifact, input_kind="enforcement")

        assert result["continuation_allowed"] is True
        assert result["replay_governance_result"] is None
