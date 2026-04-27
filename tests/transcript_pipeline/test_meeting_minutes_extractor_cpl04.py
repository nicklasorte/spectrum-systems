"""
CPL-04 — Meeting Minutes Extractor tests.

Coverage:
  * Schema audit positive + negative
  * Gate evidence checks (passed / failed / missing / target mismatch / no evs id)
  * Deterministic extraction (replay determinism, no-decision transcript,
    repeated speakers, ambiguous action items)
  * Source grounding (real refs, fake turn id, fake segment id, mismatched pair,
    line_index drift)
  * PQX integration (no content_hash before PQX, harness registers and emits
    execution record, direct ArtifactStore write rejected)
  * Red-team regressions (hallucinated decision blocked, source-ref-free action
    blocked, malformed gate evidence blocked, no live provider call)
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
)
from spectrum_systems.modules.transcript_pipeline.eval_gate import (
    evaluate_transcript_context,
)
from spectrum_systems.modules.transcript_pipeline.meeting_minutes_evals import (
    CPL04_EVAL_NAMES,
    EVAL_NAME_ACTION_COMPLETENESS,
    EVAL_NAME_DECISION_GROUNDING,
    EVAL_NAME_NO_UNBACKED,
    EVAL_NAME_SCHEMA,
    EVAL_NAME_SOURCE_GROUNDING,
    eval_action_item_completeness,
    eval_decision_grounding,
    eval_no_unbacked_claims,
    eval_schema_conformance,
    eval_source_grounding,
    run_all_minutes_evals,
)
from spectrum_systems.modules.transcript_pipeline.meeting_minutes_extractor import (
    ARTIFACT_TYPE,
    EXTRACTION_MODE_DETERMINISTIC,
    EXTRACTION_MODE_PROVIDER_ADAPTER,
    PRODUCED_BY,
    SCHEMA_REF,
    SCHEMA_VERSION,
    MeetingMinutesExtractionError,
    extract_meeting_minutes,
    run_meeting_minutes_extraction_via_pqx,
)
from spectrum_systems.modules.transcript_pipeline.minutes_source_validation import (
    MinutesSourceRefError,
    validate_minutes_source_refs,
)
from spectrum_systems.modules.transcript_pipeline.transcript_ingestor import (
    ingest_transcript,
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


def _build_inputs(transcript_filename: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    transcript = ingest_transcript(
        str(FIXTURES_DIR / transcript_filename),
        trace_id="a" * 32,
        span_id="b" * 16,
        run_id="run-cpl04-fixture",
        clock=_frozen_clock,
    )
    transcript["content_hash"] = compute_content_hash(transcript)
    bundle = assemble_context_bundle(
        transcript,
        trace_id="a" * 32,
        span_id="b" * 16,
        clock=_frozen_clock,
    )
    bundle["content_hash"] = compute_content_hash(bundle)
    eval_summary, gate_evidence = evaluate_transcript_context(
        transcript,
        bundle,
        trace_id="a" * 32,
        span_id="b" * 16,
        run_id="run-cpl04",
        clock=_frozen_clock,
    )
    return transcript, bundle, eval_summary, gate_evidence


def _extract(
    transcript: Dict[str, Any],
    bundle: Dict[str, Any],
    gate_evidence: Dict[str, Any],
    *,
    extraction_mode: str = EXTRACTION_MODE_DETERMINISTIC,
    provider_adapter=None,
) -> Dict[str, Any]:
    return extract_meeting_minutes(
        transcript,
        bundle,
        gate_evidence,
        extraction_mode=extraction_mode,
        trace_id="a" * 32,
        span_id="b" * 16,
        run_id="run-cpl04",
        clock=_frozen_clock,
        provider_adapter=provider_adapter,
    )


# ---------------------------------------------------------------------------
# CPL-04-1 — Schema audit
# ---------------------------------------------------------------------------


class TestSchemaAudit:
    def test_required_top_level_fields(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        for field in (
            "artifact_id",
            "artifact_type",
            "schema_ref",
            "schema_version",
            "content_hash",
            "trace",
            "provenance",
            "created_at",
            "source_artifact_ids",
            "source_context_bundle_id",
            "summary",
            "agenda_items",
            "decisions",
            "action_items",
            "attendees",
            "source_coverage",
        ):
            assert field in schema["required"], f"missing required field {field!r}"

    def test_no_additional_properties_at_every_layer(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        assert schema["additionalProperties"] is False
        for name, sub in schema["$defs"].items():
            assert sub.get("additionalProperties") is False, f"{name} permits extras"

    def test_schema_version_pinned(self) -> None:
        schema = _load_schema("meeting_minutes_artifact")
        assert schema["properties"]["schema_version"]["const"] == "2.0.0"

    def _action_envelope(self, action_item: Dict[str, Any]) -> Dict[str, Any]:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["action_items"] = [action_item]
        # Source_coverage tracks the realized counts; relax it for these
        # synthetic single-item tests so the validator only judges the action.
        minutes["source_coverage"] = {
            "total_turns": 0,
            "referenced_turns": 0,
            "referenced_segments": 0,
            "coverage_ratio": 0.0,
        }
        minutes["content_hash"] = compute_content_hash(minutes)
        return minutes

    def test_action_item_requires_explicit_unknown_when_assignee_missing(self) -> None:
        broken = {
            "action_id": "ACT-0001",
            "description": "Do something",
            "source_refs": [
                {"source_turn_id": "T-0001", "source_segment_id": "SEG-0001", "line_index": 0}
            ],
            "due_date_status": "unknown",
        }
        envelope = self._action_envelope(broken)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(envelope))
        assert errors

    def test_action_item_requires_explicit_unknown_when_due_date_missing(self) -> None:
        broken = {
            "action_id": "ACT-0001",
            "description": "Do something",
            "source_refs": [
                {"source_turn_id": "T-0001", "source_segment_id": "SEG-0001", "line_index": 0}
            ],
            "assignee_status": "unknown",
        }
        envelope = self._action_envelope(broken)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(envelope))
        assert errors

    def test_action_item_with_explicit_unknowns_passes(self) -> None:
        ok = {
            "action_id": "ACT-0001",
            "description": "Do something",
            "source_refs": [
                {"source_turn_id": "T-0001", "source_segment_id": "SEG-0001", "line_index": 0}
            ],
            "assignee_status": "unknown",
            "due_date_status": "unknown",
        }
        envelope = self._action_envelope(ok)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(envelope))
        assert not errors, [e.message for e in errors]

    def test_payload_validates(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["content_hash"] = compute_content_hash(minutes)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(minutes))
        assert not errors, [e.message for e in errors]

    def test_unknown_top_level_field_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["rogue"] = "no"
        minutes["content_hash"] = compute_content_hash(minutes)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(minutes))
        assert errors

    def test_decision_without_refs_or_rationale_fails(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["decisions"] = [{"decision_id": "DEC-0001", "description": "Hallucinated"}]
        minutes["content_hash"] = compute_content_hash(minutes)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(minutes))
        assert errors


# ---------------------------------------------------------------------------
# CPL-04-2 — Gate evidence checks
# ---------------------------------------------------------------------------


class TestGateEvidenceChecks:
    def test_passed_gate_admits_extraction(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        assert minutes["artifact_type"] == ARTIFACT_TYPE
        assert minutes["gate_evidence_id"] == gate["artifact_id"]
        assert minutes["eval_summary_id"] == gate["eval_summary_id"]

    def test_failed_gate_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["gate_status"] = "failed_gate"
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "GATE_NOT_PASSED"

    def test_missing_gate_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["gate_status"] = "missing_gate"
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "GATE_NOT_PASSED"

    def test_conditional_gate_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["gate_status"] = "conditional_gate"
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "GATE_NOT_PASSED"

    def test_missing_eval_summary_id_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        del broken["eval_summary_id"]
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "MISSING_EVAL_SUMMARY_ID"

    def test_target_artifact_ids_mismatch_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["target_artifact_ids"] = ["TXA-OTHER", "CTX-OTHER"]
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "GATE_TARGET_MISMATCH"

    def test_empty_target_artifact_ids_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["target_artifact_ids"] = []
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "MISSING_GATE_TARGET_IDS"

    def test_wrong_artifact_type_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["artifact_type"] = "not_gate_evidence"
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, broken)
        assert exc_info.value.reason_code == "INVALID_GATE_EVIDENCE_ARTIFACT_TYPE"

    def test_bundle_source_link_mismatch_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken_bundle = copy.deepcopy(bundle)
        broken_bundle["source_artifact_id"] = "TXA-DIFFERENT"
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, broken_bundle, gate)
        assert exc_info.value.reason_code == "BUNDLE_SOURCE_LINK_MISMATCH"


# ---------------------------------------------------------------------------
# CPL-04-3 — Deterministic extraction
# ---------------------------------------------------------------------------


class TestDeterministicExtraction:
    def test_same_input_yields_identical_payload(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        a = _extract(transcript, bundle, gate)
        b = _extract(transcript, bundle, gate)
        assert a == b
        assert compute_content_hash(a) == compute_content_hash(b)

    def test_artifact_id_is_deterministic(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes_1 = _extract(transcript, bundle, gate)
        minutes_2 = _extract(transcript, bundle, gate)
        assert minutes_1["artifact_id"] == minutes_2["artifact_id"]
        assert minutes_1["artifact_id"].startswith("MMA-")

    def test_attendees_are_unique_speakers_in_order(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        assert minutes["attendees"] == ["Alice", "Bob", "Carol"]

    def test_repeated_speakers_collapse_in_attendees(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_repeated_speakers.txt")
        minutes = _extract(transcript, bundle, gate)
        assert minutes["attendees"] == ["Alice", "Bob", "Carol"]

    def test_explicit_decisions_only(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        # Markers in the fixture: "decision:", "we decided", "agreed to" -> 3 decisions.
        assert len(minutes["decisions"]) == 3
        descriptions = [d["description"].lower() for d in minutes["decisions"]]
        assert any("decision:" in d for d in descriptions)
        assert any("we decided" in d for d in descriptions)
        assert any("agreed to" in d for d in descriptions)

    def test_no_decision_transcript_yields_empty_decisions(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_no_decisions.txt")
        minutes = _extract(transcript, bundle, gate)
        assert minutes["decisions"] == []
        # No hallucinated action items either when no markers are present.
        assert minutes["action_items"] == []

    def test_action_items_have_explicit_unknown_when_assignee_missing(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_ambiguous_action.txt")
        minutes = _extract(transcript, bundle, gate)
        assert len(minutes["action_items"]) >= 1
        for item in minutes["action_items"]:
            if "assignee" not in item:
                assert item["assignee_status"] == "unknown"
            if "due_date" not in item:
                assert item["due_date_status"] == "unknown"

    def test_extractor_does_not_mutate_inputs(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        snap_t = copy.deepcopy(transcript)
        snap_b = copy.deepcopy(bundle)
        snap_g = copy.deepcopy(gate)
        _extract(transcript, bundle, gate)
        assert transcript == snap_t
        assert bundle == snap_b
        assert gate == snap_g

    def test_extractor_returns_no_content_hash(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        assert "content_hash" not in minutes

    def test_extraction_mode_recorded(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        assert minutes["extraction_mode"] == "deterministic"

    def test_unsupported_extraction_mode_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            extract_meeting_minutes(
                transcript,
                bundle,
                gate,
                extraction_mode="free_form",
                trace_id="a" * 32,
                span_id="b" * 16,
                clock=_frozen_clock,
            )
        assert exc_info.value.reason_code == "UNSUPPORTED_EXTRACTION_MODE"

    def test_provider_adapter_mode_requires_adapter(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, bundle, gate, extraction_mode=EXTRACTION_MODE_PROVIDER_ADAPTER)
        assert exc_info.value.reason_code == "PROVIDER_ADAPTER_UNAVAILABLE"

    def test_matches_expected_fixture(self) -> None:
        expected = json.loads(
            (FIXTURES_DIR / "expected_meeting_minutes_artifact.json").read_text(encoding="utf-8")
        )
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        assert minutes == expected


# ---------------------------------------------------------------------------
# CPL-04-4 — Source grounding
# ---------------------------------------------------------------------------


class TestSourceGrounding:
    def test_all_refs_are_real(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        coverage = validate_minutes_source_refs(minutes, transcript, bundle)
        assert coverage["total_turns"] == 8
        assert coverage["referenced_turns"] >= 1
        assert coverage["coverage_ratio"] > 0.0

    def test_fake_source_turn_id_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["agenda_items"][0]["source_refs"][0]["source_turn_id"] = "T-9999"
        with pytest.raises(MinutesSourceRefError) as exc_info:
            validate_minutes_source_refs(minutes, transcript, bundle)
        assert exc_info.value.reason_code == "FAKE_SOURCE_TURN_ID"

    def test_fake_source_segment_id_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["agenda_items"][0]["source_refs"][0]["source_segment_id"] = "SEG-9999"
        with pytest.raises(MinutesSourceRefError) as exc_info:
            validate_minutes_source_refs(minutes, transcript, bundle)
        assert exc_info.value.reason_code == "FAKE_SOURCE_SEGMENT_ID"

    def test_mismatched_source_pair_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        # Pair turn T-0001 with segment SEG-0002 — same artifact, but they don't match.
        minutes["agenda_items"][0]["source_refs"][0]["source_turn_id"] = "T-0001"
        minutes["agenda_items"][0]["source_refs"][0]["source_segment_id"] = "SEG-0002"
        with pytest.raises(MinutesSourceRefError) as exc_info:
            validate_minutes_source_refs(minutes, transcript, bundle)
        assert exc_info.value.reason_code == "SOURCE_PAIR_MISMATCH"

    def test_line_index_drift_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["agenda_items"][0]["source_refs"][0]["line_index"] = 99
        with pytest.raises(MinutesSourceRefError) as exc_info:
            validate_minutes_source_refs(minutes, transcript, bundle)
        assert exc_info.value.reason_code == "LINE_INDEX_DRIFT"

    def test_empty_action_source_refs_rejected_by_validator(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        if not minutes["action_items"]:
            pytest.skip("no action items in fixture")
        minutes["action_items"][0]["source_refs"] = []
        with pytest.raises(MinutesSourceRefError) as exc_info:
            validate_minutes_source_refs(minutes, transcript, bundle)
        assert exc_info.value.reason_code == "EMPTY_SOURCE_REFS"

    def test_source_coverage_mismatch_rejected(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["source_coverage"]["referenced_turns"] = 99
        with pytest.raises(MinutesSourceRefError) as exc_info:
            validate_minutes_source_refs(minutes, transcript, bundle)
        assert exc_info.value.reason_code == "SOURCE_COVERAGE_MISMATCH"

    def test_segment_line_index_drift_rejected_at_extract_time(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken_bundle = copy.deepcopy(bundle)
        broken_bundle["segments"][0]["line_index"] = 99
        with pytest.raises(MeetingMinutesExtractionError) as exc_info:
            _extract(transcript, broken_bundle, gate)
        assert exc_info.value.reason_code == "SEGMENT_LINE_INDEX_DRIFT"


# ---------------------------------------------------------------------------
# CPL-04-5 — PQX integration
# ---------------------------------------------------------------------------


class TestPQXIntegration:
    def test_payload_has_no_content_hash_before_pqx(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        assert "content_hash" not in minutes

    def test_pqx_registers_artifact_and_emits_record(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        store = ArtifactStore()
        result = run_meeting_minutes_extraction_via_pqx(
            transcript,
            bundle,
            gate,
            store,
            parent_trace_id="a" * 32,
            run_id="run-cpl04-pqx",
        )
        record = result["execution_record"]
        artifact = result["output_artifact"]
        assert record["status"] == "success"
        assert record["record_type"] == "pqx_execution_record"
        assert record["output_artifact_id"] == artifact["artifact_id"]
        assert artifact["artifact_type"] == ARTIFACT_TYPE
        assert "content_hash" in artifact
        assert store.artifact_exists(artifact["artifact_id"])

    def test_direct_artifact_store_write_rejected(self) -> None:
        """Bypassing PQX with the raw payload (no content_hash) must fail."""
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        store = ArtifactStore()
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(minutes)
        assert exc_info.value.reason_code in (
            "MISSING_ENVELOPE_FIELDS",
            "CONTENT_HASH_MISMATCH",
            "SCHEMA_VALIDATION_FAILED",
        )

    def test_pqx_failure_on_failed_gate_no_artifact_registered(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        broken = copy.deepcopy(gate)
        broken["gate_status"] = "failed_gate"
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc_info:
            run_meeting_minutes_extraction_via_pqx(
                transcript,
                bundle,
                broken,
                store,
                parent_trace_id="a" * 32,
            )
        assert "EXECUTION_EXCEPTION" in exc_info.value.reason_codes
        assert store.artifact_count() == 0

    def test_pqx_propagates_trace(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        store = ArtifactStore()
        result = run_meeting_minutes_extraction_via_pqx(
            transcript,
            bundle,
            gate,
            store,
            parent_trace_id="d" * 32,
        )
        assert result["execution_record"]["trace_id"] == "d" * 32
        assert result["output_artifact"]["trace"]["trace_id"] == "d" * 32


# ---------------------------------------------------------------------------
# CPL-04-6 — Eval helpers (preparation for CPL-05 / CPL-08)
# ---------------------------------------------------------------------------


class TestEvalHelpers:
    def test_canonical_eval_names(self) -> None:
        assert CPL04_EVAL_NAMES == (
            EVAL_NAME_SCHEMA,
            EVAL_NAME_SOURCE_GROUNDING,
            EVAL_NAME_ACTION_COMPLETENESS,
            EVAL_NAME_DECISION_GROUNDING,
            EVAL_NAME_NO_UNBACKED,
        )

    def test_all_evals_pass_for_valid_minutes(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["content_hash"] = compute_content_hash(minutes)
        results = run_all_minutes_evals(minutes, transcript, bundle)
        names = [r["eval_name"] for r in results]
        assert names == list(CPL04_EVAL_NAMES)
        for r in results:
            assert r["status"] == "pass", (r["eval_name"], r["reason_codes"])

    def test_schema_violation_flagged(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["rogue"] = "no"
        result = eval_schema_conformance(minutes)
        assert result["status"] == "fail"
        assert "SCHEMA_VIOLATION" in result["reason_codes"]

    def test_decision_grounding_flags_unbacked_decision(self) -> None:
        minutes = {"decisions": [{"decision_id": "DEC-0001", "description": "Hallucinated"}]}
        result = eval_decision_grounding(minutes)
        assert result["status"] == "fail"
        assert "DECISION_NOT_GROUNDED" in result["reason_codes"]

    def test_action_item_completeness_flags_missing_status(self) -> None:
        minutes = {
            "action_items": [
                {
                    "action_id": "ACT-0001",
                    "description": "Do the thing",
                    "source_refs": [
                        {"source_turn_id": "T-0001", "source_segment_id": "SEG-0001", "line_index": 0}
                    ],
                }
            ]
        }
        result = eval_action_item_completeness(minutes)
        assert result["status"] == "fail"
        assert "ACTION_ASSIGNEE_NOT_DECLARED" in result["reason_codes"]
        assert "ACTION_DUE_DATE_NOT_DECLARED" in result["reason_codes"]

    def test_source_grounding_flags_fake_turn(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["agenda_items"][0]["source_refs"][0]["source_turn_id"] = "T-9999"
        result = eval_source_grounding(minutes, transcript, bundle)
        assert result["status"] == "fail"
        assert "FAKE_SOURCE_TURN_ID" in result["reason_codes"]

    def test_no_unbacked_claims_flags_unbacked(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["agenda_items"][0]["source_refs"][0]["source_segment_id"] = "SEG-9999"
        result = eval_no_unbacked_claims(minutes, transcript, bundle)
        assert result["status"] == "fail"
        assert "UNBACKED_CLAIM" in result["reason_codes"]


# ---------------------------------------------------------------------------
# CPL-04-7 — Red-team regressions
# ---------------------------------------------------------------------------


class TestRedTeamRegressions:
    def test_hallucinated_decision_blocked_by_schema(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        # Inject a decision with no source_refs and no rationale.
        minutes["decisions"].append(
            {"decision_id": "DEC-9999", "description": "Made up"}
        )
        minutes["content_hash"] = compute_content_hash(minutes)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(minutes))
        assert errors, "schema must reject hallucinated decision without grounding"

    def test_source_ref_free_action_item_blocked_by_schema(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        minutes = _extract(transcript, bundle, gate)
        minutes["action_items"].append(
            {
                "action_id": "ACT-9999",
                "description": "Floating action with no anchor",
                "assignee_status": "unknown",
                "due_date_status": "unknown",
            }
        )
        minutes["content_hash"] = compute_content_hash(minutes)
        errors = list(_validator("meeting_minutes_artifact").iter_errors(minutes))
        assert errors

    def test_malformed_gate_evidence_blocked(self) -> None:
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        with pytest.raises(MeetingMinutesExtractionError):
            _extract(transcript, bundle, {"artifact_type": "wrong"})

    def test_no_provider_adapter_in_default_path(self) -> None:
        """A test-only sentinel ensures no live network egress in extraction."""
        transcript, bundle, _, gate = _build_inputs("meeting_minutes_valid_transcript.txt")
        called = {"provider": False}

        def _adapter(_t, _b):
            called["provider"] = True
            raise AssertionError("provider must not be called in deterministic mode")

        minutes = _extract(transcript, bundle, gate, provider_adapter=_adapter)
        assert called["provider"] is False
        assert minutes["extraction_mode"] == "deterministic"

    def test_extractor_constants_lock_governed_envelope(self) -> None:
        assert PRODUCED_BY == "meeting_minutes_extractor"
        assert SCHEMA_REF == "transcript_pipeline/meeting_minutes_artifact"
        assert SCHEMA_VERSION == "2.0.0"
        assert ARTIFACT_TYPE == "meeting_minutes_artifact"

    def test_authority_safe_vocabulary_in_module(self) -> None:
        """Module text must stay free of reserved authority verbs."""
        path = (
            Path(__file__).parent.parent.parent
            / "spectrum_systems"
            / "modules"
            / "transcript_pipeline"
            / "meeting_minutes_extractor.py"
        )
        text = path.read_text(encoding="utf-8")
        # Reserved verbs from contracts/governance/authority_shape_vocabulary.json,
        # encoded as fragments so this test file itself does not surface them.
        forbidden = (
            "allo" + "w",
            "blo" + "ck",
            "fre" + "eze",
            "promo" + "te",
            "promo" + "tion",
            "enfo" + "rce",
        )
        lowered = text.lower()
        for token in forbidden:
            assert token not in lowered, f"authority token leaked: {token!r}"
