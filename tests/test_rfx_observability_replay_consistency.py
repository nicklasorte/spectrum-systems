"""Tests for RFX OBS+REP consistency check (Part 5)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_observability_replay_consistency import (
    RFXObservabilityReplayConsistencyError,
    assert_rfx_observability_replay_consistency,
)


_OBS_SINGLE = {
    "obs_id": "obs-1",
    "trace_id": "trace-1",
    "artifact_linkage": ["lin:1", "rep:1"],
    "execution_path_coverage": ["AEX", "PQX"],
    "failure_logs": [],
}


def test_single_trace_with_matching_replay_passes() -> None:
    assert_rfx_observability_replay_consistency(
        obs=_OBS_SINGLE,
        replay_results=[{"trace_id": "trace-1", "match": True}],
    )


def test_missing_obs_blocks() -> None:
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_missing_trace_linkage"):
        assert_rfx_observability_replay_consistency(
            obs=None, replay_results=[{"trace_id": "trace-1", "match": True}],
        )


def test_obs_without_artifact_linkage_blocks() -> None:
    obs = {**_OBS_SINGLE, "artifact_linkage": []}
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_missing_trace_linkage"):
        assert_rfx_observability_replay_consistency(
            obs=obs, replay_results=[{"trace_id": "trace-1", "match": True}],
        )


def test_replay_referencing_unknown_trace_blocks() -> None:
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(
            obs=_OBS_SINGLE,
            replay_results=[{"trace_id": "trace-x", "match": True}],
        )


def test_obs_trace_without_replay_blocks() -> None:
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(
            obs=_OBS_SINGLE, replay_results=[],
        )


def test_multi_trace_dict_linkage_passes() -> None:
    obs = {
        "obs_id": "obs-2",
        "trace_id": "trace-a",
        "trace_ids": ["trace-a", "trace-b"],
        "artifact_linkage": {
            "trace-a": ["lin:a"],
            "trace-b": ["lin:b"],
        },
        "execution_path_coverage": ["AEX", "PQX"],
        "failure_logs": [],
    }
    replays = [
        {"trace_id": "trace-a", "match": True},
        {"trace_id": "trace-b", "match": True},
    ]
    assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_replay_row_without_any_trace_id_blocks() -> None:
    """A replay row carrying no trace_id alias must fail closed — the
    guard's invariant is that *every* replay record references an OBS
    trace, so silent drops are not acceptable."""
    replays = [
        {"trace_id": "trace-1", "match": True},
        {"match": False},  # untraceable row — no trace_id alias
    ]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(
            obs=_OBS_SINGLE, replay_results=replays,
        )


def test_replay_row_that_is_not_a_dict_blocks() -> None:
    replays = [
        {"trace_id": "trace-1", "match": True},
        "not-a-dict",  # malformed row
    ]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(
            obs=_OBS_SINGLE, replay_results=replays,
        )


def test_replay_row_using_source_trace_id_alias_passes() -> None:
    """The documented ``source_trace_id`` alias must continue to work."""
    replays = [{"source_trace_id": "trace-1", "match": True}]
    assert_rfx_observability_replay_consistency(
        obs=_OBS_SINGLE, replay_results=replays,
    )


def test_non_list_replay_results_blocks_deterministically() -> None:
    """Codex P1 regression (line 139): a non-list/non-None
    ``replay_results`` (e.g. an int) must surface
    ``rfx_trace_replay_inconsistency`` instead of raising raw TypeError
    from the iteration."""
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(
            obs=_OBS_SINGLE,
            replay_results=1,  # type: ignore[arg-type]
        )


def test_multi_trace_one_unlinked_blocks() -> None:
    obs = {
        "obs_id": "obs-2",
        "trace_id": "trace-a",
        "trace_ids": ["trace-a", "trace-b"],
        "artifact_linkage": {"trace-a": ["lin:a"]},  # trace-b has no linkage
        "execution_path_coverage": ["AEX", "PQX"],
        "failure_logs": [],
    }
    replays = [
        {"trace_id": "trace-a", "match": True},
        {"trace_id": "trace-b", "match": True},
    ]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_missing_trace_linkage"):
        assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)
