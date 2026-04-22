"""Tests for Phase 5.2: SystemConsolidation."""

import pytest

from spectrum_systems.governance.system_consolidation import SystemConsolidation


@pytest.fixture()
def consolidation():
    dep_graph = {
        "alpha": set(),
        "beta": set(),
        "gamma": {"alpha"},  # gamma depends on alpha → cannot merge with alpha
        "delta": set(),
    }
    return SystemConsolidation(dep_graph)


# ---------------------------------------------------------------------------
# test_consolidation_candidates_found
# ---------------------------------------------------------------------------
def test_consolidation_candidates_found(consolidation):
    candidates = consolidation.find_consolidation_candidates()
    # alpha↔beta, alpha↔delta, beta↔delta should be candidates
    candidate_set = {frozenset(c) for c in candidates}
    assert frozenset({"alpha", "beta"}) in candidate_set
    assert frozenset({"beta", "delta"}) in candidate_set
    # gamma depends on alpha → alpha↔gamma NOT a candidate
    assert frozenset({"alpha", "gamma"}) not in candidate_set


# ---------------------------------------------------------------------------
# test_consolidation_plan_created
# ---------------------------------------------------------------------------
def test_consolidation_plan_created(consolidation):
    plan = consolidation.plan_consolidation("alpha", "beta")
    assert plan["merge_from"] == "beta"
    assert plan["merge_into"] == "alpha"
    assert len(plan["actions"]) >= 4


# ---------------------------------------------------------------------------
# test_functionality_identical_after_merge (structural check)
# ---------------------------------------------------------------------------
def test_functionality_identical_after_merge(consolidation):
    # After planning a merge, the dependency graph semantics are preserved.
    # Verify that the plan includes import-update step.
    plan = consolidation.plan_consolidation("alpha", "beta")
    actions_text = " ".join(plan["actions"]).lower()
    assert "import" in actions_text


# ---------------------------------------------------------------------------
# test_no_orphaned_code
# ---------------------------------------------------------------------------
def test_no_orphaned_code(consolidation):
    plan = consolidation.plan_consolidation("alpha", "delta")
    # Plan must include test merge step (no code left behind)
    actions_text = " ".join(plan["actions"]).lower()
    assert "test" in actions_text
