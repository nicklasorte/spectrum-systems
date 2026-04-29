"""Pytest selection mapping for changed root governance instruction docs.

Regression coverage for the AEX-DOC-01 contract preflight failure where a
PR that only touched root ``AGENTS.md`` / ``CLAUDE.md`` produced an empty
pytest selection (``pytest_selection_missing``) and was correctly blocked
by the governed contract preflight. The fix maps these surfaces to a
deterministic pytest selection so future doc-only PRs do not fall through
to the governed PR fallback.

Mirrors ``tests/test_workflow_pytest_selection_mapping.py`` (WFL-01).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import run_contract_preflight as preflight
from spectrum_systems.modules.runtime.pytest_selection_integrity import (
    evaluate_pytest_selection_integrity,
)


_POLICY_PATH = Path("docs/governance/pytest_pr_selection_integrity_policy.json")
_BOUND_TEST = "tests/test_system_registry_guard.py"


def test_root_governance_instruction_docs_classify_as_forced_evaluation_surface() -> None:
    for path in ("AGENTS.md", "CLAUDE.md"):
        requires_eval, surface, reason = preflight._is_forced_evaluation_surface(path)
        assert requires_eval is True, f"{path} must be a forced evaluation surface"
        assert surface == "governance_instruction_doc"
        assert "instruction" in reason.lower()


def test_preflight_selection_policy_files_classify_as_forced_evaluation_surface() -> None:
    for path in (
        "docs/governance/pytest_pr_selection_integrity_policy.json",
        "docs/governance/preflight_required_surface_test_overrides.json",
    ):
        requires_eval, surface, reason = preflight._is_forced_evaluation_surface(path)
        assert requires_eval is True, f"{path} must be a forced evaluation surface"
        assert surface == "preflight_selection_policy"
        assert "selection policy" in reason.lower()


def test_root_governance_instruction_docs_have_explicit_required_surface_override() -> None:
    overrides = preflight._load_required_surface_override_map(preflight.REPO_ROOT)
    assert _BOUND_TEST in overrides.get("AGENTS.md", [])
    assert _BOUND_TEST in overrides.get("CLAUDE.md", [])


def test_root_governance_instruction_docs_have_explicit_selection_integrity_surface_rule() -> None:
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    rules = {
        rule["path_prefix"]: rule["required_test_targets"]
        for rule in policy.get("surface_rules", [])
        if isinstance(rule, dict) and rule.get("path_prefix")
    }
    assert "AGENTS.md" in rules
    assert "CLAUDE.md" in rules
    assert _BOUND_TEST in rules["AGENTS.md"]
    assert _BOUND_TEST in rules["CLAUDE.md"]


def test_doc_only_pr_diff_produces_allow_selection_integrity() -> None:
    selected = [_BOUND_TEST]
    result = evaluate_pytest_selection_integrity(
        changed_paths=["AGENTS.md", "CLAUDE.md"],
        selected_test_targets=selected,
        required_test_targets=selected,
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_POLICY_PATH,
        generated_at="2026-04-29T00:00:00Z",
    )
    assert result.decision == "ALLOW"
    assert result.blocking_reasons == []


def test_doc_only_pr_does_not_silently_fall_to_fallback_targets() -> None:
    # Reproduces the AEX-DOC-01 blocking signature: an empty selection paired
    # with PR_PYTEST_SELECTED_TARGETS_EMPTY must remain fail-closed even when
    # fallback is non-empty — guards against silent broadening if the mapping
    # regresses.
    result = evaluate_pytest_selection_integrity(
        changed_paths=["AGENTS.md"],
        selected_test_targets=[],
        required_test_targets=[],
        pytest_execution_record={
            "executed": True,
            "selection_reason_codes": ["PR_PYTEST_SELECTED_TARGETS_EMPTY"],
        },
        policy_path=_POLICY_PATH,
        generated_at="2026-04-29T00:00:00Z",
    )
    assert result.decision == "BLOCK"
    assert "PYTEST_SELECTION_FILTERING_DETECTED" in result.blocking_reasons
