import pytest

import copy

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema


SOURCE_REF_VALID = {
    "artifact_type": "strategic_knowledge_source_ref",
    "schema_version": "1.0.0",
    "source_id": "SRC-BOOK-001",
    "source_type": "book_pdf",
    "source_path": "strategic_knowledge/raw/books/book-a.pdf",
    "source_status": "registered",
    "registered_at": "2026-03-20T00:00:00Z",
    "metadata": {"title": "Book A"},
}

ARTIFACT_REF_VALID = {
    "artifact_type": "book_intelligence_pack",
    "artifact_id": "ART-001",
    "artifact_version": "1.0.0",
    "schema_version": "1.0.0",
    "created_at": "2026-03-20T00:00:00Z",
    "source": {
        "source_id": "SRC-BOOK-001",
        "source_type": "book_pdf",
        "source_path": "strategic_knowledge/raw/books/book-a.pdf",
    },
    "provenance": {
        "extraction_run_id": "run-001",
        "extractor_version": "0.1.0",
    },
    "evidence_anchors": [{"anchor_type": "pdf", "page_number": 1}],
}


def _book_payload() -> dict:
    payload = copy.deepcopy(ARTIFACT_REF_VALID)
    payload.update(
        {
            "artifact_type": "book_intelligence_pack",
            "insights": ["Insight 1"],
            "themes": ["Theme A"],
            "key_claims": ["Claim A"],
            "confidence": "medium",
        }
    )
    return payload


def _transcript_payload() -> dict:
    payload = copy.deepcopy(ARTIFACT_REF_VALID)
    payload.update(
        {
            "artifact_type": "transcript_intelligence_pack",
            "source": {
                "source_id": "SRC-TX-001",
                "source_type": "transcript",
                "source_path": "strategic_knowledge/raw/transcripts/session-1.txt",
            },
            "evidence_anchors": [
                {
                    "anchor_type": "transcript",
                    "timestamp_start": "00:02:00",
                    "timestamp_end": "00:03:00",
                    "speaker": "Moderator",
                }
            ],
            "decisions": ["Decision A"],
            "open_questions": ["Question A"],
            "action_signals": ["Action A"],
        }
    )
    return payload


def _story_payload() -> dict:
    payload = copy.deepcopy(ARTIFACT_REF_VALID)
    payload.update(
        {
            "artifact_type": "story_bank_entry",
            "headline": "Headline",
            "narrative": "Narrative text",
            "strategic_relevance": "Strategic relevance",
        }
    )
    return payload


def _tactic_payload() -> dict:
    payload = copy.deepcopy(ARTIFACT_REF_VALID)
    payload.update(
        {
            "artifact_type": "tactic_register",
            "tactic_name": "Tactic",
            "context": "Context",
            "recommended_use": "Use in condition X",
        }
    )
    return payload


def _viewpoint_payload() -> dict:
    payload = copy.deepcopy(ARTIFACT_REF_VALID)
    payload.update(
        {
            "artifact_type": "viewpoint_pack",
            "viewpoint": "A viewpoint",
            "supporting_arguments": ["Arg 1"],
            "counterpoints": ["Counter 1"],
        }
    )
    return payload


def _evidence_map_payload() -> dict:
    payload = copy.deepcopy(ARTIFACT_REF_VALID)
    payload.update(
        {
            "artifact_type": "evidence_map",
            "claim_id": "CLAIM-1",
            "claim_text": "Claim text",
            "confidence": "low",
        }
    )
    return payload


def test_source_ref_schema_valid_payload() -> None:
    schema = load_schema("strategic_knowledge_source_ref")
    Draft202012Validator(schema).validate(SOURCE_REF_VALID)


def test_artifact_ref_schema_valid_payload() -> None:
    schema = load_schema("strategic_knowledge_artifact_ref")
    Draft202012Validator(schema).validate(ARTIFACT_REF_VALID)


def test_all_artifact_family_schemas_accept_valid_payloads() -> None:
    payloads = {
        "book_intelligence_pack": _book_payload(),
        "transcript_intelligence_pack": _transcript_payload(),
        "story_bank_entry": _story_payload(),
        "tactic_register": _tactic_payload(),
        "viewpoint_pack": _viewpoint_payload(),
        "evidence_map": _evidence_map_payload(),
    }
    for schema_name, payload in payloads.items():
        schema = load_schema(schema_name)
        Draft202012Validator(schema).validate(payload)


def test_missing_required_field_fails() -> None:
    schema = load_schema("book_intelligence_pack")
    payload = _book_payload()
    payload.pop("artifact_id")
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_extra_field_fails() -> None:
    schema = load_schema("book_intelligence_pack")
    payload = _book_payload()
    payload["unexpected"] = "bad"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_invalid_source_type_fails() -> None:
    schema = load_schema("book_intelligence_pack")
    payload = _book_payload()
    payload["source"]["source_type"] = "podcast"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_malformed_transcript_anchor_fails() -> None:
    schema = load_schema("transcript_intelligence_pack")
    payload = _transcript_payload()
    payload["evidence_anchors"][0]["timestamp_start"] = "bad-time"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_invalid_artifact_type_fails() -> None:
    schema = load_schema("evidence_map")
    payload = _evidence_map_payload()
    payload["artifact_type"] = "story_bank_entry"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)

