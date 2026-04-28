"""Tests for RFX-05 fix integrity proof.

Covers each weakening vector, valid fix path, fake-fix detection, and the
RT-13 red-team campaign with fix-follow-up + revalidation.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_fix_integrity_proof import (
    RFXFixIntegrityProofError,
    assert_rfx_fix_integrity_proof,
)


def _baseline() -> dict[str, dict[str, dict[str, object]]]:
    """Return a healthy baseline of all eight before/after snapshots."""
    return {
        "schema_coverage": {"before": {"coverage": 0.9}, "after": {"coverage": 0.9}},
        "test_coverage": {"before": {"count": 100}, "after": {"count": 100}},
        "eval_coverage": {
            "before": {"required_cases": ["a", "b"], "coverage": 0.95},
            "after": {"required_cases": ["a", "b"], "coverage": 0.95},
        },
        "replay_integrity": {"before": {"match": True}, "after": {"match": True}},
        "lineage_continuity": {"before": {"authenticity": "pass"}, "after": {"authenticity": "pass"}},
        "obs_slo_evidence": {
            "before": {"obs_completeness": "pass", "slo_status": "ok"},
            "after": {"obs_completeness": "pass", "slo_status": "ok"},
        },
        "certification_evidence_path": {
            "before": {"required_gates": ["EVL", "TPA", "CDE", "GOV"]},
            "after": {"required_gates": ["EVL", "TPA", "CDE", "GOV"]},
        },
        "authority_boundaries": {
            "before": {"ownership": {"EVL": "EVL", "GOV": "GOV"}},
            "after": {"ownership": {"EVL": "EVL", "GOV": "GOV"}},
        },
    }


def test_valid_fix_passes() -> None:
    proof = assert_rfx_fix_integrity_proof(**_baseline())
    assert proof["artifact_type"] == "rfx_fix_integrity_proof_record"
    assert proof["result"] == "preserved"


def test_schema_weakening_blocks() -> None:
    b = _baseline()
    b["schema_coverage"] = {"before": {"coverage": 0.9}, "after": {"coverage": 0.7}}
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_schema_weakened"):
        assert_rfx_fix_integrity_proof(**b)


def test_test_coverage_reduced_blocks() -> None:
    b = _baseline()
    b["test_coverage"] = {"before": {"count": 100}, "after": {"count": 90}}
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_test_coverage_reduced"):
        assert_rfx_fix_integrity_proof(**b)


def test_eval_gap_blocks_when_required_case_removed() -> None:
    b = _baseline()
    b["eval_coverage"] = {
        "before": {"required_cases": ["a", "b"]},
        "after": {"required_cases": ["a"]},
    }
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_eval_gap_introduced"):
        assert_rfx_fix_integrity_proof(**b)


def test_replay_regression_blocks() -> None:
    b = _baseline()
    b["replay_integrity"] = {"before": {"match": True}, "after": {"match": False}}
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_replay_regression"):
        assert_rfx_fix_integrity_proof(**b)


def test_lineage_break_blocks() -> None:
    b = _baseline()
    b["lineage_continuity"] = {
        "before": {"authenticity": "pass"},
        "after": {"authenticity": "fail"},
    }
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_lineage_break"):
        assert_rfx_fix_integrity_proof(**b)


def test_obs_slo_regression_blocks() -> None:
    b = _baseline()
    b["obs_slo_evidence"] = {
        "before": {"obs_completeness": "pass", "slo_status": "ok"},
        "after": {"obs_completeness": "incomplete", "slo_status": "ok"},
    }
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_obs_slo_regression"):
        assert_rfx_fix_integrity_proof(**b)


def test_certification_evidence_path_weakened_blocks() -> None:
    b = _baseline()
    b["certification_evidence_path"] = {
        "before": {"required_gates": ["EVL", "TPA", "CDE", "GOV"]},
        "after": {"required_gates": ["EVL", "GOV"]},
    }
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_certification_evidence_path_weakened"):
        assert_rfx_fix_integrity_proof(**b)


def test_authority_boundary_regression_blocks() -> None:
    b = _baseline()
    b["authority_boundaries"] = {
        "before": {"ownership": {"EVL": "EVL", "GOV": "GOV"}},
        "after": {"ownership": {"EVL": "RFX", "GOV": "GOV"}},
    }
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_authority_boundary_regression"):
        assert_rfx_fix_integrity_proof(**b)


def test_fake_fix_with_passing_tests_but_broken_replay_blocks() -> None:
    b = _baseline()
    b["test_coverage"] = {"before": {"count": 100}, "after": {"count": 100}}
    b["replay_integrity"] = {"before": {"match": True}, "after": {"match": False}}
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_replay_regression"):
        assert_rfx_fix_integrity_proof(**b)


def test_missing_snapshot_fails_closed() -> None:
    b = _baseline()
    b["schema_coverage"] = None  # type: ignore[assignment]
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_schema_weakened"):
        assert_rfx_fix_integrity_proof(**b)


# ---------------------------------------------------------------------------
# RT-13 red-team: attempt to pass fix that removes tests or weakens schema
# ---------------------------------------------------------------------------

def test_rt13_red_team_remove_tests_blocks_then_revalidates() -> None:
    """RT-13: a fix that removes tests must block.

    Then the fix-follow-up restores test coverage and revalidates.
    """
    bad = _baseline()
    bad["test_coverage"] = {"before": {"count": 100}, "after": {"count": 50}}
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_test_coverage_reduced"):
        assert_rfx_fix_integrity_proof(**bad)

    # Fix-follow-up + revalidation: tests restored.
    fixed = _baseline()
    fixed["test_coverage"] = {"before": {"count": 100}, "after": {"count": 105}}
    proof = assert_rfx_fix_integrity_proof(**fixed)
    assert proof["result"] == "preserved"


def test_rt13_red_team_weaken_schema_blocks_then_revalidates() -> None:
    """RT-13: a fix that weakens schema must block, then revalidate after fix."""
    bad = _baseline()
    bad["schema_coverage"] = {"before": {"coverage": 0.9}, "after": {"coverage": 0.6}}
    with pytest.raises(RFXFixIntegrityProofError, match="rfx_schema_weakened"):
        assert_rfx_fix_integrity_proof(**bad)

    fixed = _baseline()
    proof = assert_rfx_fix_integrity_proof(**fixed)
    assert proof["result"] == "preserved"
