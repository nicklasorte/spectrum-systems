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
