from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


def test_tlc_handoff_example_validates() -> None:
    validate_artifact(load_example("tlc_handoff_record.example"), "tlc_handoff_record")


def test_tlc_handoff_schema_rejects_malformed_payload() -> None:
    schema = load_schema("tlc_handoff_record")
    validator = Draft202012Validator(schema)
    malformed = copy.deepcopy(load_example("tlc_handoff_record.example"))
    malformed.pop("lineage", None)
    malformed["handoff_status"] = "unknown"
    malformed["unexpected"] = True
    errors = list(validator.iter_errors(malformed))
    assert errors, "schema must reject malformed tlc_handoff_record"


def test_tlc_handoff_schema_requires_no_unknown_fields() -> None:
    payload = copy.deepcopy(load_example("tlc_handoff_record.example"))
    payload["tlc_run_context"]["unexpected"] = "x"
    with pytest.raises(ValidationError):
        validate_artifact(payload, "tlc_handoff_record")
