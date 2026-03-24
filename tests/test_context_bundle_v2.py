from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.context_bundle import (
    ContextBundleValidationError,
    compose_context_bundle,
    validate_context_bundle,
)


def _compose() -> dict:
    return compose_context_bundle(
        task_type="meeting_minutes",
        input_payload={"transcript": "hello", "provenance_id": "input-001"},
        policy_constraints={"require": ["decisions"], "provenance_id": "policy-001"},
        retrieved_context=[
            {
                "artifact_id": "ret-001",
                "content": "snippet",
                "relevance_score": 0.8,
                "provenance": {"source_id": "ext-src-001", "provenance_refs": ["ext-src-001"]},
            }
        ],
        prior_artifacts=[{"artifact_id": "art-001", "kind": "decision"}],
        glossary_terms=["SLA"],
        unresolved_questions=["owner?"],
        source_artifact_ids=["art-001"],
        trace_id="trace-001",
        run_id="run-001",
    )


def test_schema_example_validation() -> None:
    schema = load_schema("context_bundle")
    example_path = Path("contracts/examples/context_bundle.json")
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_valid_typed_trusted_bundle_construction() -> None:
    bundle = _compose()
    assert bundle["artifact_type"] == "context_bundle"
    assert bundle["schema_version"] == "2.0.0"
    assert bundle["context_items"][0]["item_type"] == "primary_input"
    assert bundle["context_items"][0]["trust_level"] == "high"


def test_deterministic_repeated_composition() -> None:
    b1 = _compose()
    b2 = _compose()
    assert b1 == b2


def test_unknown_item_type_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0]["item_type"] = "unknown"
    with pytest.raises(ContextBundleValidationError, match="unknown item_type"):
        validate_context_bundle(bundle)


def test_unknown_trust_level_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0]["trust_level"] = "super_trusted"
    with pytest.raises(ContextBundleValidationError, match="unknown trust_level"):
        validate_context_bundle(bundle)


def test_missing_provenance_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0]["provenance_refs"] = []
    with pytest.raises(ContextBundleValidationError, match="provenance"):
        validate_context_bundle(bundle)


def test_invalid_source_classification_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0]["source_classification"] = "mixed"
    with pytest.raises(ContextBundleValidationError, match="source_classification"):
        validate_context_bundle(bundle)


def test_no_silent_coercion_of_malformed_items() -> None:
    bundle = _compose()
    bundle["context_items"][0]["item_index"] = 7
    with pytest.raises(ContextBundleValidationError, match="non-deterministic ordering"):
        validate_context_bundle(bundle)
