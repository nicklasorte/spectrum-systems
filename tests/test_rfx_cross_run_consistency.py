"""Tests for RFX-10 cross-run consistency."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_cross_run_consistency import (
    RFXCrossRunConsistencyError,
    assert_rfx_cross_run_consistency,
)


def _run(
    *,
    run_id: str,
    cde_status: str = "ready",
    gov_status: str = "certified",
    replay_match: bool = True,
    policy_version: str = "pol-v1",
    metadata: dict[str, object] | None = None,
    inputs: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "inputs": inputs or {"evidence": "alpha", "policy_version": policy_version},
        "cde": {"status": cde_status, "decision_id": f"cde-{run_id}"},
        "gov": {"status": gov_status},
        "replay": {"match": replay_match},
        "policy_version": policy_version,
        "metadata": metadata or {"timestamp": run_id},
    }


def test_equivalent_runs_match() -> None:
    record = assert_rfx_cross_run_consistency(
        runs=[_run(run_id="r1"), _run(run_id="r2"), _run(run_id="r3")]
    )
    assert record["artifact_type"] == "rfx_cross_run_consistency_record"
    assert record["result"] == "consistent"


def test_changed_policy_version_explains_difference() -> None:
    runs = [
        _run(run_id="r1", policy_version="pol-v1", inputs={"evidence": "alpha", "policy_version": "pol-v1"}),
        _run(run_id="r2", policy_version="pol-v2", inputs={"evidence": "alpha", "policy_version": "pol-v2"}),
    ]
    # Different policy_version → different fingerprint → not in same cluster.
    record = assert_rfx_cross_run_consistency(runs=runs)
    assert record["result"] == "consistent"


def test_unexplained_difference_blocks() -> None:
    runs = [
        _run(run_id="r1", cde_status="ready"),
        _run(run_id="r2", cde_status="not_ready"),
    ]
    with pytest.raises(RFXCrossRunConsistencyError, match="rfx_decision_volatility"):
        assert_rfx_cross_run_consistency(runs=runs)


def test_replay_mismatch_blocks() -> None:
    runs = [
        _run(run_id="r1", replay_match=True),
        _run(run_id="r2", replay_match=False),
    ]
    with pytest.raises(RFXCrossRunConsistencyError, match="rfx_replay_cross_run_mismatch"):
        assert_rfx_cross_run_consistency(runs=runs)


def test_too_few_runs_blocks() -> None:
    with pytest.raises(RFXCrossRunConsistencyError, match="rfx_cross_run_inconsistency"):
        assert_rfx_cross_run_consistency(runs=[_run(run_id="r1")])


# ---------------------------------------------------------------------------
# RT-18 red-team: hide inconsistent run by changing non-material metadata
# ---------------------------------------------------------------------------


def test_rt18_red_team_non_material_metadata_does_not_mask() -> None:
    runs = [
        _run(run_id="r1", cde_status="ready", metadata={"timestamp": "2026-01-01", "tag": "x"}),
        _run(run_id="r2", cde_status="not_ready", metadata={"timestamp": "2026-04-04", "tag": "y"}),
    ]
    # Same material inputs, different CDE status → must still be detected.
    with pytest.raises(RFXCrossRunConsistencyError, match="rfx_decision_volatility"):
        assert_rfx_cross_run_consistency(runs=runs)


def test_rt18_fix_follow_up_revalidation() -> None:
    runs = [_run(run_id="r1"), _run(run_id="r2")]
    record = assert_rfx_cross_run_consistency(runs=runs)
    assert record["result"] == "consistent"
