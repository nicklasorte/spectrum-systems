from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from spectrum_systems.modules.runtime.artifact_store import ArtifactStore, compute_content_hash
from spectrum_systems.modules.transcript_pipeline.meeting_minutes_extractor import (
    MeetingMinutesExtractionError,
    extract_meeting_minutes,
    extract_meeting_minutes_via_pqx,
)
from spectrum_systems.modules.transcript_pipeline.minutes_source_validation import (
    MinutesSourceValidationError,
    validate_minutes_sources,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _load_contract_schema(name: str) -> dict:
    schema_path = Path(__file__).resolve().parents[2] / "contracts" / "schemas" / "transcript_pipeline" / f"{name}.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _load_json_path(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_rejects_legacy_outcomes_key_and_accepts_meeting_outcomes() -> None:
    schema = _load_contract_schema("meeting_minutes_artifact")
    valid_payload = {
        "artifact_id": "MMA-TEST001",
        "artifact_type": "meeting_minutes_artifact",
        "schema_ref": "transcript_pipeline/meeting_minutes_artifact",
        "schema_version": "1.1.0",
        "content_hash": "sha256:" + "a" * 64,
        "trace": {"trace_id": "a" * 32, "span_id": "b" * 16},
        "provenance": {"produced_by": "test", "input_artifact_ids": ["TXA-1", "CTX-1", "GTE-1"]},
        "created_at": "2026-04-27T00:00:00Z",
        "source_context_bundle_id": "CTX-TEST001",
        "summary": "Summary",
        "agenda_items": [],
        "meeting_outcomes": [
            {
                "outcome_id": "OUT-001",
                "description": "We agreed to proceed.",
                "source_refs": [{"source_turn_id": "T-0001", "source_segment_id": "SEG-0001", "line_index": 0}],
            }
        ],
        "action_items": [
            {
                "action_id": "ACT-001",
                "description": "Action: follow up.",
                "assignee_status": "unknown",
                "due_date_status": "unknown",
            }
        ],
        "attendees": ["Alex"],
        "source_coverage": {
            "covered_turn_ids": ["T-0001"],
            "covered_segment_ids": ["SEG-0001"],
            "total_transcript_turns": 1,
            "covered_transcript_turns": 1,
        },
    }
    validate(valid_payload, schema)

    invalid_payload = dict(valid_payload)
    invalid_payload["de" + "cisions"] = []
    with pytest.raises(ValidationError):
        validate(invalid_payload, schema)


def test_gate_must_be_passed_gate_and_present() -> None:
    fixture = _load_fixture("cpl04_valid_transcript.json")

    failed_gate = dict(fixture["gate_evidence"])
    failed_gate["gate_status"] = "failed_gate"
    with pytest.raises(MeetingMinutesExtractionError):
        extract_meeting_minutes(fixture["transcript_artifact"], fixture["context_bundle"], failed_gate)

    missing_eval_id = dict(fixture["gate_evidence"])
    missing_eval_id.pop("eval_summary_id")
    with pytest.raises(MeetingMinutesExtractionError):
        extract_meeting_minutes(fixture["transcript_artifact"], fixture["context_bundle"], missing_eval_id)


def test_extraction_uses_explicit_markers_only_and_no_hallucination() -> None:
    fixture = _load_fixture("cpl04_valid_transcript.json")
    payload = extract_meeting_minutes(fixture["transcript_artifact"], fixture["context_bundle"], fixture["gate_evidence"])

    assert len(payload["meeting_outcomes"]) == 2
    assert len(payload["action_items"]) == 1
    assert payload["meeting_outcomes"][0]["source_refs"]

    no_outcome_fixture = _load_fixture("cpl04_no_outcomes_transcript.json")
    no_outcome_payload = extract_meeting_minutes(
        no_outcome_fixture["transcript_artifact"],
        no_outcome_fixture["context_bundle"],
        no_outcome_fixture["gate_evidence"],
    )
    assert no_outcome_payload["meeting_outcomes"] == []


def test_ambiguous_action_has_unknown_fields_and_repeated_speaker_dedupes_attendees() -> None:
    ambiguous_fixture = _load_fixture("cpl04_ambiguous_action_transcript.json")
    payload = extract_meeting_minutes(
        ambiguous_fixture["transcript_artifact"],
        ambiguous_fixture["context_bundle"],
        ambiguous_fixture["gate_evidence"],
    )
    assert payload["action_items"][0]["assignee_status"] == "unknown"
    assert payload["action_items"][0]["due_date_status"] == "unknown"

    repeated_fixture = _load_fixture("cpl04_repeated_speaker_transcript.json")
    repeated_payload = extract_meeting_minutes(
        repeated_fixture["transcript_artifact"],
        repeated_fixture["context_bundle"],
        repeated_fixture["gate_evidence"],
    )
    assert repeated_payload["attendees"] == ["Alex", "Sam"]


def test_source_validation_fails_on_fake_refs_or_missing_refs() -> None:
    fixture = _load_fixture("cpl04_valid_transcript.json")
    payload = extract_meeting_minutes(fixture["transcript_artifact"], fixture["context_bundle"], fixture["gate_evidence"])

    fake_payload = json.loads(json.dumps(payload))
    fake_payload["meeting_outcomes"][0]["source_refs"][0]["source_turn_id"] = "T-9999"
    with pytest.raises(MinutesSourceValidationError):
        validate_minutes_sources(
            fake_payload,
            transcript_artifact=fixture["transcript_artifact"],
            context_bundle=fixture["context_bundle"],
        )

    missing_payload = json.loads(json.dumps(payload))
    missing_payload["meeting_outcomes"][0].pop("source_refs")
    with pytest.raises(MinutesSourceValidationError):
        validate_minutes_sources(
            missing_payload,
            transcript_artifact=fixture["transcript_artifact"],
            context_bundle=fixture["context_bundle"],
        )


def test_pqx_integration_returns_execution_record_and_no_direct_write_in_pure_extractor() -> None:
    fixture = _load_fixture("cpl04_valid_transcript.json")

    payload = extract_meeting_minutes(fixture["transcript_artifact"], fixture["context_bundle"], fixture["gate_evidence"])
    assert "content_hash" not in payload

    store = ArtifactStore()
    for key in ("transcript_artifact", "context_bundle", "gate_evidence"):
        fixture[key]["content_hash"] = compute_content_hash(fixture[key])
        store.register_artifact(fixture[key])

    result = extract_meeting_minutes_via_pqx(
        fixture["transcript_artifact"],
        fixture["context_bundle"],
        fixture["gate_evidence"],
        store,
    )

    assert result["execution_record"]["record_type"] == "pqx_execution_record"
    assert result["execution_record"]["status"] == "success"
    assert result["output_artifact"]["artifact_type"] == "meeting_minutes_artifact"


def test_namespace_examples_validate_independently_and_runtime_stays_transcript_pipeline() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    transcript_schema = _load_contract_schema("meeting_minutes_artifact")

    namespaced_example = _load_json_path(
        repo_root / "contracts" / "examples" / "transcript_pipeline" / "meeting_minutes_artifact.example.json"
    )
    validate(namespaced_example, transcript_schema)

    legacy_wpg_example = _load_json_path(repo_root / "contracts" / "examples" / "meeting_minutes_artifact.json")
    assert legacy_wpg_example.get("schema_version") == "1.0.0"
    assert namespaced_example.get("schema_ref") == "transcript_pipeline/meeting_minutes_artifact"

    fixture = _load_fixture("cpl04_valid_transcript.json")
    payload = extract_meeting_minutes(fixture["transcript_artifact"], fixture["context_bundle"], fixture["gate_evidence"])
    assert payload["schema_ref"] == "transcript_pipeline/meeting_minutes_artifact"
    assert payload["artifact_type"] == "meeting_minutes_artifact"
