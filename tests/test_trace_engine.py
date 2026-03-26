"""Tests for BK–BM Trace + Correlation Layer (trace_engine.py).

Covers all 15 required behaviors from the problem statement:
 1.  trace created on every run
 2.  spans created in correct hierarchy
 3.  events recorded correctly
 4.  artifacts linked to trace
 5.  missing trace_id blocks execution
 6.  malformed span blocks execution
 7.  deterministic trace output (same structure)
 8.  integration with control_chain
 9.  integration with validator_engine
10.  integration with SLO pipeline
11.  multiple spans per run
12.  nested span correctness
13.  failure propagation captured in trace
14.  trace retrieval works
15.  no orphan spans (every span has a valid parent or is root)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.trace_engine import (  # noqa: E402
    SPAN_STATUS_BLOCKED,
    SPAN_STATUS_ERROR,
    SPAN_STATUS_OK,
    TraceConflictError,
    SpanNotFoundError,
    TraceNotFoundError,
    attach_artifact,
    clear_trace_store,
    end_span,
    get_all_trace_ids,
    get_trace,
    record_event,
    start_span,
    start_trace,
    summarize_trace,
    validate_trace_context,
)
from spectrum_systems.modules.runtime.validator_engine import (  # noqa: E402
    run_validators,
)
from spectrum_systems.modules.runtime.slo_evaluator import (  # noqa: E402
    compute_slo_status,
    map_validator_results_to_slis,
)
from spectrum_systems.modules.runtime.slo_enforcer import (  # noqa: E402
    enforce_slo_policy,
)
from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    run_control_chain,
)


@pytest.fixture(autouse=True)
def _clear_store():
    """Clear the in-process trace store before/after each test."""
    clear_trace_store()
    yield
    clear_trace_store()


# ---------------------------------------------------------------------------
# Test 1: trace created on every run
# ---------------------------------------------------------------------------

class TestTraceCreatedOnEveryRun:
    def test_start_trace_returns_string_id(self):
        trace_id = start_trace()
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0

    def test_start_trace_id_is_unique(self):
        ids = [start_trace() for _ in range(10)]
        assert len(set(ids)) == 10

    def test_start_trace_creates_retrievable_trace(self):
        trace_id = start_trace({"run_id": "test-run"})
        trace = get_trace(trace_id)
        assert trace["trace_id"] == trace_id
        assert trace["spans"] == []
        assert trace["artifacts"] == []
        assert trace["start_time"] is not None
        assert trace["end_time"] is None

    def test_trace_includes_context(self):
        trace_id = start_trace({"stage": "synthesis", "run_id": "R-001"})
        trace = get_trace(trace_id)
        assert trace["context"]["stage"] == "synthesis"
        assert trace["context"]["run_id"] == "R-001"

    def test_get_all_trace_ids_includes_new_trace(self):
        trace_id = start_trace()
        assert trace_id in get_all_trace_ids()

    def test_start_trace_deterministic_seed_reuses_same_id(self):
        trace_a = start_trace({"deterministic_seed": "seed-001", "run_id": "run-001"})
        with pytest.raises(TraceConflictError):
            start_trace({"deterministic_seed": "seed-001", "run_id": "run-001"})
        assert isinstance(trace_a, str)
        assert len(trace_a) == 36

    def test_start_trace_explicit_trace_id_conflict_is_blocked(self):
        start_trace({"trace_id": "trace-001", "run_id": "run-001"})
        with pytest.raises(TraceConflictError):
            start_trace({"trace_id": "trace-001", "run_id": "run-002"})


# ---------------------------------------------------------------------------
# Test 2: spans created in correct hierarchy
# ---------------------------------------------------------------------------

class TestSpanHierarchy:
    def test_root_span_has_no_parent(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "root_op")
        trace = get_trace(trace_id)
        span = trace["spans"][0]
        assert span["parent_span_id"] is None
        assert span["name"] == "root_op"
        assert trace["root_span_id"] == span_id

    def test_child_span_has_parent(self):
        trace_id = start_trace()
        root_id = start_span(trace_id, "root")
        child_id = start_span(trace_id, "child", root_id)
        trace = get_trace(trace_id)
        child = next(s for s in trace["spans"] if s["span_id"] == child_id)
        assert child["parent_span_id"] == root_id

    def test_first_span_becomes_root(self):
        trace_id = start_trace()
        s1 = start_span(trace_id, "first")
        s2 = start_span(trace_id, "second", s1)
        trace = get_trace(trace_id)
        assert trace["root_span_id"] == s1

    def test_start_span_unknown_trace_raises(self):
        with pytest.raises(TraceNotFoundError):
            start_span("nonexistent-trace-id", "op")

    def test_start_span_unknown_parent_raises(self):
        trace_id = start_trace()
        with pytest.raises(SpanNotFoundError):
            start_span(trace_id, "op", "nonexistent-span-id")

    def test_start_span_parent_from_different_trace_raises(self):
        t1 = start_trace()
        t2 = start_trace()
        s1 = start_span(t1, "span-in-t1")
        with pytest.raises(SpanNotFoundError):
            start_span(t2, "cross-trace-child", s1)


# ---------------------------------------------------------------------------
# Test 3: events recorded correctly
# ---------------------------------------------------------------------------

class TestEventRecording:
    def test_record_event_appends_to_span(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "op")
        record_event(span_id, "validator_result", {"status": "pass", "name": "v1"})
        trace = get_trace(trace_id)
        span = trace["spans"][0]
        assert len(span["events"]) == 1
        ev = span["events"][0]
        assert ev["event_type"] == "validator_result"
        assert ev["payload"]["status"] == "pass"
        assert ev["timestamp"] is not None

    def test_multiple_events_on_same_span(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "op")
        record_event(span_id, "start", {})
        record_event(span_id, "progress", {"pct": 50})
        record_event(span_id, "complete", {"result": "ok"})
        trace = get_trace(trace_id)
        assert len(trace["spans"][0]["events"]) == 3

    def test_record_event_unknown_span_raises(self):
        with pytest.raises(SpanNotFoundError):
            record_event("bad-span-id", "something", {})

    def test_record_event_empty_event_type_raises(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "op")
        with pytest.raises(ValueError):
            record_event(span_id, "", {})


# ---------------------------------------------------------------------------
# Test 4: artifacts linked to trace
# ---------------------------------------------------------------------------

class TestArtifactAttachment:
    def test_attach_artifact_appears_in_trace(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "op")
        attach_artifact(trace_id, "ART-001", "control_chain_decision", span_id)
        trace = get_trace(trace_id)
        assert len(trace["artifacts"]) == 1
        art = trace["artifacts"][0]
        assert art["artifact_id"] == "ART-001"
        assert art["artifact_type"] == "control_chain_decision"
        assert art["parent_span_id"] == span_id
        assert art["attached_at"] is not None

    def test_attach_artifact_unknown_trace_raises(self):
        with pytest.raises(TraceNotFoundError):
            attach_artifact("bad-trace-id", "X", "type")

    def test_multiple_artifacts_attached(self):
        trace_id = start_trace()
        attach_artifact(trace_id, "A1", "validator_execution_result")
        attach_artifact(trace_id, "A2", "slo_evaluation_result")
        attach_artifact(trace_id, "A3", "control_chain_decision")
        trace = get_trace(trace_id)
        assert len(trace["artifacts"]) == 3


# ---------------------------------------------------------------------------
# Test 5: missing trace_id blocks execution
# ---------------------------------------------------------------------------

class TestMissingTraceIdBlocksExecution:
    def test_validate_trace_context_empty_string(self):
        errors = validate_trace_context("")
        assert len(errors) > 0
        assert any("missing" in e.lower() for e in errors)

    def test_validate_trace_context_none(self):
        errors = validate_trace_context(None)
        assert len(errors) > 0

    def test_validate_trace_context_unknown_id(self):
        errors = validate_trace_context("completely-unknown-id")
        assert len(errors) > 0

    def test_run_validators_with_malformed_trace_blocks(self):
        # Manually corrupt the store to trigger malformed-trace detection
        # We test this by patching validate_trace_context to return errors
        with patch(
            "spectrum_systems.modules.runtime.validator_engine.validate_trace_context",
            return_value=["malformed_trace: test error"],
        ):
            # Force a non-empty trace_id so it doesn't auto-start a new trace
            result = run_validators(
                ["validate_runtime_compatibility"],
                context={"trace_id": "fake-id"},
            )
        assert result["overall_status"] == "blocked"
        assert "malformed_trace_context" in result["failure_reason_codes"]


# ---------------------------------------------------------------------------
# Test 6: malformed span blocks execution
# ---------------------------------------------------------------------------

class TestMalformedSpanBlocksExecution:
    def test_end_span_invalid_status_raises(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "op")
        with pytest.raises(ValueError, match="status"):
            end_span(span_id, "invalid_status")

    def test_end_span_unknown_id_raises(self):
        with pytest.raises(SpanNotFoundError):
            end_span("bad-span-id", SPAN_STATUS_OK)

    def test_start_span_empty_name_raises(self):
        trace_id = start_trace()
        with pytest.raises(ValueError):
            start_span(trace_id, "")


# ---------------------------------------------------------------------------
# Test 7: deterministic trace output
# ---------------------------------------------------------------------------

class TestDeterministicTraceOutput:
    def test_same_operations_produce_consistent_structure(self):
        def _make_trace() -> Dict[str, Any]:
            tid = start_trace({"run": "determinism-test"})
            s1 = start_span(tid, "control_chain")
            s2 = start_span(tid, "enforcement", s1)
            record_event(s2, "enforcement_complete", {"decision_status": "allow"})
            end_span(s2, SPAN_STATUS_OK)
            s3 = start_span(tid, "gating", s1)
            record_event(s3, "gating_complete", {"gating_outcome": "proceed"})
            end_span(s3, SPAN_STATUS_OK)
            end_span(s1, SPAN_STATUS_OK)
            attach_artifact(tid, "DEC-001", "control_chain_decision", s1)
            return get_trace(tid)

        t1 = _make_trace()
        t2 = _make_trace()

        # Structure must be consistent (same span count, event count, artifact count)
        assert len(t1["spans"]) == len(t2["spans"])
        assert len(t1["spans"][0]["events"]) == len(t2["spans"][0]["events"])
        assert len(t1["artifacts"]) == len(t2["artifacts"])

        # Span names must be identical
        names1 = [s["name"] for s in t1["spans"]]
        names2 = [s["name"] for s in t2["spans"]]
        assert names1 == names2

    def test_schema_version_is_constant(self):
        tid = start_trace()
        trace = get_trace(tid)
        assert trace["schema_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Test 8: integration with control_chain
# ---------------------------------------------------------------------------

class TestControlChainIntegration:
    def _make_slo_evaluation(self) -> Dict[str, Any]:
        return {
            "artifact_type": "slo_evaluation",
            "artifact_id": "EVAL-001",
            "stage": "observe",
            "evaluated_at": "2025-01-01T00:00:00+00:00",
            "slo_status": "healthy",
            "slis": {
                "completeness": 1.0,
                "timeliness": 1.0,
                "traceability": 1.0,
                "traceability_integrity": 1.0,
            },
            "violations": [],
            "schema_version": "1.0.0",
        }

    def test_control_chain_result_includes_trace_id(self):
        result = run_control_chain(self._make_slo_evaluation(), stage="observe")
        assert "trace_id" in result
        assert isinstance(result["trace_id"], str)
        assert len(result["trace_id"]) > 0

    def test_control_chain_decision_includes_trace_id(self):
        result = run_control_chain(self._make_slo_evaluation(), stage="observe")
        decision = result["control_chain_decision"]
        assert "trace_id" in decision
        assert decision["trace_id"] == result["trace_id"]

    def test_control_chain_trace_is_retrievable(self):
        result = run_control_chain(self._make_slo_evaluation(), stage="observe")
        trace_id = result["trace_id"]
        trace = get_trace(trace_id)
        assert trace["trace_id"] == trace_id
        assert len(trace["spans"]) >= 1

    def test_control_chain_trace_has_spans(self):
        result = run_control_chain(self._make_slo_evaluation(), stage="observe")
        trace = get_trace(result["trace_id"])
        span_names = [s["name"] for s in trace["spans"]]
        assert "control_chain" in span_names

    def test_control_chain_trace_contains_gating_span(self):
        result = run_control_chain(self._make_slo_evaluation(), stage="observe")
        trace = get_trace(result["trace_id"])
        span_names = [s["name"] for s in trace["spans"]]
        assert "gating" in span_names

    def test_control_chain_trace_contains_enforcement_span(self):
        result = run_control_chain(self._make_slo_evaluation(), stage="observe")
        trace = get_trace(result["trace_id"])
        span_names = [s["name"] for s in trace["spans"]]
        assert "enforcement" in span_names


# ---------------------------------------------------------------------------
# Test 9: integration with validator_engine
# ---------------------------------------------------------------------------

class TestValidatorEngineIntegration:
    def test_run_validators_auto_starts_trace(self):
        before = set(get_all_trace_ids())
        run_validators(["validate_runtime_compatibility"], context={"artifact": {}})
        after = set(get_all_trace_ids())
        assert len(after) > len(before)

    def test_run_validators_uses_provided_trace_id(self):
        trace_id = start_trace({"source": "test"})
        root_span = start_span(trace_id, "root")
        run_validators(
            ["validate_runtime_compatibility"],
            context={"artifact": {}, "trace_id": trace_id, "parent_span_id": root_span},
        )
        trace = get_trace(trace_id)
        span_names = [s["name"] for s in trace["spans"]]
        assert "validator_execution" in span_names

    def test_run_validators_creates_per_validator_spans(self):
        trace_id = start_trace()
        run_validators(
            ["validate_runtime_compatibility"],
            context={"artifact": {}, "trace_id": trace_id},
        )
        trace = get_trace(trace_id)
        span_names = [s["name"] for s in trace["spans"]]
        assert any("validator:validate_runtime_compatibility" in n for n in span_names)

    def test_run_validators_attaches_result_artifact(self):
        trace_id = start_trace()
        result = run_validators(
            ["validate_runtime_compatibility"],
            context={"artifact": {}, "trace_id": trace_id},
        )
        trace = get_trace(trace_id)
        artifact_ids = [a["artifact_id"] for a in trace["artifacts"]]
        assert result["execution_id"] in artifact_ids


# ---------------------------------------------------------------------------
# Test 10: integration with SLO pipeline
# ---------------------------------------------------------------------------

class TestSLOPipelineIntegration:
    def _healthy_ve_result(self) -> Dict[str, Any]:
        return {
            "execution_id": "EX-001",
            "validators_requested": ["validate_runtime_compatibility"],
            "validators_run": ["validate_runtime_compatibility"],
            "validators_passed": ["validate_runtime_compatibility"],
            "validators_failed": [],
            "validator_results": [
                {
                    "validator_name": "validate_runtime_compatibility",
                    "status": "pass",
                    "blocking": False,
                    "reason_codes": [],
                    "warnings": [],
                    "errors": [],
                    "details": {},
                }
            ],
            "overall_status": "pass",
            "failure_reason_codes": [],
            "evaluated_at": "2025-01-01T00:00:00+00:00",
            "schema_version": "1.0.0",
        }

    def test_map_validator_results_creates_span(self):
        trace_id = start_trace()
        root_span = start_span(trace_id, "root")
        map_validator_results_to_slis(
            self._healthy_ve_result(),
            trace_id=trace_id,
            parent_span_id=root_span,
        )
        trace = get_trace(trace_id)
        span_names = [s["name"] for s in trace["spans"]]
        assert "sli_mapping" in span_names

    def test_compute_slo_status_creates_span(self):
        trace_id = start_trace()
        root_span = start_span(trace_id, "root")
        slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0, "traceability_integrity": 1.0}
        compute_slo_status(slis, trace_id=trace_id, parent_span_id=root_span)
        trace = get_trace(trace_id)
        span_names = [s["name"] for s in trace["spans"]]
        assert "slo_computation" in span_names

    def test_enforce_slo_policy_creates_span(self):
        trace_id = start_trace()
        root_span = start_span(trace_id, "root")
        enforce_slo_policy(
            "healthy",
            {"overall": 0.05},
            trace_id=trace_id,
            parent_span_id=root_span,
        )
        trace = get_trace(trace_id)
        span_names = [s["name"] for s in trace["spans"]]
        assert "slo_enforcement_decision" in span_names

    def test_slo_pipeline_spans_have_correct_status_on_healthy(self):
        trace_id = start_trace()
        root_span = start_span(trace_id, "root")
        slis = {"completeness": 1.0, "timeliness": 1.0, "traceability": 1.0, "traceability_integrity": 1.0}
        compute_slo_status(slis, trace_id=trace_id, parent_span_id=root_span)
        trace = get_trace(trace_id)
        slo_span = next(s for s in trace["spans"] if s["name"] == "slo_computation")
        assert slo_span["status"] == SPAN_STATUS_OK


# ---------------------------------------------------------------------------
# Test 11: multiple spans per run
# ---------------------------------------------------------------------------

class TestMultipleSpansPerRun:
    def test_multiple_spans_in_single_trace(self):
        trace_id = start_trace()
        ids = [start_span(trace_id, f"op_{i}") for i in range(5)]
        for sid in ids:
            end_span(sid, SPAN_STATUS_OK)
        trace = get_trace(trace_id)
        assert len(trace["spans"]) == 5

    def test_spans_are_in_creation_order(self):
        trace_id = start_trace()
        names = ["alpha", "beta", "gamma", "delta"]
        for name in names:
            start_span(trace_id, name)
        trace = get_trace(trace_id)
        assert [s["name"] for s in trace["spans"]] == names


# ---------------------------------------------------------------------------
# Test 12: nested span correctness
# ---------------------------------------------------------------------------

class TestNestedSpanCorrectness:
    def test_three_level_nesting(self):
        trace_id = start_trace()
        l1 = start_span(trace_id, "l1")
        l2 = start_span(trace_id, "l2", l1)
        l3 = start_span(trace_id, "l3", l2)
        trace = get_trace(trace_id)
        span_map = {s["span_id"]: s for s in trace["spans"]}
        assert span_map[l2]["parent_span_id"] == l1
        assert span_map[l3]["parent_span_id"] == l2

    def test_summarize_trace_shows_nested_tree(self):
        trace_id = start_trace()
        l1 = start_span(trace_id, "control_chain")
        l2 = start_span(trace_id, "enforcement", l1)
        end_span(l2, SPAN_STATUS_OK)
        end_span(l1, SPAN_STATUS_OK)
        summary = summarize_trace(trace_id)
        assert "control_chain" in summary
        assert "enforcement" in summary


# ---------------------------------------------------------------------------
# Test 13: failure propagation captured in trace
# ---------------------------------------------------------------------------

class TestFailurePropagationInTrace:
    def test_blocked_span_status_recorded(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "validator:validate_bundle_contract")
        record_event(span_id, "validator_result", {"status": "blocked", "reason": "unknown_validator"})
        end_span(span_id, SPAN_STATUS_BLOCKED)
        trace = get_trace(trace_id)
        span = trace["spans"][0]
        assert span["status"] == SPAN_STATUS_BLOCKED

    def test_error_span_status_recorded(self):
        trace_id = start_trace()
        span_id = start_span(trace_id, "enforcement")
        end_span(span_id, SPAN_STATUS_ERROR)
        trace = get_trace(trace_id)
        assert trace["spans"][0]["status"] == SPAN_STATUS_ERROR

    def test_summarize_trace_shows_first_failure(self):
        trace_id = start_trace()
        s1 = start_span(trace_id, "control_chain")
        s2 = start_span(trace_id, "enforcement", s1)
        end_span(s2, SPAN_STATUS_BLOCKED)
        end_span(s1, SPAN_STATUS_BLOCKED)
        summary = summarize_trace(trace_id)
        assert "first_failure_span" in summary
        assert s2 in summary or s2[:8] in summary

    def test_run_validators_failure_captured(self):
        trace_id = start_trace()
        result = run_validators(
            ["nonexistent_validator_xyz"],
            context={"artifact": {}, "trace_id": trace_id},
        )
        assert result["overall_status"] == "blocked"
        trace = get_trace(trace_id)
        all_statuses = [s.get("status") for s in trace["spans"]]
        assert SPAN_STATUS_BLOCKED in all_statuses


# ---------------------------------------------------------------------------
# Test 14: trace retrieval works
# ---------------------------------------------------------------------------

class TestTraceRetrieval:
    def test_get_trace_returns_deep_copy(self):
        trace_id = start_trace()
        start_span(trace_id, "op")
        t1 = get_trace(trace_id)
        t1["spans"][0]["name"] = "MUTATED"
        t2 = get_trace(trace_id)
        assert t2["spans"][0]["name"] == "op"

    def test_get_trace_unknown_id_raises(self):
        with pytest.raises(TraceNotFoundError):
            get_trace("nonexistent-id")

    def test_summarize_trace_unknown_id_raises(self):
        with pytest.raises(TraceNotFoundError):
            summarize_trace("nonexistent-id")

    def test_summarize_trace_contains_required_fields(self):
        trace_id = start_trace()
        s1 = start_span(trace_id, "root_op")
        attach_artifact(trace_id, "DECID-001", "control_chain_decision", s1)
        end_span(s1, SPAN_STATUS_OK)
        summary = summarize_trace(trace_id)
        assert trace_id in summary
        assert "Span Tree" in summary
        assert "Artifacts" in summary
        assert "DECID-001" in summary
        assert "first_failure_span" in summary


# ---------------------------------------------------------------------------
# Test 15: no orphan spans
# ---------------------------------------------------------------------------

class TestNoOrphanSpans:
    def test_all_spans_have_valid_parent_or_are_root(self):
        trace_id = start_trace()
        root = start_span(trace_id, "root")
        c1 = start_span(trace_id, "child1", root)
        c2 = start_span(trace_id, "child2", root)
        gc = start_span(trace_id, "grandchild", c1)
        end_span(gc, SPAN_STATUS_OK)
        end_span(c1, SPAN_STATUS_OK)
        end_span(c2, SPAN_STATUS_OK)
        end_span(root, SPAN_STATUS_OK)

        trace = get_trace(trace_id)
        span_ids = {s["span_id"] for s in trace["spans"]}
        root_id = trace["root_span_id"]

        for span in trace["spans"]:
            pid = span["parent_span_id"]
            if span["span_id"] == root_id:
                assert pid is None, f"Root span must have no parent; got {pid}"
            else:
                assert pid in span_ids, (
                    f"Span '{span['name']}' has parent_span_id '{pid}' "
                    "which is not in the trace's span list — orphan span detected"
                )

    def test_control_chain_spans_all_have_valid_parents(self):
        slo_eval = {
            "artifact_type": "slo_evaluation",
            "artifact_id": "EVAL-002",
            "stage": "observe",
            "evaluated_at": "2025-01-01T00:00:00+00:00",
            "slo_status": "healthy",
            "slis": {
                "completeness": 1.0,
                "timeliness": 1.0,
                "traceability": 1.0,
                "traceability_integrity": 1.0,
            },
            "violations": [],
            "schema_version": "1.0.0",
        }
        result = run_control_chain(slo_eval, stage="observe")
        trace = get_trace(result["trace_id"])
        span_ids = {s["span_id"] for s in trace["spans"]}
        root_id = trace["root_span_id"]

        for span in trace["spans"]:
            pid = span["parent_span_id"]
            if span["span_id"] == root_id:
                assert pid is None
            else:
                assert pid in span_ids, (
                    f"Orphan span detected: '{span['name']}' has parent '{pid}'"
                )
