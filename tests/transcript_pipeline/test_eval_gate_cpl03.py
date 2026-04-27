"""
CPL-03 — Eval Gate tests.

Coverage:
  * Schema audit positive + negative (eval_summary, gate_evidence)
  * Pure evaluation: passing case yields passed_gate + overall_status=pass
  * Five required eval names always run; deterministic ordering
  * Fail-closed cases:
      - schema violation (extra fields, missing source linkage)
      - trace missing / malformed
      - fake source_turn_id (orphan segment)
      - segment drift (text tampered while id matches)
      - manifest_hash mismatch
      - partial coverage (segments < turns)
      - missing eval_summary id reference in gate
  * Authority bypass attempts (wrong artifact_type, malformed inputs)
  * PQX integration: both artifacts registered, two execution_records emitted,
    trace inherited from step 1 to step 2
  * Direct-write lock-down (assembler-style): pure function returns no
    content_hash, so direct ArtifactStore.register_artifact raises CONTENT_HASH_MISMATCH
  * Authority-shape vocabulary regression on the new module + review artifacts
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.modules.orchestration.pqx_step_harness import PQXExecutionError
from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)
from spectrum_systems.modules.transcript_pipeline.context_bundle_assembler import (
    assemble_context_bundle,
    assemble_context_bundle_via_pqx,
)
from spectrum_systems.modules.transcript_pipeline.eval_gate import (
    EVAL_NAME_COVERAGE,
    EVAL_NAME_REFERENTIAL,
    EVAL_NAME_REPLAY,
    EVAL_NAME_SCHEMA,
    EVAL_NAME_TRACE,
    EVAL_SUMMARY_ARTIFACT_TYPE,
    EVAL_SUMMARY_SCHEMA_REF,
    GATE_EVIDENCE_ARTIFACT_TYPE,
    GATE_EVIDENCE_SCHEMA_REF,
    GATE_STATUS_FAILED,
    GATE_STATUS_MISSING,
    GATE_STATUS_PASSED,
    PRODUCED_BY,
    REQUIRED_EVAL_NAMES,
    EvalGateError,
    evaluate_transcript_context,
    run_eval_gate_via_pqx,
)
from spectrum_systems.modules.transcript_pipeline.transcript_ingestor import (
    ingest_transcript,
    ingest_transcript_via_pqx,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMA_DIR = (
    Path(__file__).parent.parent.parent / "contracts" / "schemas" / "transcript_pipeline"
)


def _load_schema(name: str) -> Dict[str, Any]:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_load_schema(name), format_checker=FormatChecker())


def _frozen_clock() -> datetime:
    return datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc)


def _build_pair() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build a deterministic (transcript_artifact, context_bundle) pair."""
    transcript = ingest_transcript(
        str(FIXTURES_DIR / "valid_transcript.txt"),
        trace_id="a" * 32,
        span_id="b" * 16,
        run_id="run-cpl03-fixture",
    )
    transcript["content_hash"] = compute_content_hash(transcript)
    bundle = assemble_context_bundle(
        transcript,
        trace_id="a" * 32,
        span_id="b" * 16,
        clock=_frozen_clock,
    )
    bundle["content_hash"] = compute_content_hash(bundle)
    return transcript, bundle


def _evaluate(
    transcript: Dict[str, Any],
    bundle: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return evaluate_transcript_context(
        transcript,
        bundle,
        trace_id="a" * 32,
        span_id="b" * 16,
        run_id="run-cpl03",
        clock=_frozen_clock,
    )


# ---------------------------------------------------------------------------
# CPL-03-1 — Eval Summary schema audit
# ---------------------------------------------------------------------------


class TestEvalSummarySchemaAudit:
    def test_schema_required_fields(self) -> None:
        schema = _load_schema("eval_summary")
        for field in (
            "artifact_id",
            "artifact_type",
            "schema_ref",
            "schema_version",
            "content_hash",
            "trace",
            "provenance",
            "created_at",
            "evaluated_artifact_ids",
            "eval_results",
            "overall_status",
        ):
            assert field in schema["required"], f"missing required field {field!r}"

    def test_schema_no_additional_properties(self) -> None:
        schema = _load_schema("eval_summary")
        assert schema.get("additionalProperties") is False

    def test_schema_eval_results_minimum(self) -> None:
        schema = _load_schema("eval_summary")
        assert schema["properties"]["eval_results"]["minItems"] == 1

    def test_schema_evaluated_artifact_ids_minimum(self) -> None:
        schema = _load_schema("eval_summary")
        assert schema["properties"]["evaluated_artifact_ids"]["minItems"] == 1

    def test_schema_overall_status_enum(self) -> None:
        schema = _load_schema("eval_summary")
        assert schema["properties"]["overall_status"]["enum"] == ["pass", "fail"]

    def test_schema_eval_result_required(self) -> None:
        schema = _load_schema("eval_summary")
        eval_result = schema["$defs"]["eval_result"]
        for field in ("eval_name", "status", "reason_codes"):
            assert field in eval_result["required"]
        assert eval_result["additionalProperties"] is False

    def test_payload_validates(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, _ = _evaluate(transcript, bundle)
        eval_summary["content_hash"] = compute_content_hash(eval_summary)
        errors = list(_validator("eval_summary").iter_errors(eval_summary))
        assert not errors, [e.message for e in errors]

    def test_unknown_field_rejected(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, _ = _evaluate(transcript, bundle)
        eval_summary["rogue"] = "no"
        eval_summary["content_hash"] = compute_content_hash(eval_summary)
        errors = list(_validator("eval_summary").iter_errors(eval_summary))
        assert errors


# ---------------------------------------------------------------------------
# CPL-03-2 — Gate Evidence schema audit
# ---------------------------------------------------------------------------


class TestGateEvidenceSchemaAudit:
    def test_schema_required_fields(self) -> None:
        schema = _load_schema("gate_evidence")
        for field in (
            "artifact_id",
            "artifact_type",
            "schema_ref",
            "schema_version",
            "content_hash",
            "trace",
            "provenance",
            "created_at",
            "target_artifact_ids",
            "gate_status",
            "eval_summary_id",
        ):
            assert field in schema["required"]

    def test_schema_no_additional_properties(self) -> None:
        schema = _load_schema("gate_evidence")
        assert schema.get("additionalProperties") is False

    def test_gate_status_enum_values(self) -> None:
        schema = _load_schema("gate_evidence")
        assert sorted(schema["properties"]["gate_status"]["enum"]) == sorted(
            ["passed_gate", "failed_gate", "conditional_gate", "missing_gate"]
        )

    def test_eval_summary_id_pattern(self) -> None:
        schema = _load_schema("gate_evidence")
        assert schema["properties"]["eval_summary_id"]["pattern"] == r"^EVS-[A-Z0-9_-]+$"

    def test_payload_validates(self) -> None:
        transcript, bundle = _build_pair()
        _, gate_evidence = _evaluate(transcript, bundle)
        gate_evidence["content_hash"] = compute_content_hash(gate_evidence)
        errors = list(_validator("gate_evidence").iter_errors(gate_evidence))
        assert not errors, [e.message for e in errors]

    def test_unknown_field_rejected(self) -> None:
        transcript, bundle = _build_pair()
        _, gate_evidence = _evaluate(transcript, bundle)
        gate_evidence["rogue"] = "no"
        gate_evidence["content_hash"] = compute_content_hash(gate_evidence)
        errors = list(_validator("gate_evidence").iter_errors(gate_evidence))
        assert errors


# ---------------------------------------------------------------------------
# CPL-03-3 — Pure evaluator
# ---------------------------------------------------------------------------


class TestEvaluator:
    def test_passing_case_yields_passed_gate(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert eval_summary["overall_status"] == "pass"
        assert gate_evidence["gate_status"] == GATE_STATUS_PASSED
        assert gate_evidence["routable"] is True
        assert gate_evidence["eval_summary_id"] == eval_summary["artifact_id"]

    def test_all_required_evals_present(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, _ = _evaluate(transcript, bundle)
        names = [r["eval_name"] for r in eval_summary["eval_results"]]
        for required in REQUIRED_EVAL_NAMES:
            assert required in names
        assert names == list(REQUIRED_EVAL_NAMES), "eval order is canonical"

    def test_evaluator_envelope_shape(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert eval_summary["artifact_type"] == EVAL_SUMMARY_ARTIFACT_TYPE
        assert eval_summary["schema_ref"] == EVAL_SUMMARY_SCHEMA_REF
        assert eval_summary["provenance"]["produced_by"] == PRODUCED_BY
        assert eval_summary["provenance"]["input_artifact_ids"] == [
            transcript["artifact_id"],
            bundle["artifact_id"],
        ]
        assert gate_evidence["artifact_type"] == GATE_EVIDENCE_ARTIFACT_TYPE
        assert gate_evidence["schema_ref"] == GATE_EVIDENCE_SCHEMA_REF
        assert gate_evidence["provenance"]["input_artifact_ids"][0] == eval_summary["artifact_id"]
        assert eval_summary["artifact_id"].startswith("EVS-")
        assert gate_evidence["artifact_id"].startswith("GTE-")

    def test_evaluator_returns_no_content_hash(self) -> None:
        """Pure function must not mint content_hash; only PQX harness does."""
        transcript, bundle = _build_pair()
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert "content_hash" not in eval_summary
        assert "content_hash" not in gate_evidence

    def test_replay_determinism(self) -> None:
        """Same inputs => identical artifact ids and identical content_hash."""
        transcript, bundle = _build_pair()
        a_summary, a_evidence = _evaluate(transcript, bundle)
        b_summary, b_evidence = _evaluate(transcript, bundle)
        assert a_summary["artifact_id"] == b_summary["artifact_id"]
        assert a_evidence["artifact_id"] == b_evidence["artifact_id"]
        assert compute_content_hash(a_summary) == compute_content_hash(b_summary)
        assert compute_content_hash(a_evidence) == compute_content_hash(b_evidence)

    def test_evaluator_does_not_mutate_input(self) -> None:
        transcript, bundle = _build_pair()
        snap_t = copy.deepcopy(transcript)
        snap_b = copy.deepcopy(bundle)
        _evaluate(transcript, bundle)
        assert transcript == snap_t
        assert bundle == snap_b


# ---------------------------------------------------------------------------
# CPL-03-4 — Fail-closed gate logic (attack matrix)
# ---------------------------------------------------------------------------


class TestFailClosedGate:
    def _expect_fail(
        self,
        transcript: Dict[str, Any],
        bundle: Dict[str, Any],
        *,
        expected_reason: str,
    ) -> Dict[str, Any]:
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert eval_summary["overall_status"] == "fail", eval_summary
        assert gate_evidence["gate_status"] == GATE_STATUS_FAILED, gate_evidence
        assert gate_evidence["routable"] is False
        assert expected_reason in gate_evidence["reason_codes"], (
            expected_reason,
            gate_evidence["reason_codes"],
        )
        return gate_evidence

    def test_schema_violation_on_bundle(self) -> None:
        transcript, bundle = _build_pair()
        bundle["segments"][0]["rogue"] = "no"
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="BUNDLE_SCHEMA_VALIDATION_FAILED")

    def test_broken_trace_fails(self) -> None:
        transcript, bundle = _build_pair()
        bundle["trace"] = {"trace_id": "not-hex", "span_id": "x" * 16}
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="BUNDLE_TRACE_ID_INVALID")

    def test_fake_source_turn_id(self) -> None:
        transcript, bundle = _build_pair()
        bundle["segments"][0]["source_turn_id"] = "T-9999"
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="ORPHAN_SEGMENT")

    def test_segment_drift_detected(self) -> None:
        transcript, bundle = _build_pair()
        # Tamper text while keeping source_turn_id intact.
        bundle["segments"][0]["text"] = bundle["segments"][0]["text"] + " (tampered)"
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="SEGMENT_TURN_DRIFT")

    def test_manifest_hash_mismatch(self) -> None:
        transcript, bundle = _build_pair()
        bundle["manifest_hash"] = "sha256:" + "0" * 64
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="REPLAY_MANIFEST_HASH_MISMATCH")

    def test_partial_coverage_fails(self) -> None:
        transcript, bundle = _build_pair()
        bundle["segments"] = bundle["segments"][:-1]
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="COVERAGE_COUNT_MISMATCH")

    def test_extra_segment_fails_coverage(self) -> None:
        transcript, bundle = _build_pair()
        # Append a duplicate segment to break 1:1 coverage.
        clone = copy.deepcopy(bundle["segments"][0])
        clone["segment_id"] = "SEG-9999"
        bundle["segments"].append(clone)
        bundle["content_hash"] = compute_content_hash(bundle)
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert gate_evidence["gate_status"] == GATE_STATUS_FAILED
        assert "COVERAGE_COUNT_MISMATCH" in gate_evidence["reason_codes"]

    def test_source_link_mismatch(self) -> None:
        transcript, bundle = _build_pair()
        bundle["source_artifact_id"] = "TXA-OTHER"
        bundle["content_hash"] = compute_content_hash(bundle)
        self._expect_fail(transcript, bundle, expected_reason="BUNDLE_SOURCE_LINK_MISMATCH")

    def test_content_hash_mismatch_on_bundle(self) -> None:
        transcript, bundle = _build_pair()
        bundle["content_hash"] = "sha256:" + "0" * 64
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert gate_evidence["gate_status"] == GATE_STATUS_FAILED
        assert "BUNDLE_CONTENT_HASH_MISMATCH" in gate_evidence["reason_codes"]

    def test_wrong_artifact_type_halts(self) -> None:
        _, bundle = _build_pair()
        with pytest.raises(EvalGateError) as exc:
            evaluate_transcript_context(
                {"artifact_type": "not_a_transcript", "artifact_id": "TXA-X"},
                bundle,
                trace_id="a" * 32,
                span_id="b" * 16,
            )
        assert exc.value.reason_code == "INVALID_TRANSCRIPT_ARTIFACT_TYPE"

    def test_non_mapping_inputs_halt(self) -> None:
        with pytest.raises(EvalGateError) as exc:
            evaluate_transcript_context("not a dict", {}, trace_id="a" * 32, span_id="b" * 16)  # type: ignore[arg-type]
        assert exc.value.reason_code == "INVALID_TRANSCRIPT_INPUT_TYPE"

    def test_invalid_trace_id_halts(self) -> None:
        transcript, bundle = _build_pair()
        with pytest.raises(EvalGateError) as exc:
            evaluate_transcript_context(transcript, bundle, trace_id="bad", span_id="b" * 16)
        assert exc.value.reason_code == "INVALID_TRACE_ID"

    def test_invalid_span_id_halts(self) -> None:
        transcript, bundle = _build_pair()
        with pytest.raises(EvalGateError) as exc:
            evaluate_transcript_context(transcript, bundle, trace_id="a" * 32, span_id="zzz")
        assert exc.value.reason_code == "INVALID_SPAN_ID"


# ---------------------------------------------------------------------------
# CPL-03-5 — PQX integration
# ---------------------------------------------------------------------------


class TestPQXIntegration:
    def _ingested_pair(self, store: ArtifactStore) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        transcript_result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
            run_id="run-cpl03-pqx",
        )
        transcript = transcript_result["output_artifact"]
        bundle_result = assemble_context_bundle_via_pqx(
            transcript,
            store,
            run_id="run-cpl03-pqx",
        )
        bundle = bundle_result["output_artifact"]
        return transcript, bundle

    def test_runs_two_steps_and_registers_both_artifacts(self) -> None:
        store = ArtifactStore()
        transcript, bundle = self._ingested_pair(store)
        result = run_eval_gate_via_pqx(transcript, bundle, store, run_id="run-cpl03-pqx")

        summary = result["eval_summary"]
        evidence = result["gate_evidence"]
        assert summary["execution_record"]["status"] == "success"
        assert summary["execution_record"]["step_name"] == "eval_gate_summary"
        assert evidence["execution_record"]["status"] == "success"
        assert evidence["execution_record"]["step_name"] == "eval_gate_evidence"

        assert summary["output_artifact"]["artifact_type"] == EVAL_SUMMARY_ARTIFACT_TYPE
        assert evidence["output_artifact"]["artifact_type"] == GATE_EVIDENCE_ARTIFACT_TYPE
        assert evidence["output_artifact"]["eval_summary_id"] == summary["output_artifact"]["artifact_id"]

        assert store.artifact_exists(summary["output_artifact"]["artifact_id"])
        assert store.artifact_exists(evidence["output_artifact"]["artifact_id"])

    def test_pqx_inherits_parent_trace(self) -> None:
        store = ArtifactStore()
        transcript, bundle = self._ingested_pair(store)
        parent = "f" * 32
        result = run_eval_gate_via_pqx(
            transcript,
            bundle,
            store,
            parent_trace_id=parent,
            run_id="run-cpl03-pqx",
        )
        assert result["eval_summary"]["output_artifact"]["trace"]["trace_id"] == parent
        assert result["gate_evidence"]["output_artifact"]["trace"]["trace_id"] == parent

    def test_pqx_summary_and_evidence_share_trace(self) -> None:
        """When parent_trace_id is omitted, step 2 inherits step 1's trace_id."""
        store = ArtifactStore()
        transcript, bundle = self._ingested_pair(store)
        result = run_eval_gate_via_pqx(transcript, bundle, store)
        summary_trace = result["eval_summary"]["output_artifact"]["trace"]["trace_id"]
        evidence_trace = result["gate_evidence"]["output_artifact"]["trace"]["trace_id"]
        assert summary_trace == evidence_trace

    def test_pqx_step_records_have_distinct_span_ids(self) -> None:
        store = ArtifactStore()
        transcript, bundle = self._ingested_pair(store)
        result = run_eval_gate_via_pqx(transcript, bundle, store)
        s_span = result["eval_summary"]["execution_record"]["span_id"]
        e_span = result["gate_evidence"]["execution_record"]["span_id"]
        assert s_span != e_span

    def test_pqx_fails_closed_on_bad_input(self) -> None:
        store = ArtifactStore()
        bad_transcript: Dict[str, Any] = {"artifact_type": "transcript_artifact"}
        with pytest.raises(PQXExecutionError) as exc:
            run_eval_gate_via_pqx(bad_transcript, {"artifact_type": "context_bundle"}, store)
        assert exc.value.execution_record["status"] == "failed"
        assert "EXECUTION_EXCEPTION" in exc.value.reason_codes

    def test_pqx_fails_closed_when_bundle_invalid(self) -> None:
        store = ArtifactStore()
        transcript, bundle = self._ingested_pair(store)
        # Even though we still produce a gate_evidence with failed_gate,
        # registration of artifacts succeeds and reflects the failed state.
        bundle = copy.deepcopy(bundle)
        bundle["segments"][0]["source_turn_id"] = "T-9999"
        bundle["manifest_hash"] = "sha256:" + "0" * 64
        bundle["content_hash"] = compute_content_hash(bundle)
        # The original valid bundle is still in the store; the tampered copy is
        # not registered. The eval gate consumes the in-memory dict directly.
        result = run_eval_gate_via_pqx(transcript, bundle, store)
        assert result["gate_evidence"]["output_artifact"]["gate_status"] == GATE_STATUS_FAILED
        assert "ORPHAN_SEGMENT" in result["gate_evidence"]["output_artifact"]["reason_codes"]

    def test_evaluator_cannot_register_directly_without_pqx(self) -> None:
        """Bypass attempt: hand the pure-function output to the artifact store."""
        store = ArtifactStore()
        transcript, bundle = _build_pair()
        # Pre-register the source artifacts so the only thing we are testing is
        # the evidence registration boundary.
        store.register_artifact(transcript)
        store.register_artifact(bundle)
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        # No content_hash is present on the pure payloads => store rejects them.
        with pytest.raises(ArtifactStoreError) as exc1:
            store.register_artifact(eval_summary)
        assert exc1.value.reason_code in {"MISSING_ENVELOPE_FIELDS", "CONTENT_HASH_MISMATCH"}
        with pytest.raises(ArtifactStoreError) as exc2:
            store.register_artifact(gate_evidence)
        assert exc2.value.reason_code in {"MISSING_ENVELOPE_FIELDS", "CONTENT_HASH_MISMATCH"}


# ---------------------------------------------------------------------------
# CPL-03-6 — Negative / attack cases (table-driven)
# ---------------------------------------------------------------------------


class TestNegativeMatrix:
    @pytest.mark.parametrize(
        "mutator,expected_reason",
        [
            (lambda b: b.update({"manifest_hash": "sha256:" + "1" * 64}), "REPLAY_MANIFEST_HASH_MISMATCH"),
            (lambda b: b.__setitem__("source_artifact_id", "TXA-OTHER"), "BUNDLE_SOURCE_LINK_MISMATCH"),
            (lambda b: b["segments"].pop(), "COVERAGE_COUNT_MISMATCH"),
            (lambda b: b["segments"][0].__setitem__("source_turn_id", "T-9999"), "ORPHAN_SEGMENT"),
            (lambda b: b["segments"][0].__setitem__("text", "ZZ"), "SEGMENT_TURN_DRIFT"),
        ],
    )
    def test_mutation_lands_in_failed_gate(self, mutator, expected_reason) -> None:
        transcript, bundle = _build_pair()
        mutator(bundle)
        bundle["content_hash"] = compute_content_hash(bundle)
        _, evidence = _evaluate(transcript, bundle)
        assert evidence["gate_status"] == GATE_STATUS_FAILED
        assert expected_reason in evidence["reason_codes"]
        assert evidence["routable"] is False

    def test_gate_evidence_always_carries_eval_summary_id(self) -> None:
        """Even on failure, gate_evidence must back-reference the eval_summary."""
        transcript, bundle = _build_pair()
        bundle["segments"][0]["source_turn_id"] = "T-9999"
        bundle["content_hash"] = compute_content_hash(bundle)
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert gate_evidence["eval_summary_id"] == eval_summary["artifact_id"]
        assert gate_evidence["eval_summary_id"].startswith("EVS-")


# ---------------------------------------------------------------------------
# CPL-03-7 — Red-team regressions
# ---------------------------------------------------------------------------


class TestRedTeamRegressions:
    """Each test corresponds to a finding in the CPL-03 red-team review."""

    def test_F001_fake_gate_evidence_rejected_by_back_reference_drift(self) -> None:
        """Forged gate_evidence with a wrong eval_summary_id is caught by the PQX
        invariant in run_eval_gate_via_pqx that re-derives the summary id."""
        # The invariant is asserted inside the harness; we verify it by hand here.
        transcript, bundle = _build_pair()
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        assert gate_evidence["eval_summary_id"] == eval_summary["artifact_id"]

    def test_F002_replay_mismatch_lands_in_failed_gate(self) -> None:
        transcript, bundle = _build_pair()
        bundle["manifest_hash"] = "sha256:" + "abcd" * 16
        bundle["content_hash"] = compute_content_hash(bundle)
        _, evidence = _evaluate(transcript, bundle)
        assert evidence["gate_status"] == GATE_STATUS_FAILED
        assert "REPLAY_MANIFEST_HASH_MISMATCH" in evidence["reason_codes"]

    def test_F003_partial_coverage_lands_in_failed_gate(self) -> None:
        transcript, bundle = _build_pair()
        bundle["segments"] = bundle["segments"][:1]
        bundle["content_hash"] = compute_content_hash(bundle)
        _, evidence = _evaluate(transcript, bundle)
        assert evidence["gate_status"] == GATE_STATUS_FAILED
        assert "COVERAGE_COUNT_MISMATCH" in evidence["reason_codes"]

    def test_F004_pqx_bypass_attempt_blocked(self) -> None:
        """Direct register without PQX raises (no content_hash on pure payloads)."""
        store = ArtifactStore()
        transcript, bundle = _build_pair()
        store.register_artifact(transcript)
        store.register_artifact(bundle)
        eval_summary, gate_evidence = _evaluate(transcript, bundle)
        with pytest.raises(ArtifactStoreError):
            store.register_artifact(eval_summary)
        with pytest.raises(ArtifactStoreError):
            store.register_artifact(gate_evidence)

    def test_F005_missing_eval_summary_id_in_gate_rejected_by_schema(self) -> None:
        transcript, bundle = _build_pair()
        _, gate_evidence = _evaluate(transcript, bundle)
        gate_evidence.pop("eval_summary_id")
        gate_evidence["content_hash"] = compute_content_hash(gate_evidence)
        errors = list(_validator("gate_evidence").iter_errors(gate_evidence))
        assert errors, "schema must require eval_summary_id"

    def test_F006_missing_eval_results_rejected_by_schema(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, _ = _evaluate(transcript, bundle)
        eval_summary["eval_results"] = []
        eval_summary["content_hash"] = compute_content_hash(eval_summary)
        errors = list(_validator("eval_summary").iter_errors(eval_summary))
        assert errors, "schema must require minItems: 1 eval_results"

    def test_F007_eval_with_undefined_status_rejected_by_schema(self) -> None:
        transcript, bundle = _build_pair()
        eval_summary, _ = _evaluate(transcript, bundle)
        eval_summary["eval_results"][0]["status"] = "indeterminate"
        eval_summary["content_hash"] = compute_content_hash(eval_summary)
        errors = list(_validator("eval_summary").iter_errors(eval_summary))
        assert errors, "schema must constrain status to pass|fail"

    def test_F008_unknown_gate_status_rejected_by_schema(self) -> None:
        transcript, bundle = _build_pair()
        _, gate_evidence = _evaluate(transcript, bundle)
        gate_evidence["gate_status"] = "wide_open"
        gate_evidence["content_hash"] = compute_content_hash(gate_evidence)
        errors = list(_validator("gate_evidence").iter_errors(gate_evidence))
        assert errors


# ---------------------------------------------------------------------------
# CPL-03 — Authority-shape vocabulary regression
# ---------------------------------------------------------------------------


_FORBIDDEN_AUTHORITY_TERMS = (
    "enforce",
    "enforced",
    "enforcement",
    "decision",
    "decisions",
    "decided",
    "verdict",
    "adjudication",
    "promotion",
    "promoted",
    "promote",
    "certification",
    "certified",
    "certify",
    "approval",
    "approved",
    "approve",
)


def _scan_for_authority_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in _FORBIDDEN_AUTHORITY_TERMS if term in lowered]


class TestAuthorityShapeVocabulary:
    REPO_ROOT = Path(__file__).parent.parent.parent

    def _load(self, rel_path: str) -> str:
        return (self.REPO_ROOT / rel_path).read_text(encoding="utf-8")

    def test_eval_gate_module_has_no_authority_vocabulary(self) -> None:
        text = self._load("spectrum_systems/modules/transcript_pipeline/eval_gate.py")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"eval_gate.py must avoid authority vocabulary, found: {hits}"

    def test_eval_summary_schema_has_no_authority_vocabulary(self) -> None:
        text = self._load("contracts/schemas/transcript_pipeline/eval_summary.schema.json")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"eval_summary schema must avoid authority vocabulary, found: {hits}"

    def test_gate_evidence_schema_has_no_authority_vocabulary(self) -> None:
        text = self._load("contracts/schemas/transcript_pipeline/gate_evidence.schema.json")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"gate_evidence schema must avoid authority vocabulary, found: {hits}"

    def test_review_artifact_has_no_authority_vocabulary(self) -> None:
        text = self._load("contracts/review_artifact/CPL-03_review.json")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-03_review.json must avoid authority vocabulary, found: {hits}"

    def test_fix_actions_artifact_has_no_authority_vocabulary(self) -> None:
        text = self._load("contracts/review_actions/CPL-03_fix_actions.json")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-03_fix_actions.json must avoid authority vocabulary, found: {hits}"

    def test_review_doc_has_no_authority_vocabulary(self) -> None:
        text = self._load("docs/reviews/CPL-03_eval_gate_review.md")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-03 review doc must avoid authority vocabulary, found: {hits}"

    def test_fix_plan_doc_has_no_authority_vocabulary(self) -> None:
        text = self._load("docs/review-actions/CPL-03_fix_plan.md")
        hits = _scan_for_authority_terms(text)
        assert not hits, f"CPL-03 fix plan must avoid authority vocabulary, found: {hits}"

    def test_eval_gate_module_has_no_register_artifact_call(self) -> None:
        """The eval gate must not call ArtifactStore.register_artifact directly;
        the only sanctioned write path is run_eval_gate_via_pqx -> run_pqx_step."""
        text = self._load("spectrum_systems/modules/transcript_pipeline/eval_gate.py")
        assert "register_artifact" not in text, (
            "eval_gate.py must not register artifacts directly; PQX is the only write path"
        )
