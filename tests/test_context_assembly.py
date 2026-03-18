"""
Tests for spectrum_systems/modules/ai_workflow/context_assembly.py

Covers:
  - build_context_bundle: minimal valid bundle creation
  - build_context_bundle: deterministic context_id
  - build_context_bundle: source_artifacts are reflected in prior_artifacts
  - apply_context_budget: valid policy passes through without truncation
  - apply_context_budget: oversized policy_constraints are truncated and logged
  - apply_context_budget: oversized retrieved_context is truncated and logged
  - apply_context_budget: invalid policy raises ValueError
  - apply_context_budget: conflicting reservations raise ValueError
  - apply_context_budget: zero retrieval results pass through cleanly
  - enforce_overflow_policy: budget satisfied → no-op
  - enforce_overflow_policy: truncate_retrieval removes retrieved_context
  - enforce_overflow_policy: reject_call raises ContextBudgetExceededError
  - enforce_overflow_policy: escalate raises with escalation_required=True
  - prioritize_context_elements: canonical section order is respected
  - retrieve_context stub: always returns []
  - build_context_bundle with budget_policy: full assembly with enforcement
  - estimate_tokens / estimate_bundle_tokens: consistent and non-negative
  - build_assembly_record: fields align with the bundle
  - Schema validation: context bundle and assembly record match JSON schemas
  - Edge cases: oversized policy constraints, zero retrieval, conflicting budgets
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.ai_workflow.context_assembly import (
    PRIORITY_ORDER,
    ContextBudgetExceededError,
    apply_context_budget,
    build_assembly_record,
    build_context_bundle,
    enforce_overflow_policy,
    estimate_bundle_tokens,
    estimate_tokens,
    prioritize_context_elements,
    retrieve_context,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    with path.open() as fh:
        return json.load(fh)


def _validate(instance: dict, schema: dict) -> None:
    """Validate *instance* against *schema* using jsonschema."""
    from jsonschema import validate as js_validate
    js_validate(instance=instance, schema=schema)


MINIMAL_INPUT: dict = {
    "transcript": "We discussed 3.5 GHz interference modelling.",
    "meeting_id": "MTG-001",
}


def _make_policy(
    total: int = 4000,
    input_res: int = 1000,
    policy_res: int = 500,
    retrieval_res: int = 1000,
    output_res: int = 500,
    overflow: str = "truncate_retrieval",
) -> dict:
    return {
        "total_budget_tokens": total,
        "input_reservation": input_res,
        "policy_constraint_reservation": policy_res,
        "retrieval_reservation": retrieval_res,
        "output_reservation": output_res,
        "overflow_action": overflow,
    }


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_non_empty_string_returns_positive(self):
        assert estimate_tokens("hello world") > 0

    def test_consistent_for_same_input(self):
        text = "Spectrum coordination meeting agenda."
        assert estimate_tokens(text) == estimate_tokens(text)

    def test_longer_text_has_more_tokens(self):
        short = "hello"
        long = "hello " * 100
        assert estimate_tokens(long) > estimate_tokens(short)


# ---------------------------------------------------------------------------
# estimate_bundle_tokens
# ---------------------------------------------------------------------------

class TestEstimateBundleTokens:
    def test_total_is_sum_of_sections(self):
        bundle = {
            "primary_input": {"text": "some input text"},
            "policy_constraints": "use deterministic outputs",
            "retrieved_context": [],
            "prior_artifacts": [],
            "glossary_terms": [],
            "unresolved_questions": [],
        }
        estimates = estimate_bundle_tokens(bundle)
        section_sum = sum(
            estimates[s] for s in PRIORITY_ORDER
        )
        assert estimates["total"] == section_sum

    def test_returns_non_negative_for_empty_bundle(self):
        estimates = estimate_bundle_tokens({})
        assert all(v >= 0 for v in estimates.values())

    def test_total_key_present(self):
        estimates = estimate_bundle_tokens({"primary_input": {"a": 1}})
        assert "total" in estimates


# ---------------------------------------------------------------------------
# retrieve_context (stub)
# ---------------------------------------------------------------------------

class TestRetrieveContext:
    def test_always_returns_empty_list(self):
        result = retrieve_context("any query", "meeting_minutes")
        assert result == []

    def test_returns_list_with_filters(self):
        result = retrieve_context("query", "gap_analysis", filters={"band": "3.5GHz"})
        assert isinstance(result, list)
        assert result == []


# ---------------------------------------------------------------------------
# build_context_bundle
# ---------------------------------------------------------------------------

class TestBuildContextBundle:
    def test_returns_dict_with_required_keys(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        for key in (
            "context_id", "task_type", "primary_input", "policy_constraints",
            "retrieved_context", "prior_artifacts", "glossary_terms",
            "unresolved_questions", "metadata", "token_estimates", "truncation_log",
        ):
            assert key in bundle, f"Missing key: {key}"

    def test_task_type_preserved(self):
        bundle = build_context_bundle("gap_analysis", MINIMAL_INPUT)
        assert bundle["task_type"] == "gap_analysis"

    def test_primary_input_preserved(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        assert bundle["primary_input"] == MINIMAL_INPUT

    def test_deterministic_context_id(self):
        b1 = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        b2 = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        assert b1["context_id"] == b2["context_id"]

    def test_context_id_changes_with_different_inputs(self):
        b1 = build_context_bundle("meeting_minutes", {"x": 1})
        b2 = build_context_bundle("meeting_minutes", {"x": 2})
        assert b1["context_id"] != b2["context_id"]

    def test_source_artifacts_in_prior_artifacts(self):
        artifacts = [{"artifact_id": "ART-001", "type": "decision"}]
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT,
                                      source_artifacts=artifacts)
        assert len(bundle["prior_artifacts"]) == 1
        assert bundle["prior_artifacts"][0]["artifact_id"] == "ART-001"

    def test_source_artifact_ids_in_metadata(self):
        artifacts = [{"artifact_id": "ART-001"}, {"artifact_id": "ART-002"}]
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT,
                                      source_artifacts=artifacts)
        assert set(bundle["metadata"]["source_artifact_ids"]) == {"ART-001", "ART-002"}

    def test_retrieval_status_unavailable_when_stub(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        assert bundle["metadata"]["retrieval_status"] == "unavailable"

    def test_empty_task_type_raises(self):
        with pytest.raises(ValueError, match="task_type"):
            build_context_bundle("", MINIMAL_INPUT)

    def test_empty_input_payload_raises(self):
        with pytest.raises(ValueError, match="input_payload"):
            build_context_bundle("meeting_minutes", {})

    def test_token_estimates_total_non_negative(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        assert bundle["token_estimates"]["total"] >= 0

    def test_priority_order_key_present(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        assert "priority_order" in bundle

    def test_glossary_and_questions_from_config(self):
        cfg = {
            "glossary_terms": ["EIRP", "path loss"],
            "unresolved_questions": ["What are the antenna heights?"],
        }
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config=cfg)
        assert "EIRP" in bundle["glossary_terms"]
        assert len(bundle["unresolved_questions"]) == 1

    def test_schema_validation(self):
        schema = _load_schema("context_bundle.schema.json")
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        _validate(bundle, schema)


# ---------------------------------------------------------------------------
# apply_context_budget
# ---------------------------------------------------------------------------

class TestApplyContextBudget:
    def _make_bundle(self, policy_text: str = "", retrieval_text: str = "") -> dict:
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config={
            "policy_constraints": policy_text or "follow standard rules",
        })
        if retrieval_text:
            bundle["retrieved_context"] = [
                {"artifact_id": "ART-X", "content": retrieval_text,
                 "relevance_score": 0.9, "provenance": {}}
            ]
        return bundle

    def test_no_truncation_when_within_budget(self):
        bundle = self._make_bundle()
        policy = _make_policy(total=50000, policy_res=10000, retrieval_res=10000)
        result = apply_context_budget(bundle, policy)
        assert result["truncation_log"] == []

    def test_truncates_policy_constraints_when_oversized(self):
        large_policy_text = "A" * 10000
        bundle = self._make_bundle(policy_text=large_policy_text)
        policy = _make_policy(policy_res=10)
        result = apply_context_budget(bundle, policy)
        assert any(e["section"] == "policy_constraints" for e in result["truncation_log"])

    def test_truncates_retrieved_context_when_oversized(self):
        large_retrieval = "B" * 10000
        bundle = self._make_bundle(retrieval_text=large_retrieval)
        policy = _make_policy(retrieval_res=5)
        result = apply_context_budget(bundle, policy)
        assert any(e["section"] == "retrieved_context" for e in result["truncation_log"])

    def test_truncation_logged_with_required_fields(self):
        large_policy = "X" * 5000
        bundle = self._make_bundle(policy_text=large_policy)
        policy = _make_policy(policy_res=10)
        result = apply_context_budget(bundle, policy)
        entry = next(e for e in result["truncation_log"] if e["section"] == "policy_constraints")
        assert "original_tokens" in entry
        assert "allowed_tokens" in entry
        assert "action" in entry

    def test_token_estimates_recalculated_after_truncation(self):
        large_policy = "Y" * 8000
        bundle = self._make_bundle(policy_text=large_policy)
        policy = _make_policy(policy_res=50)
        result = apply_context_budget(bundle, policy)
        assert result["token_estimates"]["policy_constraints"] <= 60  # approx

    def test_missing_policy_key_raises_value_error(self):
        bundle = self._make_bundle()
        bad_policy = {"total_budget_tokens": 4000}
        with pytest.raises(ValueError, match="missing required keys"):
            apply_context_budget(bundle, bad_policy)

    def test_invalid_overflow_action_raises_value_error(self):
        bundle = self._make_bundle()
        policy = _make_policy(overflow="do_nothing_silently")
        with pytest.raises(ValueError, match="Invalid overflow_action"):
            apply_context_budget(bundle, policy)

    def test_conflicting_reservations_raise_value_error(self):
        bundle = self._make_bundle()
        # Sum of reservations exceeds total
        policy = _make_policy(total=100, input_res=50, policy_res=50,
                              retrieval_res=50, output_res=50)
        with pytest.raises(ValueError, match="Sum of reservations"):
            apply_context_budget(bundle, policy)

    def test_zero_retrieval_results_pass_through(self):
        bundle = self._make_bundle()
        assert bundle["retrieved_context"] == []
        policy = _make_policy()
        result = apply_context_budget(bundle, policy)
        assert result["retrieved_context"] == []
        assert result["truncation_log"] == []


# ---------------------------------------------------------------------------
# enforce_overflow_policy
# ---------------------------------------------------------------------------

class TestEnforceOverflowPolicy:
    def _oversized_bundle(self) -> dict:
        """Return a bundle that is guaranteed to exceed a tiny budget."""
        large_text = "Z" * 50000
        bundle = build_context_bundle("meeting_minutes", {
            "content": large_text, "meeting_id": "MTG-999"
        })
        return bundle

    def _make_overflow_policy(self, overflow: str) -> dict:
        """Policy with total=1 and all reservations=0 to force overflow."""
        return _make_policy(total=1, overflow=overflow,
                            input_res=0, policy_res=0,
                            retrieval_res=0, output_res=0)

    def test_no_action_when_within_budget(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        policy = _make_policy(total=9999999)
        result = enforce_overflow_policy(bundle, policy)
        assert result is bundle or result["context_id"] == bundle["context_id"]

    def test_truncate_retrieval_removes_retrieved_context(self):
        bundle = self._oversized_bundle()
        # Inject some retrieved context so we can verify it gets cleared.
        bundle["retrieved_context"] = [
            {"artifact_id": "ART-Y", "content": "some retrieved text",
             "relevance_score": 0.7, "provenance": {}}
        ]
        bundle["token_estimates"] = estimate_bundle_tokens(bundle)
        policy = self._make_overflow_policy("truncate_retrieval")
        result = enforce_overflow_policy(bundle, policy)
        assert result["retrieved_context"] == []
        assert any(
            "overflow_truncate_retrieval" in e["action"]
            for e in result["truncation_log"]
        )

    def test_reject_call_raises_context_budget_exceeded_error(self):
        bundle = self._oversized_bundle()
        bundle["token_estimates"] = estimate_bundle_tokens(bundle)
        policy = self._make_overflow_policy("reject_call")
        with pytest.raises(ContextBudgetExceededError) as exc_info:
            enforce_overflow_policy(bundle, policy)
        assert not exc_info.value.escalation_required

    def test_escalate_raises_with_escalation_required(self):
        bundle = self._oversized_bundle()
        bundle["token_estimates"] = estimate_bundle_tokens(bundle)
        policy = self._make_overflow_policy("escalate")
        with pytest.raises(ContextBudgetExceededError) as exc_info:
            enforce_overflow_policy(bundle, policy)
        assert exc_info.value.escalation_required is True

    def test_context_budget_exceeded_error_has_token_info(self):
        bundle = self._oversized_bundle()
        bundle["token_estimates"] = estimate_bundle_tokens(bundle)
        policy = self._make_overflow_policy("reject_call")
        with pytest.raises(ContextBudgetExceededError) as exc_info:
            enforce_overflow_policy(bundle, policy)
        assert exc_info.value.token_usage > 0
        assert exc_info.value.token_budget == 1


# ---------------------------------------------------------------------------
# prioritize_context_elements
# ---------------------------------------------------------------------------

class TestPrioritizeContextElements:
    def test_priority_order_matches_canonical(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config={
            "policy_constraints": "rule A",
            "glossary_terms": ["EIRP"],
            "unresolved_questions": ["Q1"],
        })
        prioritized = prioritize_context_elements(bundle)
        order = prioritized.get("priority_order", [])
        # primary_input should always come before policy_constraints
        if "primary_input" in order and "policy_constraints" in order:
            assert order.index("primary_input") < order.index("policy_constraints")

    def test_all_priority_sections_present_in_output(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        prioritized = prioritize_context_elements(bundle)
        assert "priority_order" in prioritized

    def test_idempotent(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        once = prioritize_context_elements(bundle)
        twice = prioritize_context_elements(once)
        assert once.get("priority_order") == twice.get("priority_order")

    def test_no_key_loss(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config={
            "glossary_terms": ["term1"],
        })
        prioritized = prioritize_context_elements(bundle)
        assert "context_id" in prioritized
        assert "metadata" in prioritized
        assert "truncation_log" in prioritized


# ---------------------------------------------------------------------------
# build_assembly_record
# ---------------------------------------------------------------------------

class TestBuildAssemblyRecord:
    def test_required_fields_present(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        record = build_assembly_record(bundle)
        for key in (
            "context_id", "task_type", "source_artifact_ids",
            "included_sections", "excluded_sections", "token_budget",
            "token_usage", "overflow_actions_taken", "retrieval_status",
            "warnings", "timestamp",
        ):
            assert key in record, f"Missing key: {key}"

    def test_context_id_matches_bundle(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        record = build_assembly_record(bundle)
        assert record["context_id"] == bundle["context_id"]

    def test_retrieval_warning_present_when_unavailable(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        record = build_assembly_record(bundle)
        assert any("retrieval_unavailable" in w for w in record["warnings"])

    def test_truncation_warning_present_when_truncated(self):
        large_policy = "P" * 8000
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config={
            "policy_constraints": large_policy,
            "budget_policy": _make_policy(policy_res=20),
        })
        record = build_assembly_record(bundle)
        assert any("truncation_occurred" in w for w in record["warnings"])

    def test_token_budget_null_without_policy(self):
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        record = build_assembly_record(bundle, policy=None)
        assert record["token_budget"] is None

    def test_token_budget_matches_policy_total(self):
        policy = _make_policy(total=8000)
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT,
                                      config={"budget_policy": policy})
        record = build_assembly_record(bundle, policy=policy)
        assert record["token_budget"] == 8000

    def test_schema_validation(self):
        schema = _load_schema("context_assembly_record.schema.json")
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT)
        record = build_assembly_record(bundle)
        _validate(record, schema)


# ---------------------------------------------------------------------------
# Full assembly with budget_policy in config
# ---------------------------------------------------------------------------

class TestFullAssemblyWithBudgetPolicy:
    def test_bundle_with_policy_passes_schema_validation(self):
        schema = _load_schema("context_bundle.schema.json")
        policy = _make_policy()
        bundle = build_context_bundle(
            "meeting_minutes",
            MINIMAL_INPUT,
            config={"budget_policy": policy, "policy_constraints": "standard rules"},
        )
        _validate(bundle, schema)

    def test_reject_call_policy_raises_when_budget_exceeded(self):
        large_input = {"content": "X" * 50000, "meeting_id": "MTG-999"}
        policy = _make_policy(total=1, overflow="reject_call",
                              input_res=0, policy_res=0,
                              retrieval_res=0, output_res=0)
        with pytest.raises(ContextBudgetExceededError):
            build_context_bundle("meeting_minutes", large_input,
                                 config={"budget_policy": policy})

    def test_truncate_retrieval_policy_does_not_raise(self):
        large_input = {"content": "X" * 50000, "meeting_id": "MTG-999"}
        policy = _make_policy(total=1, overflow="truncate_retrieval",
                              input_res=0, policy_res=0,
                              retrieval_res=0, output_res=0)
        # Should not raise — retrieved_context is removed instead
        bundle = build_context_bundle("meeting_minutes", large_input,
                                     config={"budget_policy": policy})
        assert bundle["retrieved_context"] == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_oversized_policy_constraints_alone(self):
        """Oversized policy constraints are truncated and logged."""
        policy = _make_policy(policy_res=5)
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config={
            "policy_constraints": "R" * 5000,
            "budget_policy": policy,
        })
        assert any(e["section"] == "policy_constraints" for e in bundle["truncation_log"])

    def test_zero_retrieval_results_clean(self):
        """Zero retrieval results produce no truncation log entries."""
        bundle = build_context_bundle("meeting_minutes", MINIMAL_INPUT, config={
            "budget_policy": _make_policy(),
        })
        assert bundle["retrieved_context"] == []
        assert not any(
            e["section"] == "retrieved_context" for e in bundle["truncation_log"]
        )

    def test_conflicting_budget_allocation_raises(self):
        """Reservations summing beyond total must raise at policy validation time."""
        policy = {
            "total_budget_tokens": 100,
            "input_reservation": 50,
            "policy_constraint_reservation": 50,
            "retrieval_reservation": 50,
            "output_reservation": 50,
            "overflow_action": "truncate_retrieval",
        }
        with pytest.raises(ValueError, match="Sum of reservations"):
            build_context_bundle("meeting_minutes", MINIMAL_INPUT,
                                 config={"budget_policy": policy})
