from __future__ import annotations

from copy import deepcopy

from spectrum_systems.modules.runtime.context_admission import run_context_admission
from spectrum_systems.modules.runtime.context_bundle import compose_context_bundle


def _valid_bundle() -> dict:
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
        glossary_terms=[],
        unresolved_questions=["owner?"],
        source_artifact_ids=["art-001"],
        trace_id="trace-001",
        run_id="run-001",
        glossary_registry_entries=[],
        glossary_injection_policy={"enabled": False},
    )


def test_valid_bundle_allows_execution() -> None:
    result = run_context_admission(context_bundle=_valid_bundle(), stage="observe")
    decision = result["context_admission_decision"]
    assert decision["decision_status"] == "allow"
    assert decision["allow_execution"] is True
    assert decision["reason_codes"] == []


def test_missing_bundle_blocks_execution() -> None:
    result = run_context_admission(context_bundle=None, stage="observe")
    decision = result["context_admission_decision"]
    assert decision["decision_status"] == "block"
    assert "missing_context_bundle" in decision["reason_codes"]


def test_invalid_bundle_schema_version_blocks() -> None:
    bundle = _valid_bundle()
    bundle["schema_version"] = "0.0.0"
    result = run_context_admission(context_bundle=bundle, stage="observe")
    reason_codes = result["context_admission_decision"]["reason_codes"]
    assert "unsupported_context_bundle_schema_version" in reason_codes


def test_missing_policy_resolution_blocks() -> None:
    result = run_context_admission(context_bundle=_valid_bundle(), stage="unknown_stage")
    reason_codes = result["context_admission_decision"]["reason_codes"]
    assert any(code.startswith("policy_resolution_failed:") for code in reason_codes)
    assert result["context_admission_decision"]["decision_status"] == "block"


def test_disallowed_trust_source_combination_blocks() -> None:
    bundle = _valid_bundle()
    inferred_item = next(item for item in bundle["context_items"] if item["item_type"] == "unresolved_question")
    inferred_item["trust_level"] = "untrusted"
    result = run_context_admission(context_bundle=bundle, requested_policy="decision_grade", stage="observe")
    decision = result["context_admission_decision"]
    assert decision["decision_status"] == "block"
    assert "disallowed_trust_source_combination" in decision["reason_codes"]
    assert {"source_classification": "inferred", "trust_level": "untrusted"} in decision[
        "blocked_trust_source_pairs"
    ]


def test_deterministic_same_input_same_decision() -> None:
    bundle = _valid_bundle()
    first = run_context_admission(context_bundle=deepcopy(bundle), requested_policy="permissive", stage="observe")
    second = run_context_admission(context_bundle=deepcopy(bundle), requested_policy="permissive", stage="observe")
    assert first["context_validation_result"] == second["context_validation_result"]
    assert first["context_admission_decision"] == second["context_admission_decision"]


def test_invalid_admission_state_never_silent_pass() -> None:
    result = run_context_admission(context_bundle="not-an-object", stage="observe")
    decision = result["context_admission_decision"]
    assert decision["decision_status"] == "block"
    assert decision["allow_execution"] is False
