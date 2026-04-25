"""
H03 PQX Step Harness Tests — tests/transcript_pipeline/test_pqx_step_harness_h03.py

Tests:
- success path: execution_fn returns valid artifact → registered + record emitted
- failure path: schema violation → PQXExecutionError + record emitted
- missing output (None) → PQXExecutionError
- execution_fn raises → PQXExecutionError + record contains reason_codes
- every execution produces a pqx_execution_record
- record contains trace_id and span_id
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import pytest

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore, compute_content_hash
from spectrum_systems.modules.orchestration.pqx_step_harness import (
    PQXExecutionError,
    run_pqx_step,
)
from tests.transcript_pipeline.conftest import _make_transcript_artifact, _trace, _provenance


def _good_execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
    artifact: Dict[str, Any] = {
        "artifact_id": f"TXA-{uuid.uuid4().hex[:8].upper()}",
        "artifact_type": "transcript_artifact",
        "schema_ref": "transcript_pipeline/transcript_artifact",
        "schema_version": "1.0.0",
        "trace": {"trace_id": trace_id, "span_id": span_id},
        "provenance": {"produced_by": "test_step", "input_artifact_ids": inputs.get("input_artifact_ids", [])},
        "created_at": "2026-04-25T00:00:00+00:00",
        "source_format": "txt",
        "raw_text": "Test transcript content",
    }
    artifact["content_hash"] = compute_content_hash(artifact)
    return artifact


def _none_execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> None:
    return None  # type: ignore[return-value]


def _raises_execution_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
    raise ValueError("Simulated execution failure")


def _schema_violation_fn(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
    artifact = _good_execution_fn(inputs, trace_id, span_id)
    artifact["source_format"] = "INVALID_FORMAT"
    artifact["content_hash"] = compute_content_hash(artifact)
    return artifact


class TestPQXStepHarnessSuccess:
    def test_success_returns_execution_record_and_output(self) -> None:
        store = ArtifactStore()
        result = run_pqx_step(
            "normalize_transcript",
            {"input_artifact_ids": []},
            _good_execution_fn,
            store,
        )
        assert "execution_record" in result
        assert "output_artifact" in result

    def test_execution_record_has_required_fields(self) -> None:
        store = ArtifactStore()
        result = run_pqx_step("test_step", {"input_artifact_ids": []}, _good_execution_fn, store)
        rec = result["execution_record"]
        assert rec["status"] == "success"
        assert rec["step_name"] == "test_step"
        assert "trace_id" in rec
        assert "span_id" in rec
        assert "started_at" in rec
        assert "completed_at" in rec
        assert "duration_ms" in rec

    def test_output_artifact_registered_in_store(self) -> None:
        store = ArtifactStore()
        result = run_pqx_step("test_step", {"input_artifact_ids": []}, _good_execution_fn, store)
        output_id = result["output_artifact"]["artifact_id"]
        assert store.artifact_exists(output_id)

    def test_output_artifact_inherits_trace_id(self) -> None:
        store = ArtifactStore()
        result = run_pqx_step("test_step", {"input_artifact_ids": []}, _good_execution_fn, store)
        rec = result["execution_record"]
        artifact = result["output_artifact"]
        assert artifact["trace"]["trace_id"] == rec["trace_id"]

    def test_parent_trace_id_propagated(self) -> None:
        store = ArtifactStore()
        parent_trace = "a" * 32
        result = run_pqx_step(
            "test_step", {"input_artifact_ids": []}, _good_execution_fn, store,
            parent_trace_id=parent_trace,
        )
        assert result["execution_record"]["trace_id"] == parent_trace


class TestPQXStepHarnessFailClosed:
    def test_none_output_raises_pqx_error(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("test_step", {"input_artifact_ids": []}, _none_execution_fn, store)
        assert "MISSING_OUTPUT" in exc_info.value.reason_codes

    def test_execution_exception_raises_pqx_error(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("test_step", {"input_artifact_ids": []}, _raises_execution_fn, store)
        assert "EXECUTION_EXCEPTION" in exc_info.value.reason_codes

    def test_schema_violation_raises_pqx_error(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("test_step", {"input_artifact_ids": []}, _schema_violation_fn, store)
        assert any("SCHEMA" in rc or "ARTIFACT_STORE" in rc for rc in exc_info.value.reason_codes)

    def test_pqx_error_carries_execution_record(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("test_step", {"input_artifact_ids": []}, _raises_execution_fn, store)
        assert exc_info.value.execution_record is not None
        assert exc_info.value.execution_record["status"] == "failed"

    def test_invalid_step_name_raises(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("", {"input_artifact_ids": []}, _good_execution_fn, store)
        assert "INVALID_STEP_NAME" in exc_info.value.reason_codes

    def test_noncallable_fn_raises(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("test_step", {"input_artifact_ids": []}, "not_callable", store)  # type: ignore[arg-type]
        assert "INVALID_EXECUTION_FN" in exc_info.value.reason_codes

    def test_failed_step_does_not_register_output(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError):
            run_pqx_step("test_step", {"input_artifact_ids": []}, _raises_execution_fn, store)
        assert store.artifact_count() == 0


class TestOutputTypeEnforcement:
    """FIX-002 regression: expected_output_type enforcement prevents wrong-type artifact production."""

    def test_correct_output_type_passes(self) -> None:
        store = ArtifactStore()
        result = run_pqx_step(
            "test_step",
            {"input_artifact_ids": []},
            _good_execution_fn,
            store,
            expected_output_type="transcript_artifact",
        )
        assert result["output_artifact"]["artifact_type"] == "transcript_artifact"

    def test_wrong_output_type_raises(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step(
                "test_step",
                {"input_artifact_ids": []},
                _good_execution_fn,
                store,
                expected_output_type="meeting_minutes_artifact",
            )
        assert "OUTPUT_TYPE_MISMATCH" in exc_info.value.reason_codes

    def test_wrong_output_type_does_not_register_artifact(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError):
            run_pqx_step(
                "test_step",
                {"input_artifact_ids": []},
                _good_execution_fn,
                store,
                expected_output_type="paper_draft_artifact",
            )
        assert store.artifact_count() == 0

    def test_no_expected_type_accepts_any(self) -> None:
        store = ArtifactStore()
        result = run_pqx_step(
            "test_step",
            {"input_artifact_ids": []},
            _good_execution_fn,
            store,
        )
        assert result["output_artifact"] is not None
