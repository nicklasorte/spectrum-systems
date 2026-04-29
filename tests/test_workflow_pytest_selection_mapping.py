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

def test_pr1283_changed_paths_have_required_surface_mappings() -> None:
    changed_paths = [
        ".github/workflows/nightly-deep-gate.yml",
        "contracts/schemas/contract_gate_result.schema.json",
        "contracts/schemas/governance_gate_result.schema.json",
        "contracts/schemas/pr_gate_result.schema.json",
        "contracts/schemas/readiness_evidence_gate_result.schema.json",
        "contracts/schemas/runtime_test_gate_result.schema.json",
        "contracts/schemas/test_selection_gate_result.schema.json",
        "docs/architecture/ci_gate_model.md",
        "docs/governance/ci_gate_ownership_manifest.json",
        "docs/governance/ci_runtime_budget.md",
        "docs/governance/preflight_required_surface_test_overrides.json",
        "docs/governance/pytest_pr_selection_integrity_policy.json",
        "docs/governance/required_check_cleanup_instructions.md",
        "docs/governance/test_gate_mapping.json",
        "docs/review-actions/PLAN-TST-01-25-2026-04-28.md",
        "docs/review-actions/PLAN-TST-01-25-FIX-PR1283-2026-04-28.md",
        "docs/reviews/TST-01-25_fix_pr1283_report.md",
        "docs/reviews/TST-01_ci_test_inventory.md",
        "docs/reviews/TST-12_required_check_alignment.md",
        "docs/reviews/TST-16_gate_bypass_redteam.md",
        "docs/reviews/TST-18_parallel_gate_migration.md",
        "docs/reviews/TST-20_post_cutover_audit.md",
        "docs/reviews/TST-21_gate_parity_report.md",
        "docs/reviews/TST-25_final_delivery_report.md",
        "scripts/run_ci_drift_detector.py",
        "scripts/run_contract_gate.py",
        "scripts/run_governance_gate.py",
        "scripts/run_pr_gate.py",
        "scripts/run_readiness_evidence_gate.py",
        "scripts/run_runtime_test_gate.py",
        "scripts/run_test_selection_gate.py",
        "tests/test_ci_drift_detector.py",
        "tests/test_ci_gate_scripts.py",
    ]
    targets_by_path = preflight.resolve_required_surface_tests(preflight.REPO_ROOT, changed_paths)
    missing = [path for path, targets in targets_by_path.items() if not targets]
    assert missing == []
