"""Tests for HOP AI failure pattern → system improvement proposal mapper.

Covers the six required test cases from HOP-004:
1. stream_idle_timeout → execution_budget + checkpoint_requirement proposals
2. ai_over_scoped_execution → AEX admission_rule + RDX execution_budget proposals
3. missing_checkpoint → HNX checkpoint_requirement + SEL enforcement_signal
4. Proposal with direct mutation authority fails validation
5. Every proposal includes required_eval and required_tests
6. eval_indeterminate → fail-closed continuation_policy
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.ai_failure_mapper import (
    AIFailureMapperError,
    build_ai_failure_pattern,
    map_failure_to_proposals,
    validate_proposal_authority_boundary,
)
from spectrum_systems.modules.hop.schemas import HopSchemaError, validate_hop_artifact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pattern(failure_type: str, **kwargs) -> dict:
    defaults = dict(
        failure_pattern_id=f"fp_{failure_type}",
        failure_type=failure_type,
        agent_or_provider="claude-sonnet-4-6",
        prompt_pattern="broad_open_ended_task",
        affected_stage="execution",
        recurrence_count=3,
        severity="high",
        observed_symptoms=["agent stalled", "no output after 60s"],
        recommended_preventions=["set explicit budget", "require checkpoint"],
        source_refs=["docs/reviews/hop004_ai_failure_test.md"],
    )
    defaults.update(kwargs)
    return build_ai_failure_pattern(**defaults)


# ---------------------------------------------------------------------------
# Test 1: stream_idle_timeout → execution_budget + checkpoint_requirement
# ---------------------------------------------------------------------------


def test_stream_idle_timeout_maps_to_budget_and_checkpoint():
    pattern = _make_pattern("stream_idle_timeout")
    proposals = map_failure_to_proposals(pattern)

    change_types = {p["proposed_change_type"] for p in proposals}
    assert "execution_budget" in change_types, "expected execution_budget proposal"
    assert "checkpoint_requirement" in change_types, "expected checkpoint_requirement proposal"

    target_systems_all = {s for p in proposals for s in p["target_systems"]}
    assert "PQX" in target_systems_all, "execution_budget must target PQX"
    assert "HNX" in target_systems_all, "checkpoint_requirement must target HNX"


# ---------------------------------------------------------------------------
# Test 2: ai_over_scoped_execution → AEX admission_rule + RDX execution_budget
# ---------------------------------------------------------------------------


def test_ai_over_scoped_execution_maps_to_aex_rdx_split():
    pattern = _make_pattern("ai_over_scoped_execution")
    proposals = map_failure_to_proposals(pattern)

    change_types = {p["proposed_change_type"] for p in proposals}
    assert "admission_rule" in change_types, "expected admission_rule proposal"
    assert "execution_budget" in change_types, "expected execution_budget (split) proposal"

    assert any(
        "AEX" in p["target_systems"] and p["proposed_change_type"] == "admission_rule"
        for p in proposals
    )

    rdx_proposals = [p for p in proposals if "RDX" in p["target_systems"]]
    assert rdx_proposals, "at least one proposal must target RDX for split requirement"


# ---------------------------------------------------------------------------
# Test 3: missing_checkpoint → HNX checkpoint_requirement + SEL enforcement_signal
# ---------------------------------------------------------------------------


def test_missing_checkpoint_maps_to_hnx_sel():
    pattern = _make_pattern("missing_checkpoint")
    proposals = map_failure_to_proposals(pattern)

    change_types = {p["proposed_change_type"] for p in proposals}
    assert "checkpoint_requirement" in change_types
    assert "enforcement_signal" in change_types

    hnx_proposals = [p for p in proposals if "HNX" in p["target_systems"]]
    assert hnx_proposals, "checkpoint_requirement must target HNX"

    sel_proposals = [p for p in proposals if "SEL" in p["target_systems"]]
    assert sel_proposals, "enforcement_signal must target SEL"


# ---------------------------------------------------------------------------
# Test 4: proposal with direct mutation authority fails validation
# ---------------------------------------------------------------------------


def test_proposal_with_invalid_hop_role_fails_schema_validation():
    # A well-formed proposal that we then tamper with.
    pattern = _make_pattern("stream_idle_timeout")
    proposals = map_failure_to_proposals(pattern)
    assert proposals

    tampered = dict(proposals[0])
    tampered["authority_boundary"] = dict(tampered["authority_boundary"])
    tampered["authority_boundary"]["hop_role"] = "executes_directly"

    with pytest.raises(HopSchemaError):
        validate_hop_artifact(tampered, "hop_harness_system_improvement_proposal")


def test_proposal_with_forbidden_key_fails_python_validation():
    pattern = _make_pattern("missing_checkpoint")
    proposals = map_failure_to_proposals(pattern)
    tampered = dict(proposals[0])
    tampered["direct_mutation_authority"] = True

    with pytest.raises(AIFailureMapperError, match="forbidden_authority_key"):
        validate_proposal_authority_boundary(tampered)


def test_proposal_advisory_only_false_fails_python_validation():
    pattern = _make_pattern("budget_exhausted")
    proposals = map_failure_to_proposals(pattern)
    tampered = dict(proposals[0])
    tampered["advisory_only"] = False

    with pytest.raises(AIFailureMapperError, match="advisory_only_not_true"):
        validate_proposal_authority_boundary(tampered)


def test_proposal_advisory_only_false_fails_schema_validation():
    pattern = _make_pattern("scope_drift")
    proposals = map_failure_to_proposals(pattern)
    tampered = dict(proposals[0])
    tampered["advisory_only"] = False

    with pytest.raises(HopSchemaError):
        validate_hop_artifact(tampered, "hop_harness_system_improvement_proposal")


# ---------------------------------------------------------------------------
# Test 5: every proposal includes required_eval and required_tests
# ---------------------------------------------------------------------------


def test_every_proposal_includes_required_eval_and_tests():
    all_failure_types = [
        "stream_idle_timeout",
        "ai_over_scoped_execution",
        "missing_checkpoint",
        "budget_exhausted",
        "scope_drift",
        "eval_indeterminate",
        "architecture_boundary_violation",
    ]
    for ft in all_failure_types:
        pattern = _make_pattern(ft)
        proposals = map_failure_to_proposals(pattern)
        assert proposals, f"no proposals for {ft}"
        for proposal in proposals:
            required_eval = proposal.get("required_eval")
            assert isinstance(required_eval, list) and len(required_eval) >= 1, (
                f"proposal for {ft} missing required_eval"
            )
            for ec in required_eval:
                assert ec.get("eval_case_id"), f"eval_case missing eval_case_id in {ft}"
                assert ec.get("description"), f"eval_case missing description in {ft}"
                assert ec.get("expected_outcome"), f"eval_case missing expected_outcome in {ft}"

            required_tests = proposal.get("required_tests")
            assert isinstance(required_tests, list) and len(required_tests) >= 1, (
                f"proposal for {ft} missing required_tests"
            )


# ---------------------------------------------------------------------------
# Test 6: eval_indeterminate → fail-closed continuation_policy
# ---------------------------------------------------------------------------


def test_eval_indeterminate_maps_to_fail_closed_continuation_policy():
    pattern = _make_pattern("eval_indeterminate")
    proposals = map_failure_to_proposals(pattern)

    continuation_proposals = [
        p for p in proposals if p["proposed_change_type"] == "continuation_policy"
    ]
    assert continuation_proposals, "expected at least one continuation_policy proposal"

    cde_proposals = [p for p in continuation_proposals if "CDE" in p["target_systems"]]
    assert cde_proposals, "continuation_policy must target CDE for eval_indeterminate"

    for p in cde_proposals:
        guardrail = p["proposed_guardrail"].lower()
        assert "fail-closed" in guardrail or "block" in guardrail, (
            "CDE continuation_policy for eval_indeterminate must mention fail-closed or block"
        )


# ---------------------------------------------------------------------------
# Schema round-trip: built artifacts pass schema validation
# ---------------------------------------------------------------------------


def test_ai_failure_pattern_artifact_validates_against_schema():
    for ft in ["stream_idle_timeout", "eval_indeterminate", "architecture_boundary_violation"]:
        pattern = _make_pattern(ft)
        validate_hop_artifact(pattern, "hop_harness_ai_failure_pattern")


def test_system_improvement_proposal_validates_against_schema():
    for ft in ["stream_idle_timeout", "missing_checkpoint", "scope_drift"]:
        pattern = _make_pattern(ft)
        for proposal in map_failure_to_proposals(pattern):
            validate_hop_artifact(proposal, "hop_harness_system_improvement_proposal")


# ---------------------------------------------------------------------------
# Authority boundary: all canonical fields present and correct on every proposal
# ---------------------------------------------------------------------------


def test_all_proposals_carry_correct_authority_boundary():
    for ft in ["stream_idle_timeout", "ai_over_scoped_execution", "missing_checkpoint",
               "budget_exhausted", "scope_drift", "eval_indeterminate",
               "architecture_boundary_violation"]:
        pattern = _make_pattern(ft)
        for proposal in map_failure_to_proposals(pattern):
            boundary = proposal["authority_boundary"]
            assert boundary["hop_role"] == "proposes_only"
            assert set(boundary["review_owners"]) >= {"CDE", "GOV"}
            assert boundary["execution_owner"] == "PQX"
            assert boundary["validation_owner"] == "EVL"
            assert boundary["enforcement_signal_owner"] == "SEL"
            validate_proposal_authority_boundary(proposal)


# ---------------------------------------------------------------------------
# Fail-closed: unknown failure_type raises
# ---------------------------------------------------------------------------


def test_map_unknown_failure_type_raises():
    pattern = _make_pattern("stream_idle_timeout")
    tampered = dict(pattern)
    tampered["failure_type"] = "nonexistent_failure_type"

    with pytest.raises(AIFailureMapperError, match="no_mapping_for_failure_type"):
        map_failure_to_proposals(tampered)


def test_build_pattern_with_unknown_failure_type_raises():
    with pytest.raises(AIFailureMapperError, match="unknown_failure_type"):
        build_ai_failure_pattern(
            failure_pattern_id="fp_bad",
            failure_type="not_a_real_type",
            agent_or_provider="test",
            prompt_pattern="x",
            affected_stage="execution",
            recurrence_count=1,
            severity="low",
            observed_symptoms=["x"],
            recommended_preventions=["x"],
            source_refs=["x"],
        )
