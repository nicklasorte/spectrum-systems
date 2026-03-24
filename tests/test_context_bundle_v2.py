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


_GLOSSARY_ENTRY = {
    "artifact_type": "glossary_entry",
    "schema_version": "1.0.0",
    "glossary_entry_id": "gle-a2f8fbe34b21d991",
    "term_id": "sla",
    "canonical_term": "SLA",
    "definition": "Service Level Agreement governing measurable service commitments.",
    "domain_scope": "runtime",
    "version": "v1.0.0",
    "status": "approved",
    "provenance_refs": ["rules/policy/sla.md"],
    "created_at": "2026-03-24T00:00:00Z",
}


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
        glossary_terms=[{"requested_term": "SLA", "term_id": "sla", "domain_scope": "runtime"}],
        unresolved_questions=["owner?"],
        source_artifact_ids=["art-001"],
        trace_id="trace-001",
        run_id="run-001",
        glossary_registry_entries=[dict(_GLOSSARY_ENTRY)],
    )


def test_schema_example_validation() -> None:
    schema = load_schema("context_bundle")
    example_path = Path("contracts/examples/context_bundle.json")
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_valid_segmented_bundle_construction() -> None:
    bundle = _compose()
    assert bundle["artifact_type"] == "context_bundle"
    assert bundle["schema_version"] == "2.2.0"
    assert bundle["source_segmentation"]["classification_counts"] == {
        "internal": 3,
        "external": 1,
        "inferred": 1,
        "user_provided": 1,
    }
    glossary_items = [item for item in bundle["context_items"] if item["item_type"] == "glossary_definition"]
    assert len(glossary_items) == 1


def test_deterministic_repeated_composition() -> None:
    b1 = _compose()
    b2 = _compose()
    assert b1 == b2


def test_unknown_trust_level_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0]["trust_level"] = "super_trusted"
    with pytest.raises(ContextBundleValidationError, match="unknown trust_level"):
        validate_context_bundle(bundle)


def test_invalid_source_classification_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0]["source_classification"] = "mixed"
    with pytest.raises(ContextBundleValidationError, match="source_classification"):
        validate_context_bundle(bundle)


def test_missing_source_classification_rejected_fail_closed() -> None:
    bundle = _compose()
    del bundle["context_items"][0]["source_classification"]
    with pytest.raises(ContextBundleValidationError, match="source_classification"):
        validate_context_bundle(bundle)


def test_inferred_vs_grounded_separation_enforced() -> None:
    bundle = _compose()
    unresolved_item = next(
        item for item in bundle["context_items"] if item["item_type"] == "unresolved_question"
    )
    unresolved_item["source_classification"] = "internal"
    with pytest.raises(ContextBundleValidationError, match="mixed-source violation"):
        validate_context_bundle(bundle)


def test_user_provided_vs_internal_trust_boundary_enforced() -> None:
    bundle = _compose()
    retrieved = next(item for item in bundle["context_items"] if item["item_type"] == "retrieved_context")
    retrieved["trust_level"] = "high"
    with pytest.raises(ContextBundleValidationError, match="inconsistent trust_level"):
        validate_context_bundle(bundle)


def test_runtime_trace_linkage_and_source_summary_present() -> None:
    bundle = _compose()
    assert bundle["trace"]["trace_id"] == "trace-001"
    assert bundle["trace"]["run_id"] == "run-001"
    assert bundle["source_segmentation"]["item_refs_by_class"]["external"]


def test_no_silent_fallback_classification() -> None:
    bundle = _compose()
    bundle["context_items"][2]["source_classification"] = ""
    with pytest.raises(ContextBundleValidationError, match="source_classification"):
        validate_context_bundle(bundle)


def test_source_segmentation_mismatch_rejected() -> None:
    bundle = _compose()
    bundle["source_segmentation"]["classification_counts"]["external"] = 0
    with pytest.raises(ContextBundleValidationError, match="source segmentation mismatch"):
        validate_context_bundle(bundle)


def test_missing_required_glossary_definition_fails_closed() -> None:
    with pytest.raises(ContextBundleValidationError, match="missing required canonical glossary definitions"):
        compose_context_bundle(
            task_type="meeting_minutes",
            input_payload={"transcript": "hello", "provenance_id": "input-001"},
            policy_constraints={"require": ["decisions"], "provenance_id": "policy-001"},
            retrieved_context=[],
            prior_artifacts=[],
            glossary_terms=["UNKNOWN_TERM"],
            unresolved_questions=[],
            source_artifact_ids=[],
            trace_id="trace-001",
            run_id="run-001",
            glossary_registry_entries=[dict(_GLOSSARY_ENTRY)],
        )


def test_no_fuzzy_matching_behavior() -> None:
    with pytest.raises(ContextBundleValidationError, match="missing required canonical glossary definitions"):
        compose_context_bundle(
            task_type="meeting_minutes",
            input_payload={"transcript": "hello", "provenance_id": "input-001"},
            policy_constraints={"require": ["decisions"], "provenance_id": "policy-001"},
            retrieved_context=[],
            prior_artifacts=[],
            glossary_terms=["SLAA"],
            unresolved_questions=[],
            source_artifact_ids=[],
            trace_id="trace-001",
            run_id="run-001",
            glossary_registry_entries=[dict(_GLOSSARY_ENTRY)],
        )
