"""
H07 Chaos Tests — tests/transcript_pipeline/test_chaos_h07.py

Simulates adversarial / failure injection scenarios:
- missing artifact → BLOCK
- malformed artifact → BLOCK
- missing eval → BLOCK
- broken trace → BLOCK
- replay mismatch → BLOCK
- routing failure → BLOCK

Expected: system blocks or freezes with reason_codes. No silent success.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import pytest

from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)
from spectrum_systems.modules.orchestration.pqx_step_harness import (
    PQXExecutionError,
    run_pqx_step,
)
from spectrum_systems.modules.evaluation.pipeline_eval_runner import (
    EvalBlockedError,
    EvalCaseResult,
    EvalStatus,
    aggregate_eval_summary,
    enforce_eval_gate,
    run_eval_case,
)
from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    route_with_gate_evidence,
)

_VALID_GATE_EVIDENCE = {
    "eval_summary_id": "chaos-gate-evidence-001",
    "gate_status": "passed_gate",
}
from tests.transcript_pipeline.conftest import _make_transcript_artifact


# ---------------------------------------------------------------------------
# CHAOS: Missing artifact retrieval → BLOCK
# ---------------------------------------------------------------------------

class TestMissingArtifactChaos:
    def test_retrieve_nonexistent_blocks(self) -> None:
        store = ArtifactStore()
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.retrieve_artifact("TXA-NONEXISTENT-99")
        assert exc_info.value.reason_code == "ARTIFACT_NOT_FOUND"
        assert "TXA-NONEXISTENT-99" in str(exc_info.value)

    def test_store_rejects_artifact_with_no_content(self) -> None:
        store = ArtifactStore()
        with pytest.raises(ArtifactStoreError):
            store.register_artifact({})


# ---------------------------------------------------------------------------
# CHAOS: Malformed artifact → BLOCK at write time
# ---------------------------------------------------------------------------

class TestMalformedArtifactChaos:
    def test_artifact_with_null_trace_id_blocked(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["trace"]["trace_id"] = None
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError):
            store.register_artifact(artifact)

    def test_artifact_with_extra_field_blocked(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["injected_field"] = "SCHEMA_BYPASS_ATTEMPT"
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "SCHEMA_VALIDATION_FAILED"

    def test_artifact_with_tampered_hash_blocked(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["content_hash"] = "sha256:" + "f" * 64
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "CONTENT_HASH_MISMATCH"

    def test_artifact_wrong_type_blocked(self) -> None:
        store = ArtifactStore()
        with pytest.raises(ArtifactStoreError):
            store.register_artifact(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_artifact_with_empty_raw_text_blocked(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact(raw_text="")
        artifact["content_hash"] = compute_content_hash(artifact)
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "SCHEMA_VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# CHAOS: Missing eval → BLOCK
# ---------------------------------------------------------------------------

class TestMissingEvalChaos:
    def test_no_evals_run_blocks(self) -> None:
        summary = aggregate_eval_summary("TXA-CHAOS-001", [])
        with pytest.raises(EvalBlockedError) as exc_info:
            enforce_eval_gate(summary)
        assert "MISSING_REQUIRED_EVALS" in exc_info.value.reason_codes

    def test_partial_evals_blocks(self) -> None:
        results = [
            EvalCaseResult("schema_conformance", "TXA-CHAOS-002", EvalStatus.PASS),
        ]
        summary = aggregate_eval_summary("TXA-CHAOS-002", results)
        with pytest.raises(EvalBlockedError):
            enforce_eval_gate(summary)

    def test_unknown_eval_type_does_not_satisfy_required(self) -> None:
        results = [
            EvalCaseResult("schema_conformance", "TXA-CHAOS-003", EvalStatus.PASS),
            EvalCaseResult("trace_completeness", "TXA-CHAOS-003", EvalStatus.PASS),
            EvalCaseResult("custom_nonstandard_eval", "TXA-CHAOS-003", EvalStatus.PASS),
        ]
        summary = aggregate_eval_summary("TXA-CHAOS-003", results)
        assert summary.overall_status == EvalStatus.FAIL
        assert "replay_consistency" in summary.missing_eval_types


# ---------------------------------------------------------------------------
# CHAOS: Broken trace → BLOCK in eval
# ---------------------------------------------------------------------------

class TestBrokenTraceChaos:
    def test_missing_trace_field_blocks_eval(self) -> None:
        artifact = _make_transcript_artifact()
        del artifact["trace"]
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.FAIL
        assert "MISSING_TRACE" in result.reason_codes

    def test_malformed_trace_id_blocks_eval(self) -> None:
        artifact = _make_transcript_artifact()
        artifact["trace"]["trace_id"] = "NOT_HEX_32_CHARS"
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.FAIL
        assert "INVALID_TRACE_ID" in result.reason_codes

    def test_malformed_span_id_blocks_eval(self) -> None:
        artifact = _make_transcript_artifact()
        artifact["trace"]["span_id"] = "too_short"
        result = run_eval_case("trace_completeness", artifact)
        assert result.status == EvalStatus.FAIL
        assert "INVALID_SPAN_ID" in result.reason_codes


# ---------------------------------------------------------------------------
# CHAOS: Replay mismatch → BLOCK
# ---------------------------------------------------------------------------

class TestReplayMismatchChaos:
    def test_different_content_replay_blocks(self) -> None:
        artifact = _make_transcript_artifact()

        def bad_replay(inputs: Dict[str, Any]) -> Dict[str, Any]:
            return _make_transcript_artifact(raw_text="DIFFERENT CONTENT — chaos injection")

        result = run_eval_case("replay_consistency", artifact, replay_inputs={}, replay_fn=bad_replay)
        assert result.status == EvalStatus.FAIL
        assert "REPLAY_HASH_MISMATCH" in result.reason_codes

    def test_none_replay_output_blocks(self) -> None:
        artifact = _make_transcript_artifact()

        def null_replay(inputs: Dict[str, Any]) -> None:
            return None  # type: ignore[return-value]

        result = run_eval_case("replay_consistency", artifact, replay_inputs={}, replay_fn=null_replay)
        assert result.status == EvalStatus.FAIL
        assert "REPLAY_INVALID_OUTPUT" in result.reason_codes


# ---------------------------------------------------------------------------
# CHAOS: Routing failure → BLOCK
# ---------------------------------------------------------------------------

class TestRoutingFailureChaos:
    def test_unknown_artifact_type_blocks_routing(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence({"artifact_type": "chaos_injected_type"}, _VALID_GATE_EVIDENCE)
        assert "NO_ROUTE_DEFINED" in exc_info.value.reason_codes

    def test_terminal_artifact_blocks_further_routing(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence({"artifact_type": "release_artifact"}, _VALID_GATE_EVIDENCE)
        assert "TERMINAL_ARTIFACT_TYPE" in exc_info.value.reason_codes

    def test_empty_type_blocks_routing(self) -> None:
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence({"artifact_type": ""}, _VALID_GATE_EVIDENCE)
        assert "INVALID_ARTIFACT_TYPE" in exc_info.value.reason_codes


# ---------------------------------------------------------------------------
# CHAOS: PQX execution failures → BLOCK
# ---------------------------------------------------------------------------

class TestPQXExecutionChaos:
    def test_execution_fn_raising_blocks_step(self) -> None:
        store = ArtifactStore()

        def chaos_fn(inputs, trace_id, span_id):
            raise RuntimeError("CHAOS: Simulated execution failure")

        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("chaos_step", {"input_artifact_ids": []}, chaos_fn, store)
        assert "EXECUTION_EXCEPTION" in exc_info.value.reason_codes
        assert exc_info.value.execution_record["status"] == "failed"

    def test_execution_fn_returning_none_blocks_step(self) -> None:
        store = ArtifactStore()

        def null_fn(inputs, trace_id, span_id):
            return None

        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("null_step", {"input_artifact_ids": []}, null_fn, store)
        assert "MISSING_OUTPUT" in exc_info.value.reason_codes

    def test_execution_fn_producing_invalid_schema_blocks(self) -> None:
        store = ArtifactStore()

        def schema_bypass_fn(inputs, trace_id, span_id):
            artifact = _make_transcript_artifact()
            artifact["trace"] = {"trace_id": trace_id, "span_id": span_id}
            artifact["source_format"] = "INJECTED_BYPASS"
            artifact["content_hash"] = compute_content_hash(artifact)
            return artifact

        with pytest.raises(PQXExecutionError) as exc_info:
            run_pqx_step("bypass_step", {"input_artifact_ids": []}, schema_bypass_fn, store)
        assert any("SCHEMA" in rc or "ARTIFACT_STORE" in rc for rc in exc_info.value.reason_codes)


# ---------------------------------------------------------------------------
# CHAOS: End-to-end silent failure prevention
# ---------------------------------------------------------------------------

class TestNoSilentFailures:
    def test_all_errors_carry_reason_codes(self) -> None:
        store = ArtifactStore()

        try:
            store.retrieve_artifact("TXA-NONEXISTENT")
        except ArtifactStoreError as e:
            assert e.reason_code
            return
        pytest.fail("Expected ArtifactStoreError")

    def test_all_pqx_errors_carry_reason_codes(self) -> None:
        store = ArtifactStore()

        def fail_fn(inputs, trace_id, span_id):
            raise ValueError("chaos")

        try:
            run_pqx_step("chaos", {"input_artifact_ids": []}, fail_fn, store)
        except PQXExecutionError as e:
            assert e.reason_codes
            return
        pytest.fail("Expected PQXExecutionError")

    def test_all_eval_blocks_carry_reason_codes(self) -> None:
        summary = aggregate_eval_summary("X", [])
        try:
            enforce_eval_gate(summary)
        except EvalBlockedError as e:
            assert e.reason_codes
            return
        pytest.fail("Expected EvalBlockedError")

    def test_all_routing_errors_carry_reason_codes(self) -> None:
        try:
            route_with_gate_evidence({"artifact_type": "CHAOS_TYPE"}, _VALID_GATE_EVIDENCE)
        except ArtifactRoutingError as e:
            assert e.reason_codes
            return
        pytest.fail("Expected ArtifactRoutingError")


# ---------------------------------------------------------------------------
# CHAOS: Post-write mutation prevention (FIX-004 regression)
# ---------------------------------------------------------------------------

class TestPostWriteMutationChaos:
    def test_post_write_mutation_does_not_corrupt_store(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        original_text = artifact["raw_text"]
        store.register_artifact(artifact)
        artifact["raw_text"] = "CHAOS: MUTATION AFTER WRITE"
        retrieved = store.retrieve_artifact(artifact["artifact_id"])
        assert retrieved["raw_text"] == original_text

    def test_tampered_hash_in_eval_blocks_schema_conformance(self) -> None:
        """FIX-001/FIX-006 regression: schema_conformance catches content_hash tampering."""
        artifact = _make_transcript_artifact()
        artifact["content_hash"] = "sha256:" + "deadbeef" * 8
        result = run_eval_case("schema_conformance", artifact)
        assert result.status == EvalStatus.FAIL
        assert "CONTENT_HASH_MISMATCH" in result.reason_codes
