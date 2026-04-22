"""Tests for Phase 5.1: SystemElimination."""

import pytest

from spectrum_systems.governance.system_elimination import SystemElimination


_JUSTIFICATIONS = {
    "sys-A": {
        "prevents": ["data loss"],
        "improves": ["throughput"],
    },
    "sys-B": {
        "prevents": [],
        "improves": [],
    },
    "sys-C": {
        "improves": ["latency"],
    },
    "sys-D": {},  # Completely empty — unjustified
}


@pytest.fixture()
def elim():
    return SystemElimination(_JUSTIFICATIONS)


# ---------------------------------------------------------------------------
# test_unjustified_systems_identified
# ---------------------------------------------------------------------------
def test_unjustified_systems_identified(elim):
    unjustified = elim.identify_unjustified_systems()
    assert "sys-B" in unjustified
    assert "sys-D" in unjustified
    assert "sys-A" not in unjustified
    assert "sys-C" not in unjustified


# ---------------------------------------------------------------------------
# test_elimination_plan_created
# ---------------------------------------------------------------------------
def test_elimination_plan_created(elim):
    plan = elim.plan_elimination("sys-B")
    assert plan["system_id"] == "sys-B"
    assert len(plan["actions"]) >= 4
    assert any("regression" in a.lower() for a in plan["actions"])


# ---------------------------------------------------------------------------
# test_no_orphaned_dependencies
# ---------------------------------------------------------------------------
def test_no_orphaned_dependencies(elim):
    dep_graph = {
        "sys-A": ["sys-C"],
        "sys-C": [],
        "sys-D": [],
    }
    # sys-B has no dependents → safe to remove
    assert elim.validate_no_orphaned_dependencies("sys-B", dep_graph) is True


def test_has_orphaned_dependencies(elim):
    dep_graph = {
        "sys-A": ["sys-B"],  # A depends on B
    }
    assert elim.validate_no_orphaned_dependencies("sys-B", dep_graph) is False
