"""
H04 Pipeline Eval Runner Tests — tests/transcript_pipeline/test_pipeline_eval_runner_h04.py

Tests:
- passing eval (all three types pass)
- failing eval (each type can fail independently)
- missing eval case → BLOCK (fail-closed)
- indeterminate / unreachable states → FAIL
- enforce_eval_gate raises on failure
- EvalBlockedError carries reason_codes
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import pytest

from spectrum_systems.modules.evaluation.pipeline_eval_runner import (
    EvalBlockedError,
    EvalCaseResult,
    EvalStatus,
    REQUIRED_EVAL_TYPES,
    aggregate_eval_summary,
    enforce_eval_gate,
    run_eval_case,
)
from spectrum_systems.modules.runtime.artifact_store import compute_content_hash
from tests.transcript_pipeline.conftest import _make_transcript_artifact


def _valid_artifact() -> Dict[str, Any]:
    return _make_transcript_artifact()


def _artifact_missing_trace() -> Dict[str, Any]:
    a = _make_transcript_artifact()
    del a["trace"]
    a["content_hash"] = compute_content_hash(a)
    return a


def _artifact_bad_span_id() -> Dict[str, Any]:
    a = _make_transcript_artifact()
    a["trace"]["span_id"] = "NOT_VALID"
    a["content_hash"] = compute_content_hash(a)
    return a


class TestSchemaConformanceEval:
    def test_valid_artifact_passes(self) -> None:
        artifact = _valid_artifact()
        result = run_eval_case("schema_conformance", artifact)
        assert result.status == EvalStatus.PASS

    def test_artifact_missing_required_field_fails(self) -> None:
        artifact = _valid_artifact()
        del artifact["raw_text"]
        result = run_eval_case("schema_conformance", artifact)
        assert result.status == EvalStatus.FAIL
        assert result.reason_codes

    def test_invalid_schema_ref_fails(self) -> None:
        artifact = _valid_artifact()
        artifact["schema_ref"] = "unknown/type"
        result = run_eval_case("schema_conformance", artifact)
        assert result.status == EvalStatus.FAIL

    def test_tampered_content_hash_fails(self) -> None:
        """FIX-001/FIX-006 regression: schema_conformance now verifies content_hash."""
        artifact = _valid_artifact()
        artifact["content_hash"] = "sha256:" + "0" * 64
        result = run_eval_case("schema_conformance", artifact)
        assert result.status == EvalStatus.FAIL
        assert "CONTENT_HASH_MISMATCH" in result.reason_codes

    def test_correct_content_hash_passes(self) -> None:
        artifact = _valid_artifact()
        result = run_eval_case("schema_conformance", artifact)
        assert result.status == EvalStatus.PASS


class TestTraceCompletenessEval:
    def test_valid_trace_passes(self) -> None:
        artifact = _valid_artifact()
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.PASS

    def test_missing_trace_field_fails(self) -> None:
        artifact = _artifact_missing_trace()
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.FAIL
        assert "MISSING_TRACE" in result.reason_codes

    def test_invalid_trace_id_fails(self) -> None:
        artifact = _valid_artifact()
        artifact["trace"]["trace_id"] = "short"
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.FAIL
        assert "INVALID_TRACE_ID" in result.reason_codes

    def test_invalid_span_id_fails(self) -> None:
        artifact = _artifact_bad_span_id()
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.FAIL
        assert "INVALID_SPAN_ID" in result.reason_codes


class TestReplayConsistencyEval:
    def test_consistent_replay_passes(self) -> None:
        artifact = _valid_artifact()

        def replay_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
            replayed = dict(artifact)
            return replayed

        result = run_eval_case("replay_consistency", artifact, replay_inputs={}, replay_fn=replay_fn)
        assert result.status == EvalStatus.PASS

    def test_inconsistent_replay_fails(self) -> None:
        artifact = _valid_artifact()

        def replay_fn(inputs: Dict[str, Any]) -> Dict[str, Any]:
            different = _make_transcript_artifact(raw_text="Different content")
            return different

        result = run_eval_case("replay_consistency", artifact, replay_inputs={}, replay_fn=replay_fn)
        assert result.status == EvalStatus.FAIL
        assert "REPLAY_HASH_MISMATCH" in result.reason_codes

    def test_missing_replay_inputs_fails(self) -> None:
        artifact = _valid_artifact()
        result = run_eval_case("replay_consistency", artifact)
        assert result.status == EvalStatus.FAIL
        assert "REPLAY_INPUTS_MISSING" in result.reason_codes

    def test_replay_fn_raises_fails(self) -> None:
        artifact = _valid_artifact()

        def bad_replay(inputs: Dict[str, Any]) -> Dict[str, Any]:
            raise RuntimeError("Replay failed")

        result = run_eval_case("replay_consistency", artifact, replay_inputs={}, replay_fn=bad_replay)
        assert result.status == EvalStatus.FAIL
        assert "REPLAY_EXECUTION_FAILED" in result.reason_codes

    def test_unknown_eval_type_fails(self) -> None:
        artifact = _valid_artifact()
        result = run_eval_case("nonexistent_eval", artifact)
        assert result.status == EvalStatus.FAIL
        assert "UNKNOWN_EVAL_TYPE" in result.reason_codes


class TestAggregateSummary:
    def _pass_result(self, eval_type: str, artifact_id: str = "TXA-001") -> EvalCaseResult:
        return EvalCaseResult(eval_type=eval_type, artifact_id=artifact_id, status=EvalStatus.PASS)

    def _fail_result(self, eval_type: str, artifact_id: str = "TXA-001") -> EvalCaseResult:
        return EvalCaseResult(
            eval_type=eval_type,
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["SOME_FAILURE"],
        )

    def test_all_three_pass_gives_overall_pass(self) -> None:
        results = [
            self._pass_result("schema_conformance"),
            self._pass_result("replay_consistency"),
            self._pass_result("trace_completeness"),
        ]
        summary = aggregate_eval_summary("TXA-001", results)
        assert summary.overall_status == EvalStatus.PASS
        assert summary.missing_eval_types == []

    def test_one_fail_gives_overall_fail(self) -> None:
        results = [
            self._pass_result("schema_conformance"),
            self._fail_result("replay_consistency"),
            self._pass_result("trace_completeness"),
        ]
        summary = aggregate_eval_summary("TXA-001", results)
        assert summary.overall_status == EvalStatus.FAIL
        assert "EVAL_CASE_FAILED" in summary.reason_codes

    def test_missing_eval_type_gives_overall_fail(self) -> None:
        results = [
            self._pass_result("schema_conformance"),
            self._pass_result("trace_completeness"),
            # replay_consistency missing
        ]
        summary = aggregate_eval_summary("TXA-001", results)
        assert summary.overall_status == EvalStatus.FAIL
        assert "replay_consistency" in summary.missing_eval_types
        assert "MISSING_REQUIRED_EVALS" in summary.reason_codes

    def test_empty_results_gives_fail_with_all_missing(self) -> None:
        summary = aggregate_eval_summary("TXA-001", [])
        assert summary.overall_status == EvalStatus.FAIL
        assert set(summary.missing_eval_types) == REQUIRED_EVAL_TYPES


class TestEvalGateEnforcement:
    def test_passing_summary_does_not_raise(self) -> None:
        results = [
            EvalCaseResult("schema_conformance", "TXA-001", EvalStatus.PASS),
            EvalCaseResult("replay_consistency", "TXA-001", EvalStatus.PASS),
            EvalCaseResult("trace_completeness", "TXA-001", EvalStatus.PASS),
        ]
        summary = aggregate_eval_summary("TXA-001", results)
        enforce_eval_gate(summary)  # must not raise

    def test_failing_summary_raises_eval_blocked_error(self) -> None:
        results = [
            EvalCaseResult("schema_conformance", "TXA-001", EvalStatus.PASS),
        ]
        summary = aggregate_eval_summary("TXA-001", results)
        with pytest.raises(EvalBlockedError) as exc_info:
            enforce_eval_gate(summary)
        assert exc_info.value.reason_codes
        assert exc_info.value.eval_summary is not None

    def test_missing_eval_type_blocks(self) -> None:
        summary = aggregate_eval_summary("TXA-001", [])
        with pytest.raises(EvalBlockedError) as exc_info:
            enforce_eval_gate(summary)
        assert "MISSING_REQUIRED_EVALS" in exc_info.value.reason_codes

    def test_eval_blocked_error_has_to_dict(self) -> None:
        summary = aggregate_eval_summary("TXA-001", [])
        with pytest.raises(EvalBlockedError) as exc_info:
            enforce_eval_gate(summary)
        d = exc_info.value.to_dict()
        assert "error" in d
        assert "reason_codes" in d
        assert "eval_summary" in d
