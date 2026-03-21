import copy

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema


VALID_DECISION = {
    "decision_id": "SK-VAL-ART-001",
    "trace_id": "trace-001",
    "span_id": "span-001",
    "artifact_id": "ART-001",
    "artifact_type": "book_intelligence_pack",
    "schema_version": "1.0.0",
    "evaluated_at": "2026-03-21T12:00:00Z",
    "validator_version": "1.0.0",
    "schema_valid": True,
    "source_refs_valid": True,
    "artifact_refs_valid": True,
    "evidence_anchor_coverage": 1.0,
    "provenance_completeness": 1.0,
    "trust_score": 1.0,
    "issues": [
        {
            "code": "VALIDATION_PASSED",
            "severity": "info",
            "message": "Artifact satisfied all strategic knowledge validation gate checks.",
        }
    ],
    "system_response": "allow",
}


def _validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema("strategic_knowledge_validation_decision"))


def test_valid_decision_artifact_passes() -> None:
    _validator().validate(VALID_DECISION)


def test_missing_required_field_fails() -> None:
    payload = copy.deepcopy(VALID_DECISION)
    payload.pop("trace_id")
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_empty_trace_field_fails() -> None:
    payload = copy.deepcopy(VALID_DECISION)
    payload["span_id"] = ""
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_invalid_system_response_fails() -> None:
    payload = copy.deepcopy(VALID_DECISION)
    payload["system_response"] = "pass"
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_extra_field_fails_when_additional_properties_false() -> None:
    payload = copy.deepcopy(VALID_DECISION)
    payload["unexpected"] = "not-allowed"
    with pytest.raises(ValidationError):
        _validator().validate(payload)
