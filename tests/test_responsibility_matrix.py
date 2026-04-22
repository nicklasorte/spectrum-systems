"""Tests for Phase 5.3: ResponsibilityMatrix."""

import pytest

from spectrum_systems.governance.responsibility_matrix import ResponsibilityMatrix


@pytest.fixture()
def matrix():
    return ResponsibilityMatrix()


# ---------------------------------------------------------------------------
# test_responsibilities_assigned
# ---------------------------------------------------------------------------
def test_responsibilities_assigned(matrix):
    matrix.assign_responsibility("execution", "PQX")
    matrix.assign_responsibility("orchestration", "TLC")
    assert matrix.get_owner("execution") == "PQX"
    assert matrix.get_owner("orchestration") == "TLC"


# ---------------------------------------------------------------------------
# test_no_overlapping_ownership
# ---------------------------------------------------------------------------
def test_no_overlapping_ownership(matrix):
    matrix.assign_responsibility("execution", "PQX")
    with pytest.raises(ValueError, match="already owned"):
        matrix.assign_responsibility("execution", "TLC")

    ok, overlaps = matrix.validate_no_overlap()
    assert ok is True
    assert overlaps == []


# ---------------------------------------------------------------------------
# test_clarity_audit
# ---------------------------------------------------------------------------
def test_clarity_audit(matrix):
    matrix.assign_responsibility("execution", "PQX")
    matrix.assign_responsibility("enforcement", "SEL")
    audit = matrix.audit()
    assert audit == {"execution": "PQX", "enforcement": "SEL"}


# ---------------------------------------------------------------------------
# test_get_owned_by
# ---------------------------------------------------------------------------
def test_get_owned_by(matrix):
    matrix.assign_responsibility("execution", "PQX")
    matrix.assign_responsibility("retry", "PQX")
    matrix.assign_responsibility("enforcement", "SEL")
    owned = matrix.get_owned_by("PQX")
    assert "execution" in owned
    assert "retry" in owned
    assert "enforcement" not in owned


# ---------------------------------------------------------------------------
# test_unknown_responsibility_raises
# ---------------------------------------------------------------------------
def test_unknown_responsibility_raises(matrix):
    with pytest.raises(KeyError):
        matrix.get_owner("nonexistent")
