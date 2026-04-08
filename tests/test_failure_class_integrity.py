from __future__ import annotations

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.failure_diagnosis_engine import (
    _known_failure_classes,
    _RULES,
    build_failure_repair_candidate_artifact,
)

def test_no_legacy_failure_class_names_exist_in_registry_rules() -> None:
    registry_classes = _known_failure_classes()
    legacy_names = {
        "extraction_error",
        "reasoning_error",
        "grounding_failure",
        "schema_violation",
        "hallucination",
        "regression_failure",
    }
    assert legacy_names.isdisjoint(registry_classes)
    rule_classes = {row["classification"] for row in _RULES}
    assert legacy_names.isdisjoint(rule_classes)


def test_registry_is_single_source_of_truth_for_known_failure_classes() -> None:
    registry = load_example("failure_class_registry")
    expected = set(registry["classes"].keys())
    assert _known_failure_classes() == expected


def test_unknown_failure_never_allows_repair_continuation() -> None:
    candidate = build_failure_repair_candidate_artifact(
        failure_packet={
            "failure_id": "flr-1",
            "source_run_ref": "run:1",
            "source_test_refs": ["pytest_failure:test_x"],
        },
        failure_diagnosis_artifact={
            "primary_root_cause": "unknown_failure",
            "recommended_repair_paths": ["contracts/schemas/a.json"],
        },
        proposed_repair_ref="repair:manual",
        trace_refs=["trace-1"],
    )
    assert candidate["failure_class"] == "unknown_failure"
    assert candidate["safe_to_repair"] is False
