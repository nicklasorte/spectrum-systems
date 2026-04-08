from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


@pytest.mark.parametrize(
    "schema_name,example_name",
    [
        ("build_admission_record", "build_admission_record.example"),
        ("normalized_execution_request", "normalized_execution_request.example"),
        ("admission_rejection_record", "admission_rejection_record.example"),
    ],
)
def test_aex_examples_validate(schema_name: str, example_name: str) -> None:
    instance = load_example(example_name)
    validate_artifact(instance, schema_name)


@pytest.mark.parametrize(
    "schema_name,example_name",
    [
        ("build_admission_record", "build_admission_record.example"),
        ("normalized_execution_request", "normalized_execution_request.example"),
        ("admission_rejection_record", "admission_rejection_record.example"),
    ],
)
def test_aex_schemas_reject_unknown_top_level_fields(schema_name: str, example_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)
    bad = copy.deepcopy(load_example(example_name))
    bad["unexpected"] = True
    errors = list(validator.iter_errors(bad))
    assert errors, "schema must reject unknown top-level fields"
