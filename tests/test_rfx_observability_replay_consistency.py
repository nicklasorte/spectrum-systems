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


def test_dict_form_coverage_keys_are_collected_as_trace_ids() -> None:
    """Codex P1 regression (line 50): when execution_path_coverage is a
    dict keyed by trace_id, every key must contribute to the OBS trace
    set so the OBS↔REP cross-check sees secondary traces."""
    obs = {
        "obs_id": "obs-multi",
        "trace_id": "trace-a",
        "execution_path_coverage": {
            "trace-a": ["AEX", "PQX"],
            "trace-b": ["AEX", "PQX"],
        },
        "artifact_linkage": {
            "trace-a": ["lin:a"],
            "trace-b": ["lin:b"],
        },
        "failure_logs": [],
    }
    # Replay corpus is missing trace-b — must trigger inconsistency.
    replays = [{"trace_id": "trace-a", "match": True}]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_metadata_form_coverage_dict_does_not_invent_synthetic_traces() -> None:
    """Codex P2 regression (line 67): dict-form coverage that carries an
    explicit ``trace_ids`` list is the metadata schema; sibling keys
    (``segments``, etc.) are NOT trace identifiers and must not be added
    to the OBS trace set."""
    obs = {
        "obs_id": "obs-meta",
        "trace_id": "trace-1",
        "execution_path_coverage": {
            "trace_ids": ["trace-1"],
            "segments": {"phase-a": ["AEX", "PQX"]},
            "summary": "ok",
        },
        "artifact_linkage": ["lin:1"],
        "failure_logs": [],
    }
    replays = [{"trace_id": "trace-1", "match": True}]
    # Must not raise — ``segments``/``summary`` are metadata, not synthetic
    # traces; trace-1 has matching replay.
    assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_dict_linkage_bucket_with_empty_inner_values_blocks() -> None:
    """Codex P1 regression (line 113): a dict bucket whose inner values
    are themselves empty (e.g. ``{"t1": {"lin": []}}``) carries no actual
    artifact references and must NOT be treated as linked."""
    obs = {
        "obs_id": "obs-empty-inner",
        "trace_id": "trace-1",
        "execution_path_coverage": ["AEX", "PQX"],
        "artifact_linkage": {"trace-1": {"lin": [], "rep": None}},
        "failure_logs": [],
    }
    replays = [{"trace_id": "trace-1", "match": True}]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_missing_trace_linkage"):
        assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_replay_row_alias_matches_when_primary_trace_id_is_stale() -> None:
    """Codex P2 regression (line 132): a migration-era replay row with a
    stale ``trace_id`` plus a correct ``source_trace_id`` matching an OBS
    trace must pass — every alias is considered, not just the first."""
    obs = {
        "obs_id": "obs-alias",
        "trace_id": "trace-1",
        "execution_path_coverage": ["AEX"],
        "artifact_linkage": ["lin:1"],
        "failure_logs": [],
    }
    replays = [{
        "trace_id": "trace-stale",
        "source_trace_id": "trace-1",
        "match": True,
    }]
    # Must not raise — source_trace_id matches the OBS trace even though
    # trace_id is stale.
    assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_replay_row_with_all_stale_aliases_blocks() -> None:
    """Sanity counterpart: if ALL aliases miss, the row still fails."""
    obs = {
        "obs_id": "obs-alias",
        "trace_id": "trace-1",
        "execution_path_coverage": ["AEX"],
        "artifact_linkage": ["lin:1"],
        "failure_logs": [],
    }
    replays = [{
        "trace_id": "trace-stale",
        "source_trace_id": "trace-also-stale",
        "match": True,
    }]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_dict_linkage_bucket_with_dict_value_is_accepted_as_present() -> None:
    """Codex P2 regression (line 95): LOOP-08 accepts non-empty dict
    buckets in artifact_linkage, so the OBS+REP consistency guard must
    treat them as "linkage present" too — otherwise the two guards
    disagree on accepted OBS shapes and create false blocks."""
    obs = {
        "obs_id": "obs-dict-bucket",
        "trace_id": "trace-1",
        "execution_path_coverage": ["AEX", "PQX"],
        "artifact_linkage": {"trace-1": {"lin": "1", "rep": "1"}},
        "failure_logs": [],
    }
    replays = [{"trace_id": "trace-1", "match": True}]
    # Must not raise — non-empty dict bucket counts as present linkage.
    assert_rfx_observability_replay_consistency(obs=obs, replay_results=replays)


def test_dict_form_artifact_linkage_keys_are_collected_as_trace_ids() -> None:
    """Same defense via artifact_linkage dict keys: a trace declared only
    in linkage must still be cross-checked against the replay corpus."""
    obs = {
        "obs_id": "obs-multi-2",
        "trace_id": "trace-a",
        "execution_path_coverage": ["AEX", "PQX"],
        "artifact_linkage": {
            "trace-a": ["lin:a"],
            "trace-c": ["lin:c"],
        },
        "failure_logs": [],
    }
    replays = [{"trace_id": "trace-a", "match": True}]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
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
