"""Tests for Phase 3.4: ConsistencyChecker."""

import pytest

from spectrum_systems.consistency.consistency_checker import ConsistencyChecker


@pytest.fixture()
def checker():
    return ConsistencyChecker()


_ARTIFACT = {"artifact_id": "art-1", "value": 42, "status": "ok"}


# ---------------------------------------------------------------------------
# test_consistent_artifacts_pass
# ---------------------------------------------------------------------------
def test_consistent_artifacts_pass(checker):
    runs = [dict(_ARTIFACT), dict(_ARTIFACT), dict(_ARTIFACT)]
    ok, report = checker.check_artifact_consistency("art-1", runs)
    assert ok is True
    assert report["consistency"] is True
    assert report["runs_checked"] == 3


# ---------------------------------------------------------------------------
# test_inconsistent_artifacts_detected
# ---------------------------------------------------------------------------
def test_inconsistent_artifacts_detected(checker):
    run1 = {"artifact_id": "art-2", "value": 1}
    run2 = {"artifact_id": "art-2", "value": 2}  # Different value
    ok, report = checker.check_artifact_consistency("art-2", [run1, run2])
    assert ok is False
    assert report["consistency"] is False
    assert "inconsistency" in report["reason"].lower()


# ---------------------------------------------------------------------------
# test_lineage_chain_integrity
# ---------------------------------------------------------------------------
def test_lineage_chain_integrity(checker):
    chain = [
        {"artifact_id": "input-1"},
        {"artifact_id": "exec-1", "produced_from": ["input-1"]},
        {"artifact_id": "output-1", "produced_from": ["exec-1"]},
    ]
    ok, report = checker.check_lineage_integrity("output-1", chain)
    assert ok is True
    assert report["lineage_integrity"] is True
    assert report["chain_length"] == 3


# ---------------------------------------------------------------------------
# test_lineage_break_detected
# ---------------------------------------------------------------------------
def test_lineage_break_detected(checker):
    chain = [
        {"artifact_id": "input-1"},
        {"artifact_id": "exec-1", "produced_from": ["WRONG-ID"]},  # broken link
    ]
    ok, report = checker.check_lineage_integrity("exec-1", chain)
    assert ok is False
    assert report["lineage_integrity"] is False
    assert "broken_link" in report


# ---------------------------------------------------------------------------
# test_promotion_blocked_on_inconsistency
# ---------------------------------------------------------------------------
def test_promotion_blocked_on_inconsistency(checker):
    run1 = {"artifact_id": "art-X", "data": "v1"}
    run2 = {"artifact_id": "art-X", "data": "v2"}
    ok, _ = checker.check_artifact_consistency("art-X", [run1, run2])
    assert ok is False, "Inconsistent artifact must block promotion"
