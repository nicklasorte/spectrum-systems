from __future__ import annotations

import json
from datetime import datetime, timezone
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
        glossary_injection_policy={"enabled": True, "fail_on_missing_required": True},
    )


def test_schema_example_validation() -> None:
    schema = load_schema("context_bundle")
    example_path = Path("contracts/examples/context_bundle.json")
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_valid_segmented_bundle_construction() -> None:
    bundle = _compose()
    assert bundle["artifact_type"] == "context_bundle"
    assert bundle["schema_version"] == "2.3.0"
    assert bundle["source_segmentation"]["classification_counts"] == {
        "internal": 3,
        "external": 1,
        "inferred": 1,
        "user_provided": 1,
    }
    glossary_items = [item for item in bundle["context_items"] if item["item_type"] == "glossary_definition"]
    assert len(glossary_items) == 1
    assert bundle["glossary_canonicalization"]["injection_enabled"] is True


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


def test_missing_provenance_ref_rejected_fail_closed() -> None:
    bundle = _compose()
    del bundle["context_items"][0]["provenance_ref"]
    with pytest.raises(ContextBundleValidationError, match="provenance_ref"):
        validate_context_bundle(bundle)


def test_invalid_item_type_rejected_fail_closed() -> None:
    bundle = _compose()
    bundle["context_items"][0]["item_type"] = "ad_hoc"
    with pytest.raises(ContextBundleValidationError, match="unknown item_type"):
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


def test_inconsistent_ordering_rejected() -> None:
    bundle = _compose()
    bundle["context_items"][0], bundle["context_items"][1] = (
        bundle["context_items"][1],
        bundle["context_items"][0],
    )
    for idx, item in enumerate(bundle["context_items"]):
        item["item_index"] = idx
    with pytest.raises(ContextBundleValidationError, match="non-deterministic ordering"):
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
            glossary_injection_policy={"enabled": True, "fail_on_missing_required": True},
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
            glossary_injection_policy={"enabled": True, "fail_on_missing_required": True},
        )


def test_glossary_terms_with_injection_disabled_does_not_fail() -> None:
    bundle = compose_context_bundle(
        task_type="meeting_minutes",
        input_payload={"transcript": "hello", "provenance_id": "input-001"},
        policy_constraints={"require": ["decisions"], "provenance_id": "policy-001"},
        retrieved_context=[],
        prior_artifacts=[],
        glossary_terms=["SLA"],
        unresolved_questions=[],
        source_artifact_ids=[],
        trace_id="trace-001",
        run_id="run-001",
        glossary_registry_entries=[],
        glossary_injection_policy={"enabled": False},
    )
    assert bundle["glossary_definitions"] == []
    assert bundle["token_estimates"]["glossary_definitions"] == 0
    assert bundle["glossary_canonicalization"]["injection_enabled"] is False


def test_deterministic_item_id_repeated_composition() -> None:
    b1 = _compose()
    b2 = _compose()
    assert [item["item_id"] for item in b1["context_items"]] == [
        item["item_id"] for item in b2["context_items"]
    ]


def test_enabled_injection_with_missing_defs_unresolved_when_not_required() -> None:
    bundle = compose_context_bundle(
        task_type="meeting_minutes",
        input_payload={"transcript": "hello", "provenance_id": "input-001"},
        policy_constraints={"require": ["decisions"], "provenance_id": "policy-001"},
        retrieved_context=[],
        prior_artifacts=[],
        glossary_terms=["SLA"],
        unresolved_questions=[],
        source_artifact_ids=[],
        trace_id="trace-001",
        run_id="run-001",
        glossary_registry_entries=[],
        glossary_injection_policy={"enabled": True, "fail_on_missing_required": False},
    )
    assert bundle["glossary_definitions"] == []
    assert bundle["glossary_canonicalization"]["unresolved_terms"] == ["SLA@general"]
    assert bundle["glossary_canonicalization"]["injection_enabled"] is True

from spectrum_systems.modules.runtime.context_selector import (
    ContextSelectorError,
    build_context_bundle,
    canonical_serialize_context_bundle,
)


def test_context_bundle_v2_schema_example_validation() -> None:
    schema = load_schema("context_bundle_v2")
    example_path = Path("contracts/examples/context_bundle_v2.json")
    payload = json.loads(example_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_context_bundle_v2_canonical_serialization_is_deterministic() -> None:
    fixed_now = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)
    bundle = build_context_bundle(
        roadmap_state={"source_refs": ["roadmap:1"]},
        target_scope={"scope_type": "batch_id", "scope_id": "BATCH-O"},
        review_artifacts=[
            {
                "artifact_type": "review_artifact",
                "artifact_id": "rvw-1",
                "created_at": "2026-04-03T00:00:00Z",
                "batch_id": "BATCH-O",
                "module_refs": ["m/a.py"],
            }
        ],
        eval_artifacts=[],
        failure_artifacts=[],
        build_report_artifacts=[
            {
                "artifact_type": "build_report",
                "artifact_id": "br-1",
                "created_at": "2026-04-03T00:00:00Z",
                "batch_id": "BATCH-O",
                "module_refs": ["m/a.py"],
            }
        ],
        handoff_artifacts=[
            {
                "artifact_type": "next_slice_handoff",
                "artifact_id": "handoff-1",
                "created_at": "2026-04-03T00:00:00Z",
                "batch_id": "BATCH-O",
                "module_refs": ["m/a.py"],
            }
        ],
        pqx_execution_artifacts=[],
        touched_module_refs=["m/a.py"],
        active_risks=[],
        intent_refs=[],
        trace_id="trace-ctx-1",
        now=fixed_now,
    )
    bundle_replay = build_context_bundle(
        roadmap_state={"source_refs": ["roadmap:1"]},
        target_scope={"scope_type": "batch_id", "scope_id": "BATCH-O"},
        review_artifacts=[
            {
                "artifact_type": "review_artifact",
                "artifact_id": "rvw-1",
                "created_at": "2026-04-03T00:00:00Z",
                "batch_id": "BATCH-O",
                "module_refs": ["m/a.py"],
            }
        ],
        eval_artifacts=[],
        failure_artifacts=[],
        build_report_artifacts=[
            {
                "artifact_type": "build_report",
                "artifact_id": "br-1",
                "created_at": "2026-04-03T00:00:00Z",
                "batch_id": "BATCH-O",
                "module_refs": ["m/a.py"],
            }
        ],
        handoff_artifacts=[
            {
                "artifact_type": "next_slice_handoff",
                "artifact_id": "handoff-1",
                "created_at": "2026-04-03T00:00:00Z",
                "batch_id": "BATCH-O",
                "module_refs": ["m/a.py"],
            }
        ],
        pqx_execution_artifacts=[],
        touched_module_refs=["m/a.py"],
        active_risks=[],
        intent_refs=[],
        trace_id="trace-ctx-1",
        now=fixed_now,
    )
    assert canonical_serialize_context_bundle(bundle) == canonical_serialize_context_bundle(bundle_replay)


def test_context_bundle_v2_empty_selected_refs_fail_closed() -> None:
    with pytest.raises(ContextSelectorError, match="non-empty"):
        build_context_bundle(
            roadmap_state={"source_refs": ["roadmap:1"]},
            target_scope={"scope_type": "batch_id", "scope_id": "BATCH-O"},
            review_artifacts=[
                {
                    "artifact_type": "review_artifact",
                    "artifact_id": "rvw-stale",
                    "created_at": "2026-04-01T00:00:00Z",
                    "batch_id": "BATCH-O",
                    "module_refs": ["m/a.py"],
                }
            ],
            eval_artifacts=[],
            failure_artifacts=[],
            build_report_artifacts=[
                {
                    "artifact_type": "build_report",
                    "artifact_id": "br-stale",
                    "created_at": "2026-04-01T00:00:00Z",
                    "batch_id": "BATCH-O",
                    "module_refs": ["m/a.py"],
                }
            ],
            handoff_artifacts=[
                {
                    "artifact_type": "next_slice_handoff",
                    "artifact_id": "handoff-stale",
                    "created_at": "2026-04-01T00:00:00Z",
                    "batch_id": "BATCH-O",
                    "module_refs": ["m/a.py"],
                }
            ],
            pqx_execution_artifacts=[],
            touched_module_refs=["m/a.py"],
            active_risks=[],
            intent_refs=[],
            trace_id="trace-ctx-stale",
            now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
            stale_after_days=14,
        )
