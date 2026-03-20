import pytest

jsonschema = pytest.importorskip("jsonschema")
Draft202012Validator = jsonschema.Draft202012Validator
ValidationError = jsonschema.exceptions.ValidationError

from spectrum_systems.contracts import load_schema



def _book_payload() -> dict:
    return {
        'artifact_type': 'book_intelligence_pack',
        'artifact_id': 'BIP-001',
        'artifact_version': '1.0.0',
        'schema_version': '1.0.0',
        'created_at': '2026-03-20T00:00:00Z',
        'source': {
            'source_id': 'SRC-BOOK-001',
            'source_type': 'book_pdf',
            'source_path': 'strategic_knowledge/raw/books/book-a.pdf',
        },
        'provenance': {
            'extraction_run_id': 'run-001',
            'extractor_version': '0.1.0',
        },
        'evidence_anchors': [
            {
                'anchor_type': 'pdf',
                'page_number': 12,
                'quote_snippet': 'Anchor snippet',
            }
        ],
        'insights': ['Insight 1'],
        'themes': ['Theme A'],
        'key_claims': ['Claim A'],
        'confidence': 'medium',
    }


def _transcript_payload() -> dict:
    payload = {
        'artifact_type': 'transcript_intelligence_pack',
        'artifact_id': 'TIP-001',
        'artifact_version': '1.0.0',
        'schema_version': '1.0.0',
        'created_at': '2026-03-20T00:00:00Z',
        'source': {
            'source_id': 'SRC-TX-001',
            'source_type': 'transcript',
            'source_path': 'strategic_knowledge/raw/transcripts/session-1.txt',
        },
        'provenance': {
            'extraction_run_id': 'run-002',
            'extractor_version': '0.1.0',
        },
        'evidence_anchors': [
            {
                'anchor_type': 'transcript',
                'timestamp_start': '00:02:00',
                'timestamp_end': '00:03:00',
                'speaker': 'Moderator',
            }
        ],
        'decisions': ['Decision A'],
        'open_questions': ['Question A'],
        'action_signals': ['Action A'],
    }
    return payload


def test_book_schema_valid_payload() -> None:
    schema = load_schema('book_intelligence_pack')
    Draft202012Validator(schema).validate(_book_payload())


def test_transcript_schema_valid_payload() -> None:
    schema = load_schema('transcript_intelligence_pack')
    Draft202012Validator(schema).validate(_transcript_payload())


def test_missing_required_field_fails() -> None:
    schema = load_schema('book_intelligence_pack')
    payload = _book_payload()
    payload.pop('artifact_id')
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_extra_field_fails() -> None:
    schema = load_schema('book_intelligence_pack')
    payload = _book_payload()
    payload['unexpected'] = 'bad'
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_invalid_source_type_fails() -> None:
    schema = load_schema('book_intelligence_pack')
    payload = _book_payload()
    payload['source']['source_type'] = 'podcast'
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_invalid_artifact_type_fails() -> None:
    schema = load_schema('evidence_map')
    payload = {
        'artifact_type': 'story_bank_entry',
        'artifact_id': 'EM-001',
        'artifact_version': '1.0.0',
        'schema_version': '1.0.0',
        'created_at': '2026-03-20T00:00:00Z',
        'source': {
            'source_id': 'SRC-BOOK-001',
            'source_type': 'book_pdf',
            'source_path': 'strategic_knowledge/raw/books/book-a.pdf',
        },
        'provenance': {
            'extraction_run_id': 'run-001',
            'extractor_version': '0.1.0',
        },
        'evidence_anchors': [{'anchor_type': 'pdf', 'page_number': 1}],
        'claim_id': 'CLAIM-1',
        'claim_text': 'A claim',
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)
