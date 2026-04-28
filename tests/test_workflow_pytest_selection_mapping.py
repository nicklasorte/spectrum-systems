"""Pytest selection mapping for changed CI workflow files and workflow-named tests.

Regression coverage for the WFL-01 contract preflight failure where a PR that
only touched ``.github/workflows/`` and ``tests/test_*workflow*.py`` produced an
empty pytest selection (``pytest_selection_missing``) and was correctly blocked
by the governed contract preflight. The fix maps these surfaces to a
deterministic pytest selection so future workflow-only PRs do not fall through
to the governed PR fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import run_contract_preflight as preflight
from spectrum_systems.modules.runtime.pytest_selection_integrity import (
    evaluate_pytest_selection_integrity,
)


_POLICY_PATH = Path("docs/governance/pytest_pr_selection_integrity_policy.json")


def test_ci_workflow_yaml_classifies_as_forced_evaluation_surface() -> None:
    requires_eval, surface, reason = preflight._is_forced_evaluation_surface(
        ".github/workflows/artifact-boundary.yml"
    )
    assert requires_eval is True
    assert surface == "ci_workflow_surface"
    assert "workflow" in reason.lower()


def test_workflow_named_pytest_files_classify_as_contract_tied_tests() -> None:
    requires_eval, surface, _ = preflight._is_forced_evaluation_surface(
        "tests/test_artifact_boundary_workflow_pytest_policy_observation.py"
    )
    assert requires_eval is True
    assert surface == "contract_tied_tests"

    requires_eval, surface, _ = preflight._is_forced_evaluation_surface(
        "tests/test_artifact_boundary_workflow_policy_observation.py"
    )
    assert requires_eval is True
    assert surface == "contract_tied_tests"


def test_artifact_boundary_workflow_has_explicit_required_surface_override() -> None:
    overrides = preflight._load_required_surface_override_map(preflight.REPO_ROOT)
    targets = overrides.get(".github/workflows/artifact-boundary.yml", [])
    assert "tests/test_artifact_boundary_workflow_pytest_policy_observation.py" in targets
    assert "tests/test_artifact_boundary_workflow_policy_observation.py" in targets


def test_artifact_boundary_workflow_has_explicit_selection_integrity_surface_rule() -> None:
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    rules = {
        rule["path_prefix"]: rule["required_test_targets"]
        for rule in policy.get("surface_rules", [])
        if isinstance(rule, dict) and rule.get("path_prefix")
    }
    assert ".github/workflows/artifact-boundary.yml" in rules
    targets = rules[".github/workflows/artifact-boundary.yml"]
    assert "tests/test_artifact_boundary_workflow_pytest_policy_observation.py" in targets
    assert "tests/test_artifact_boundary_workflow_policy_observation.py" in targets


def test_artifact_boundary_workflow_pr_diff_produces_allow_selection_integrity() -> None:
    # Selecting the canonical workflow tests for a PR whose only changed paths
    # are the workflow yaml and its bound tests must produce ALLOW (no
    # PYTEST_REQUIRED_TARGETS_MISSING, no PYTEST_SELECTION_FILTERING_DETECTED).
    selected = [
        "tests/test_artifact_boundary_workflow_pytest_policy_observation.py",
        "tests/test_artifact_boundary_workflow_policy_observation.py",
    ]
    result = evaluate_pytest_selection_integrity(
        changed_paths=[
            ".github/workflows/artifact-boundary.yml",
            "tests/test_artifact_boundary_workflow_policy_observation.py",
            "tests/test_artifact_boundary_workflow_pytest_policy_observation.py",
        ],
        selected_test_targets=selected,
        required_test_targets=selected,
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_POLICY_PATH,
        generated_at="2026-04-27T00:00:00Z",
    )
    assert result.decision == "ALLOW"
    assert result.blocking_reasons == []


def test_workflow_only_pr_does_not_silently_fall_to_fallback_targets() -> None:
    # Reproduces the WFL-01 blocking signature: an empty selection paired with
    # an empty fallback signal (PR_PYTEST_SELECTED_TARGETS_EMPTY) must remain
    # fail-closed even when fallback is non-empty — this guards against silent
    # broadening if the mapping regresses in the future.
    result = evaluate_pytest_selection_integrity(
        changed_paths=[".github/workflows/artifact-boundary.yml"],
        selected_test_targets=[],
        required_test_targets=[],
        pytest_execution_record={
            "executed": True,
            "selection_reason_codes": ["PR_PYTEST_SELECTED_TARGETS_EMPTY"],
        },
        policy_path=_POLICY_PATH,
        generated_at="2026-04-27T00:00:00Z",
    )
    assert result.decision == "BLOCK"
    assert "PYTEST_SELECTION_FILTERING_DETECTED" in result.blocking_reasons
