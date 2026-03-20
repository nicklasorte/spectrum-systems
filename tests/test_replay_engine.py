"""Tests for BP — Replay Engine (replay_engine.py).

Covers:
 1.  validate_replay_prerequisites fails for unknown trace
 2.  validate_replay_prerequisites fails for empty trace_id
 3.  validate_replay_prerequisites passes for persisted trace with spans
 4.  validate_replay_prerequisites fails for trace with no spans
 5.  build_replay_record raises ReplayPrerequisiteError when prerequisites fail
 6.  build_replay_record returns correct structure
 7.  execute_replay returns a blocked result when prerequisites not met
 8.  execute_replay produces a schema-valid result for a simple trace
 9.  execute_replay captures all spans as steps
10.  compare_replay_outputs detects status differences
11.  compare_replay_outputs matches when statuses are identical
12.  compare_replay_outputs handles empty inputs
13.  validate_replay_result returns empty list for valid result
14.  validate_replay_result returns errors for invalid result
15.  execute_replay records determinism notes
16.  execute_replay sets status=success when all steps pass
17.  execute_replay sets status=partial when any step has error or blocked
18.  replay result artifact_type is correct
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.replay_engine import (  # noqa: E402
    ARTIFACT_TYPE,
    SCHEMA_VERSION,
    ReplayEngineError,
    ReplayPrerequisiteError,
    build_replay_record,
    compare_replay_outputs,
    execute_replay,
    validate_replay_prerequisites,
    validate_replay_result,
)
from spectrum_systems.modules.runtime.trace_store import (  # noqa: E402
    persist_trace,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_store(tmp_path):
    return tmp_path / "traces"


def _make_trace(trace_id: str, *, n_spans: int = 0) -> Dict[str, Any]:
    """Build a minimal valid trace dict with optional spans."""
    spans = []
    for i in range(n_spans):
        span_id = f"span-{i:03d}"
        spans.append(
            {
                "span_id": span_id,
                "trace_id": trace_id,
                "parent_span_id": None if i == 0 else "span-000",
                "name": f"op_{i}",
                "status": "ok",
                "start_time": "2025-01-01T00:00:00+00:00",
                "end_time": "2025-01-01T00:00:01+00:00",
                "events": [],
            }
        )
    return {
        "trace_id": trace_id,
        "root_span_id": spans[0]["span_id"] if spans else None,
        "spans": spans,
        "artifacts": [],
        "start_time": "2025-01-01T00:00:00+00:00",
        "end_time": "2025-01-01T00:00:01+00:00",
        "context": {"run_id": "run-001"},
        "schema_version": "1.0.0",
    }


def _make_valid_replay_result(
    replay_id: str = "replay-001",
    trace_id: str = "source-trace-001",
) -> Dict[str, Any]:
    """Build a minimal valid replay_result dict."""
    return {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "replay_id": replay_id,
        "source_trace_id": trace_id,
        "replayed_at": "2025-01-01T00:00:00+00:00",
        "status": "success",
        "prerequisites_valid": True,
        "prerequisite_errors": [],
        "steps_executed": [],
        "output_comparison": {
            "compared": False,
            "matched": None,
            "differences": [],
        },
        "determinism_notes": [],
        "context": {},
    }


# ---------------------------------------------------------------------------
# Test 1: validate_replay_prerequisites fails for unknown trace
# ---------------------------------------------------------------------------

class TestPrerequisitesUnknownTrace:
    def test_unknown_trace_id_returns_error(self, tmp_store):
        errors = validate_replay_prerequisites("nonexistent-trace", base_dir=tmp_store)
        assert len(errors) > 0
        assert any("nonexistent-trace" in e for e in errors)


# ---------------------------------------------------------------------------
# Test 2: validate_replay_prerequisites fails for empty trace_id
# ---------------------------------------------------------------------------

class TestPrerequisitesEmptyTraceId:
    def test_empty_string_trace_id(self, tmp_store):
        errors = validate_replay_prerequisites("", base_dir=tmp_store)
        assert len(errors) > 0

    def test_none_trace_id(self, tmp_store):
        errors = validate_replay_prerequisites(None, base_dir=tmp_store)  # type: ignore[arg-type]
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test 3: validate_replay_prerequisites passes for persisted trace with spans
# ---------------------------------------------------------------------------

class TestPrerequisitesValid:
    def test_valid_trace_passes(self, tmp_store):
        trace = _make_trace("trace-valid-prereq", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        errors = validate_replay_prerequisites("trace-valid-prereq", base_dir=tmp_store)
        assert errors == []

    def test_trace_with_multiple_spans_passes(self, tmp_store):
        trace = _make_trace("trace-multi-span", n_spans=3)
        persist_trace(trace, base_dir=tmp_store)
        errors = validate_replay_prerequisites("trace-multi-span", base_dir=tmp_store)
        assert errors == []


# ---------------------------------------------------------------------------
# Test 4: validate_replay_prerequisites fails for trace with no spans
# ---------------------------------------------------------------------------

class TestPrerequisitesNoSpans:
    def test_trace_with_no_spans_fails(self, tmp_store):
        trace = _make_trace("trace-no-spans", n_spans=0)
        persist_trace(trace, base_dir=tmp_store)
        errors = validate_replay_prerequisites("trace-no-spans", base_dir=tmp_store)
        assert len(errors) > 0
        assert any("no spans" in e for e in errors)


# ---------------------------------------------------------------------------
# Test 5: build_replay_record raises ReplayPrerequisiteError when prereqs fail
# ---------------------------------------------------------------------------

class TestBuildReplayRecordErrors:
    def test_raises_when_trace_not_found(self, tmp_store):
        with pytest.raises(ReplayPrerequisiteError):
            build_replay_record("nonexistent", base_dir=tmp_store)

    def test_raises_when_no_spans(self, tmp_store):
        trace = _make_trace("trace-build-no-spans", n_spans=0)
        persist_trace(trace, base_dir=tmp_store)
        with pytest.raises(ReplayPrerequisiteError):
            build_replay_record("trace-build-no-spans", base_dir=tmp_store)


# ---------------------------------------------------------------------------
# Test 6: build_replay_record returns correct structure
# ---------------------------------------------------------------------------

class TestBuildReplayRecord:
    def test_returns_required_keys(self, tmp_store):
        trace = _make_trace("trace-record-keys", n_spans=2)
        persist_trace(trace, base_dir=tmp_store)
        record = build_replay_record("trace-record-keys", base_dir=tmp_store)
        assert "trace_id" in record
        assert "spans" in record
        assert "artifacts" in record
        assert "context" in record
        assert "envelope" in record

    def test_trace_id_matches(self, tmp_store):
        trace = _make_trace("trace-record-id", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        record = build_replay_record("trace-record-id", base_dir=tmp_store)
        assert record["trace_id"] == "trace-record-id"

    def test_spans_are_preserved(self, tmp_store):
        trace = _make_trace("trace-record-spans", n_spans=3)
        persist_trace(trace, base_dir=tmp_store)
        record = build_replay_record("trace-record-spans", base_dir=tmp_store)
        assert len(record["spans"]) == 3

    def test_context_merged_with_caller_context(self, tmp_store):
        trace = _make_trace("trace-ctx-merge", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        record = build_replay_record(
            "trace-ctx-merge",
            base_dir=tmp_store,
            context={"triggered_by": "test"},
        )
        assert record["context"]["triggered_by"] == "test"
        assert record["context"]["run_id"] == "run-001"


# ---------------------------------------------------------------------------
# Test 7: execute_replay returns a blocked result when prerequisites not met
# ---------------------------------------------------------------------------

class TestExecuteReplayBlocked:
    def test_blocked_when_trace_not_found(self, tmp_store):
        result = execute_replay("nonexistent-trace", base_dir=tmp_store)
        assert result["status"] == "blocked"
        assert result["prerequisites_valid"] is False
        assert len(result["prerequisite_errors"]) > 0

    def test_blocked_result_has_no_steps(self, tmp_store):
        result = execute_replay("missing-trace", base_dir=tmp_store)
        assert result["steps_executed"] == []


# ---------------------------------------------------------------------------
# Test 8: execute_replay produces a schema-valid result for a simple trace
# ---------------------------------------------------------------------------

class TestExecuteReplaySchemaValid:
    def test_result_is_schema_valid(self, tmp_store):
        trace = _make_trace("trace-schema-valid", n_spans=2)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-schema-valid", base_dir=tmp_store)
        errors = validate_replay_result(result)
        assert errors == []

    def test_result_has_correct_artifact_type(self, tmp_store):
        trace = _make_trace("trace-artifact-type", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-artifact-type", base_dir=tmp_store)
        assert result["artifact_type"] == ARTIFACT_TYPE

    def test_result_has_correct_schema_version(self, tmp_store):
        trace = _make_trace("trace-schema-ver", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-schema-ver", base_dir=tmp_store)
        assert result["schema_version"] == SCHEMA_VERSION

    def test_result_has_replay_id(self, tmp_store):
        trace = _make_trace("trace-replay-id", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-replay-id", base_dir=tmp_store)
        assert isinstance(result["replay_id"], str)
        assert len(result["replay_id"]) > 0

    def test_result_source_trace_id_matches(self, tmp_store):
        trace = _make_trace("trace-src-id", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-src-id", base_dir=tmp_store)
        assert result["source_trace_id"] == "trace-src-id"


# ---------------------------------------------------------------------------
# Test 9: execute_replay captures all spans as steps
# ---------------------------------------------------------------------------

class TestExecuteReplaySteps:
    def test_step_count_equals_span_count(self, tmp_store):
        trace = _make_trace("trace-step-count", n_spans=5)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-step-count", base_dir=tmp_store)
        assert len(result["steps_executed"]) == 5

    def test_steps_have_required_fields(self, tmp_store):
        trace = _make_trace("trace-step-fields", n_spans=2)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-step-fields", base_dir=tmp_store)
        for step in result["steps_executed"]:
            assert "step_index" in step
            assert "span_name" in step
            assert "original_span_id" in step
            assert "status" in step
            assert "replayed_at" in step

    def test_steps_are_indexed_from_zero(self, tmp_store):
        trace = _make_trace("trace-step-idx", n_spans=3)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-step-idx", base_dir=tmp_store)
        indices = [s["step_index"] for s in result["steps_executed"]]
        assert indices == [0, 1, 2]

    def test_steps_preserve_original_span_names(self, tmp_store):
        trace = _make_trace("trace-step-names", n_spans=2)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-step-names", base_dir=tmp_store)
        names = [s["span_name"] for s in result["steps_executed"]]
        assert "op_0" in names
        assert "op_1" in names


# ---------------------------------------------------------------------------
# Test 10: compare_replay_outputs detects status differences
# ---------------------------------------------------------------------------

class TestCompareOutputsDifferences:
    def test_detects_status_mismatch(self):
        original_spans = [
            {
                "span_id": "span-001",
                "name": "op",
                "status": "ok",
                "start_time": "2025-01-01T00:00:00+00:00",
                "end_time": "2025-01-01T00:00:01+00:00",
                "events": [],
            }
        ]
        replay_steps = [
            {
                "step_index": 0,
                "span_name": "op",
                "original_span_id": "span-001",
                "status": "error",
                "replayed_at": "2025-01-01T00:00:02+00:00",
                "error_message": None,
            }
        ]
        comparison = compare_replay_outputs(original_spans, replay_steps)
        assert comparison["compared"] is True
        assert comparison["matched"] is False
        assert len(comparison["differences"]) > 0

    def test_difference_records_both_values(self):
        original_spans = [
            {
                "span_id": "span-001",
                "name": "op",
                "status": "blocked",
                "start_time": "2025-01-01T00:00:00+00:00",
                "end_time": "2025-01-01T00:00:01+00:00",
                "events": [],
            }
        ]
        replay_steps = [
            {
                "step_index": 0,
                "span_name": "op",
                "original_span_id": "span-001",
                "status": "ok",
                "replayed_at": "2025-01-01T00:00:02+00:00",
                "error_message": None,
            }
        ]
        comparison = compare_replay_outputs(original_spans, replay_steps)
        diff = comparison["differences"][0]
        assert diff["original_value"] == "blocked"
        assert diff["replay_value"] == "ok"


# ---------------------------------------------------------------------------
# Test 11: compare_replay_outputs matches when statuses are identical
# ---------------------------------------------------------------------------

class TestCompareOutputsMatch:
    def test_identical_statuses_match(self):
        original_spans = [
            {
                "span_id": "span-001",
                "name": "op",
                "status": "ok",
                "start_time": "2025-01-01T00:00:00+00:00",
                "end_time": "2025-01-01T00:00:01+00:00",
                "events": [],
            }
        ]
        replay_steps = [
            {
                "step_index": 0,
                "span_name": "op",
                "original_span_id": "span-001",
                "status": "ok",
                "replayed_at": "2025-01-01T00:00:02+00:00",
                "error_message": None,
            }
        ]
        comparison = compare_replay_outputs(original_spans, replay_steps)
        assert comparison["compared"] is True
        assert comparison["matched"] is True
        assert comparison["differences"] == []


# ---------------------------------------------------------------------------
# Test 12: compare_replay_outputs handles empty inputs
# ---------------------------------------------------------------------------

class TestCompareOutputsEmpty:
    def test_empty_spans_returns_not_compared(self):
        comparison = compare_replay_outputs([], [])
        assert comparison["compared"] is False
        assert comparison["matched"] is None

    def test_empty_steps_returns_not_compared(self):
        comparison = compare_replay_outputs(
            [{"span_id": "s", "status": "ok"}], []
        )
        assert comparison["compared"] is False

    def test_empty_original_spans_returns_not_compared(self):
        comparison = compare_replay_outputs(
            [],
            [{"step_index": 0, "original_span_id": "s", "status": "ok"}],
        )
        assert comparison["compared"] is False


# ---------------------------------------------------------------------------
# Test 13: validate_replay_result returns empty list for valid result
# ---------------------------------------------------------------------------

class TestValidateReplayResultValid:
    def test_valid_result_returns_no_errors(self):
        result = _make_valid_replay_result()
        errors = validate_replay_result(result)
        assert errors == []

    def test_blocked_result_is_valid(self):
        result = _make_valid_replay_result()
        result["status"] = "blocked"
        result["prerequisites_valid"] = False
        result["prerequisite_errors"] = ["some error"]
        errors = validate_replay_result(result)
        assert errors == []

    def test_partial_status_is_valid(self):
        result = _make_valid_replay_result()
        result["status"] = "partial"
        errors = validate_replay_result(result)
        assert errors == []


# ---------------------------------------------------------------------------
# Test 14: validate_replay_result returns errors for invalid result
# ---------------------------------------------------------------------------

class TestValidateReplayResultErrors:
    def test_missing_required_field(self):
        result = _make_valid_replay_result()
        del result["replay_id"]
        errors = validate_replay_result(result)
        assert len(errors) > 0

    def test_invalid_status_value(self):
        result = _make_valid_replay_result()
        result["status"] = "unknown_status"
        errors = validate_replay_result(result)
        assert len(errors) > 0

    def test_non_dict_input(self):
        errors = validate_replay_result("not a dict")  # type: ignore[arg-type]
        assert len(errors) > 0

    def test_wrong_artifact_type(self):
        result = _make_valid_replay_result()
        result["artifact_type"] = "wrong_type"
        errors = validate_replay_result(result)
        assert len(errors) > 0

    def test_wrong_schema_version(self):
        result = _make_valid_replay_result()
        result["schema_version"] = "9.9.9"
        errors = validate_replay_result(result)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Test 15: execute_replay records determinism notes
# ---------------------------------------------------------------------------

class TestExecuteReplayDeterminismNotes:
    def test_determinism_notes_present(self, tmp_store):
        trace = _make_trace("trace-det-notes", n_spans=2)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-det-notes", base_dir=tmp_store)
        assert isinstance(result["determinism_notes"], list)
        assert len(result["determinism_notes"]) > 0

    def test_determinism_notes_mention_timestamps(self, tmp_store):
        trace = _make_trace("trace-det-timestamps", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-det-timestamps", base_dir=tmp_store)
        notes_text = " ".join(result["determinism_notes"])
        assert "timestamp" in notes_text.lower() or "time" in notes_text.lower()


# ---------------------------------------------------------------------------
# Test 16: execute_replay sets status=success when all steps pass
# ---------------------------------------------------------------------------

class TestExecuteReplaySuccessStatus:
    def test_all_ok_spans_produce_success(self, tmp_store):
        trace = _make_trace("trace-success", n_spans=3)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-success", base_dir=tmp_store)
        assert result["status"] == "success"

    def test_prerequisites_valid_true_on_success(self, tmp_store):
        trace = _make_trace("trace-prereq-true", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-prereq-true", base_dir=tmp_store)
        assert result["prerequisites_valid"] is True
        assert result["prerequisite_errors"] == []


# ---------------------------------------------------------------------------
# Test 17: execute_replay sets status=partial when any step has error/blocked
# ---------------------------------------------------------------------------

class TestExecuteReplayPartialStatus:
    def _make_trace_with_error_span(self, trace_id: str) -> Dict[str, Any]:
        return {
            "trace_id": trace_id,
            "root_span_id": "span-001",
            "spans": [
                {
                    "span_id": "span-001",
                    "trace_id": trace_id,
                    "parent_span_id": None,
                    "name": "root_op",
                    "status": "ok",
                    "start_time": "2025-01-01T00:00:00+00:00",
                    "end_time": "2025-01-01T00:00:01+00:00",
                    "events": [],
                },
                {
                    "span_id": "span-002",
                    "trace_id": trace_id,
                    "parent_span_id": "span-001",
                    "name": "failed_op",
                    "status": "error",
                    "start_time": "2025-01-01T00:00:01+00:00",
                    "end_time": "2025-01-01T00:00:02+00:00",
                    "events": [],
                },
            ],
            "artifacts": [],
            "start_time": "2025-01-01T00:00:00+00:00",
            "end_time": "2025-01-01T00:00:02+00:00",
            "context": {},
            "schema_version": "1.0.0",
        }

    def test_error_span_produces_partial(self, tmp_store):
        trace = self._make_trace_with_error_span("trace-partial-error")
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-partial-error", base_dir=tmp_store)
        assert result["status"] == "partial"


# ---------------------------------------------------------------------------
# Test 18: replay result artifact_type is correct constant
# ---------------------------------------------------------------------------

class TestReplayArtifactType:
    def test_artifact_type_constant(self):
        assert ARTIFACT_TYPE == "replay_result"

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == "1.0.0"

    def test_execute_replay_artifact_type(self, tmp_store):
        trace = _make_trace("trace-art-type", n_spans=1)
        persist_trace(trace, base_dir=tmp_store)
        result = execute_replay("trace-art-type", base_dir=tmp_store)
        assert result["artifact_type"] == "replay_result"
