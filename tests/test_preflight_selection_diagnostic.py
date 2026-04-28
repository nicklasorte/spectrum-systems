"""Tests for the WFL-owned pytest selection diagnostic surface.

The module under test is a non-authoritative observation surface — it produces
recommendations and inputs for canonical decision/enforcement authorities
(JDX/CDE for decisions, SEL/ENF for enforcement). Tests assert that the surface
correctly names unmatched changed paths, mirrors the policy registry's
surface_rules, and points operators at the canonical mapping locations.
"""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.preflight_selection_diagnostic import (
    PYTEST_SELECTION_OBSERVATION_FAILURE_CLASSES,
    build_pytest_selection_observation,
    is_pytest_selection_observation_class,
)


def _write_policy(tmp_path: Path) -> Path:
    payload = {
        "artifact_type": "pytest_pr_selection_integrity_policy",
        "schema_version": "1.0.0",
        "surface_rules": [
            {
                "path_prefix": "scripts/run_contract_preflight.py",
                "required_test_targets": ["tests/test_contract_preflight.py"],
            },
            {
                "path_prefix": ".github/workflows/artifact-boundary.yml",
                "required_test_targets": [
                    "tests/test_artifact_boundary_workflow_pytest_policy_observation.py",
                ],
            },
        ],
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_observation_lists_unmatched_changed_paths_and_mirrors_policy_rules(tmp_path: Path) -> None:
    policy_path = _write_policy(tmp_path)
    observation = build_pytest_selection_observation(
        report={
            "changed_path_detection": {
                "changed_paths_resolved": [
                    ".github/workflows/example-workflow.yml",
                    "tests/test_unmatched_workflow_signal.py",
                ],
            },
            "evaluation_classification": [
                {
                    "path": ".github/workflows/example-workflow.yml",
                    "classification": "no_applicable_contract_surface",
                    "reason": "path does not map to governed contract surface",
                    "requires_evaluation": False,
                    "surface": "other",
                },
            ],
            "pytest_selection_integrity": {
                "selected_test_targets": [],
                "missing_required_targets": [
                    "tests/test_artifact_boundary_workflow_pytest_policy_observation.py",
                ],
            },
        },
        policy_path=policy_path,
    )

    assert ".github/workflows/example-workflow.yml" in observation["unmatched_changed_paths"]
    assert (
        "tests/test_artifact_boundary_workflow_pytest_policy_observation.py"
        in observation["unmatched_changed_paths"]
    )

    # The observation mirrors the canonical policy registry's surface_rules so
    # the operator sees what was attempted, not just what's missing.
    rule_prefixes = {rule["path_prefix"] for rule in observation["attempted_surface_rules"]}
    assert rule_prefixes == {
        "scripts/run_contract_preflight.py",
        ".github/workflows/artifact-boundary.yml",
    }

    locations = observation["recommended_mapping_locations"]
    assert any("pytest_pr_selection_integrity_policy.json" in loc for loc in locations)
    assert any("preflight_required_surface_test_overrides.json" in loc for loc in locations)
    assert any("_REQUIRED_SURFACE_TEST_OVERRIDES" in loc for loc in locations)
    assert any("_is_forced_evaluation_surface" in loc for loc in locations)


def test_observation_handles_missing_policy_file(tmp_path: Path) -> None:
    observation = build_pytest_selection_observation(
        report={
            "changed_path_detection": {"changed_paths_resolved": []},
            "evaluation_classification": [],
            "pytest_selection_integrity": {},
        },
        policy_path=tmp_path / "missing.json",
    )
    assert observation["attempted_surface_rules"] == []
    assert observation["unmatched_changed_paths"] == []
    assert observation["recommended_mapping_locations"]


def test_failure_class_predicate_covers_every_observation_class() -> None:
    for failure_class in PYTEST_SELECTION_OBSERVATION_FAILURE_CLASSES:
        assert is_pytest_selection_observation_class(failure_class)
    assert not is_pytest_selection_observation_class("contract_mismatch")
    assert not is_pytest_selection_observation_class("internal_preflight_error")
    assert not is_pytest_selection_observation_class(None)
    assert not is_pytest_selection_observation_class("")


def test_recommended_locations_use_non_authority_vocabulary() -> None:
    observation = build_pytest_selection_observation(
        report={"changed_path_detection": {}, "evaluation_classification": [], "pytest_selection_integrity": {}},
        policy_path=Path("nonexistent.json"),
    )
    # The recommended-locations strings must not imply WFL owns decisions or
    # enforcement — they may only point to registries or runtime selectors.
    forbidden = {"decision", "decisions", "decided", "verdict", "adjudication", "enforcement", "enforce", "enforced"}
    for loc in observation["recommended_mapping_locations"]:
        tokens = {token.lower() for token in loc.replace(":", "/").replace("#", "/").split("/")}
        flat = "/".join(tokens)
        for term in forbidden:
            assert term not in flat.split("/"), f"recommended location uses forbidden term '{term}': {loc}"
