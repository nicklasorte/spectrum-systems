"""
H08 — Transcript Ingestion (governed, fail-closed) tests.

Coverage:
  * schema audit (positive + negative for new session_id / speaker_turns fields)
  * deterministic parser
  * PQX harness integration (artifact registered, record emitted, trace propagated)
  * artifact store invariants (schema, hash, trace, provenance, duplicate id)
  * bad-input campaign (empty, malformed, missing file, oversize, non-utf8,
    duplicates normalized to a valid artifact)
  * red-team regression tests (S2+ findings closed)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from spectrum_systems.modules.orchestration.pqx_step_harness import (
    PQXExecutionError,
    run_pqx_step,
)
from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)
from spectrum_systems.modules.transcript_pipeline.transcript_ingestor import (
    ARTIFACT_TYPE,
    SCHEMA_REF,
    TranscriptIngestionError,
    ingest_transcript,
    ingest_transcript_via_pqx,
    parse_transcript_text,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "contracts"
    / "schemas"
    / "transcript_pipeline"
    / "transcript_artifact.schema.json"
)


def _load_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def _trace() -> Dict[str, str]:
    return {
        "trace_id": uuid.uuid4().hex,
        "span_id": uuid.uuid4().hex[:16],
    }


# ---------------------------------------------------------------------------
# H08-1 — Schema audit (positive + negative for new fields)
# ---------------------------------------------------------------------------


class TestSchemaAudit:
    """Schema must support session_id + speaker_turns and reject malformed input."""

    def test_schema_declares_session_id_and_speaker_turns(self) -> None:
        schema = _load_schema()
        props = schema["properties"]
        assert "session_id" in props, "schema missing session_id"
        assert "speaker_turns" in props, "schema missing speaker_turns"
        assert props["speaker_turns"]["type"] == "array"
        assert "speaker_turn" in schema["$defs"]

    def test_schema_rejects_unknown_fields(self) -> None:
        schema = _load_schema()
        assert schema.get("additionalProperties") is False

    def test_speaker_turn_requires_turn_id_speaker_text(self) -> None:
        schema = _load_schema()
        required = schema["$defs"]["speaker_turn"]["required"]
        for field in ("turn_id", "speaker", "text"):
            assert field in required

    def test_payload_with_speaker_turns_validates(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        payload["content_hash"] = compute_content_hash(payload)
        errors = list(_validator().iter_errors(payload))
        assert not errors, f"valid payload failed schema: {[e.message for e in errors]}"

    def test_speaker_turn_with_unknown_field_rejected(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        payload["speaker_turns"][0]["rogue"] = "no"
        payload["content_hash"] = compute_content_hash(payload)
        with pytest.raises(ValidationError):
            v = _validator()
            errors = list(v.iter_errors(payload))
            if errors:
                raise ValidationError(errors[0].message)

    def test_invalid_session_id_pattern_rejected(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        payload["session_id"] = "not-a-session"
        payload["content_hash"] = compute_content_hash(payload)
        errors = list(_validator().iter_errors(payload))
        assert errors, "schema should reject malformed session_id"

    def test_empty_speaker_turns_rejected(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        payload["speaker_turns"] = []
        payload["content_hash"] = compute_content_hash(payload)
        errors = list(_validator().iter_errors(payload))
        assert errors, "schema should reject empty speaker_turns array"


# ---------------------------------------------------------------------------
# H08-3 — Deterministic parser
# ---------------------------------------------------------------------------


class TestParserDeterminism:
    def test_valid_transcript_parses_to_speaker_turns(self) -> None:
        text = (FIXTURES_DIR / "valid_transcript.txt").read_text(encoding="utf-8")
        turns = parse_transcript_text(text)
        assert len(turns) == 9
        assert {t["speaker"] for t in turns} == {"Alice", "Bob", "Carol"}
        assert turns[0]["turn_id"] == "T-0001"
        assert turns[-1]["turn_id"] == f"T-{len(turns):04d}"

    def test_parsing_is_deterministic(self) -> None:
        text = (FIXTURES_DIR / "valid_transcript.txt").read_text(encoding="utf-8")
        a = parse_transcript_text(text)
        b = parse_transcript_text(text)
        assert a == b

    def test_empty_text_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            parse_transcript_text("")
        assert exc.value.reason_code == "EMPTY_TRANSCRIPT"

    def test_whitespace_only_text_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            parse_transcript_text("   \n\n\t  \n")
        assert exc.value.reason_code == "EMPTY_TRANSCRIPT"

    def test_no_speaker_turns_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            parse_transcript_text("just prose with no speakers\nanother line")
        assert exc.value.reason_code == "NO_SPEAKER_TURNS"

    def test_non_string_input_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            parse_transcript_text(b"bytes")  # type: ignore[arg-type]
        assert exc.value.reason_code == "INVALID_INPUT_TYPE"


# ---------------------------------------------------------------------------
# H08-3 — ingest_transcript() payload shape
# ---------------------------------------------------------------------------


class TestIngestPayload:
    def test_valid_file_produces_full_payload(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
            run_id="run-test-h08",
        )
        assert payload["artifact_type"] == ARTIFACT_TYPE
        assert payload["schema_ref"] == SCHEMA_REF
        assert payload["session_id"].startswith("SES-")
        assert payload["artifact_id"].startswith("TXA-")
        assert payload["provenance"]["produced_by"] == "transcript_ingestor"
        assert payload["provenance"]["run_id"] == "run-test-h08"
        assert "content_hash" not in payload, "ingestor must not compute content_hash"

    def test_payload_is_deterministic_modulo_trace_and_time(self) -> None:
        a = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        b = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="c" * 32,
            span_id="d" * 16,
        )
        a_hash = compute_content_hash(a)
        b_hash = compute_content_hash(b)
        assert a_hash == b_hash

    def test_invalid_trace_id_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(FIXTURES_DIR / "valid_transcript.txt"),
                trace_id="too-short",
                span_id="b" * 16,
            )
        assert exc.value.reason_code == "INVALID_TRACE_ID"

    def test_invalid_span_id_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(FIXTURES_DIR / "valid_transcript.txt"),
                trace_id="a" * 32,
                span_id="zzz",
            )
        assert exc.value.reason_code == "INVALID_SPAN_ID"

    def test_unsupported_source_format_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(FIXTURES_DIR / "valid_transcript.txt"),
                trace_id="a" * 32,
                span_id="b" * 16,
                source_format="mp3",
            )
        assert exc.value.reason_code == "INVALID_SOURCE_FORMAT"

    def test_missing_file_fails_closed(self) -> None:
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(FIXTURES_DIR / "does_not_exist.txt"),
                trace_id="a" * 32,
                span_id="b" * 16,
            )
        assert exc.value.reason_code == "INPUT_FILE_NOT_FOUND"

    def test_non_utf8_file_fails_closed(self, tmp_path: Path) -> None:
        bad = tmp_path / "latin.txt"
        bad.write_bytes(b"Alice: caf\xe9\n")
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(bad),
                trace_id="a" * 32,
                span_id="b" * 16,
            )
        assert exc.value.reason_code == "INPUT_NOT_UTF8"


# ---------------------------------------------------------------------------
# H08-4 — PQX harness integration
# ---------------------------------------------------------------------------


class TestPQXIntegration:
    def test_valid_ingestion_via_pqx_registers_artifact(self) -> None:
        store = ArtifactStore()
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
            run_id="run-h08-pqx",
        )
        artifact = result["output_artifact"]
        record = result["execution_record"]
        assert artifact["artifact_type"] == ARTIFACT_TYPE
        assert artifact["schema_ref"] == SCHEMA_REF
        assert artifact["trace"]["trace_id"] == record["trace_id"]
        assert record["status"] == "success"
        assert record["step_name"] == "transcript_ingestion"
        assert store.artifact_exists(artifact["artifact_id"])

    def test_pqx_record_includes_trace_and_span(self) -> None:
        store = ArtifactStore()
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
        )
        record = result["execution_record"]
        assert len(record["trace_id"]) == 32
        assert len(record["span_id"]) == 16

    def test_parent_trace_id_propagated_through_pqx(self) -> None:
        store = ArtifactStore()
        parent = "f" * 32
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
            parent_trace_id=parent,
        )
        assert result["execution_record"]["trace_id"] == parent
        assert result["output_artifact"]["trace"]["trace_id"] == parent

    def test_empty_transcript_via_pqx_fails_no_artifact_written(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError) as exc:
            ingest_transcript_via_pqx(
                str(FIXTURES_DIR / "empty_transcript.txt"),
                store,
            )
        assert "EXECUTION_EXCEPTION" in exc.value.reason_codes
        assert store.artifact_count() == 0
        assert exc.value.execution_record["status"] == "failed"

    def test_malformed_transcript_via_pqx_fails_no_artifact_written(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError):
            ingest_transcript_via_pqx(
                str(FIXTURES_DIR / "malformed_transcript.txt"),
                store,
            )
        assert store.artifact_count() == 0

    def test_whitespace_only_via_pqx_fails(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError):
            ingest_transcript_via_pqx(
                str(FIXTURES_DIR / "whitespace_only_transcript.txt"),
                store,
            )
        assert store.artifact_count() == 0

    def test_duplicate_lines_normalized_to_valid_artifact(self) -> None:
        """Duplicate raw lines are preserved as ordered turns; ingestion still passes."""
        store = ArtifactStore()
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "duplicate_lines_transcript.txt"),
            store,
        )
        artifact = result["output_artifact"]
        assert artifact["speaker_count"] == 2  # Alice, Bob
        assert len(artifact["speaker_turns"]) == 5  # all preserved, ordered


# ---------------------------------------------------------------------------
# H08-5 — Artifact store invariants
# ---------------------------------------------------------------------------


class TestArtifactStoreInvariants:
    def test_missing_trace_rejected_by_store(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        del payload["trace"]
        payload["content_hash"] = compute_content_hash(payload)
        with pytest.raises(ArtifactStoreError) as exc:
            ArtifactStore().register_artifact(payload)
        assert exc.value.reason_code == "MISSING_ENVELOPE_FIELDS"

    def test_missing_provenance_rejected_by_store(self) -> None:
        payload = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        del payload["provenance"]
        payload["content_hash"] = compute_content_hash(payload)
        with pytest.raises(ArtifactStoreError) as exc:
            ArtifactStore().register_artifact(payload)
        assert exc.value.reason_code == "MISSING_ENVELOPE_FIELDS"

    def test_duplicate_artifact_id_rejected(self) -> None:
        store = ArtifactStore()
        ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
        )
        # Same input file => same deterministic artifact_id; second registration must fail.
        with pytest.raises(PQXExecutionError) as exc:
            ingest_transcript_via_pqx(
                str(FIXTURES_DIR / "valid_transcript.txt"),
                store,
            )
        assert any("DUPLICATE" in rc or "ARTIFACT_STORE" in rc for rc in exc.value.reason_codes)
        assert store.artifact_count() == 1

    def test_content_hash_computed_by_store(self) -> None:
        store = ArtifactStore()
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
        )
        artifact = result["output_artifact"]
        expected = compute_content_hash(artifact)
        assert artifact["content_hash"] == expected

    def test_provenance_records_produced_by(self) -> None:
        store = ArtifactStore()
        result = ingest_transcript_via_pqx(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            store,
        )
        prov = result["output_artifact"]["provenance"]
        assert prov["produced_by"] == "transcript_ingestor"
        assert prov["input_artifact_ids"] == []


# ---------------------------------------------------------------------------
# H08-7 / H08-8 — Red-team regression tests (fixes for review findings)
# ---------------------------------------------------------------------------


class TestRedTeamRegressions:
    """Regression coverage for fixes documented in contracts/review_actions/H08_fix_actions.json."""

    def test_F001_empty_input_cannot_produce_artifact(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError):
            ingest_transcript_via_pqx(
                str(FIXTURES_DIR / "empty_transcript.txt"),
                store,
            )
        assert store.artifact_count() == 0

    def test_F002_malformed_input_cannot_produce_artifact(self) -> None:
        store = ArtifactStore()
        with pytest.raises(PQXExecutionError):
            ingest_transcript_via_pqx(
                str(FIXTURES_DIR / "malformed_transcript.txt"),
                store,
            )
        assert store.artifact_count() == 0

    def test_F003_oversize_input_blocked_before_parse(self, tmp_path: Path) -> None:
        big = tmp_path / "big.txt"
        big.write_bytes(b"Alice: x\n" * (1024 * 1024))  # > 5 MiB
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(big),
                trace_id="a" * 32,
                span_id="b" * 16,
            )
        assert exc.value.reason_code == "INPUT_FILE_TOO_LARGE"

    def test_F004_non_utf8_input_blocked(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.txt"
        bad.write_bytes(b"\xff\xfe\xfa")
        with pytest.raises(TranscriptIngestionError) as exc:
            ingest_transcript(
                str(bad),
                trace_id="a" * 32,
                span_id="b" * 16,
            )
        assert exc.value.reason_code == "INPUT_NOT_UTF8"

    def test_F005_session_id_is_deterministic(self) -> None:
        a = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="a" * 32,
            span_id="b" * 16,
        )
        b = ingest_transcript(
            str(FIXTURES_DIR / "valid_transcript.txt"),
            trace_id="c" * 32,
            span_id="d" * 16,
        )
        assert a["session_id"] == b["session_id"]
        assert a["artifact_id"] == b["artifact_id"]

    def test_F006_direct_artifact_writes_blocked_by_envelope_check(self) -> None:
        """ArtifactStore must reject a hand-crafted artifact missing required envelope fields."""
        bogus = {"artifact_id": "TXA-FAKE", "schema_ref": SCHEMA_REF}
        with pytest.raises(ArtifactStoreError) as exc:
            ArtifactStore().register_artifact(bogus)
        assert exc.value.reason_code == "MISSING_ENVELOPE_FIELDS"
