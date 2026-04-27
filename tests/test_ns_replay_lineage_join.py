"""NS-19..21: replay/lineage join contract — broken causality red team."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.lineage.replay_lineage_join import (
    CANONICAL_JOIN_REASON_CODES,
    build_replay_lineage_join_summary,
    verify_replay_lineage_join,
)


def _good_replay() -> dict:
    return {
        "replay_id": "rpl-1",
        "trace_id": "tA",
        "original_run_id": "rA",
        "target_artifact_id": "out-1",
        "output_hash": "deadbeef" * 4,
        "referenced_lineage_summary_id": "lin-sum-1",
    }


def _good_lineage() -> dict:
    return {
        "summary_id": "lin-sum-1",
        "trace_id": "tA",
        "run_id": "rA",
        "replay_record_ids": ["rpl-1"],
        "artifact_ids": ["input-1", "exec-1", "out-1"],
        "output_hash": "deadbeef" * 4,
        "parent_chain": [
            {"artifact_id": "input-1", "parent_id": ""},
            {"artifact_id": "exec-1", "parent_id": "input-1"},
            {"artifact_id": "out-1", "parent_id": "exec-1"},
        ],
    }


def test_full_join_allows() -> None:
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=_good_lineage()
    )
    assert res["decision"] == "allow"
    assert res["reason_code"] == "JOIN_OK"


# ---- NS-20: red team — broken causality ----


def test_red_team_replay_to_lineage_link_broken_blocks() -> None:
    rep = _good_replay()
    rep["referenced_lineage_summary_id"] = "wrong-summary"
    res = verify_replay_lineage_join(
        replay_record=rep, lineage_summary=_good_lineage()
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_LINEAGE_NOT_REFERENCED_FROM_REPLAY"


def test_red_team_lineage_to_replay_link_broken_blocks() -> None:
    lin = _good_lineage()
    lin["replay_record_ids"] = ["other-replay"]
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=lin
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_REPLAY_NOT_LINKED_FROM_LINEAGE"


def test_red_team_artifact_hash_continuity_broken_blocks() -> None:
    lin = _good_lineage()
    lin["output_hash"] = "00" * 16
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=lin
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_ARTIFACT_HASH_DISCONTINUITY"


def test_red_team_trace_id_continuity_broken_blocks() -> None:
    lin = _good_lineage()
    lin["trace_id"] = "tDIFFERENT"
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=lin
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_TRACE_ID_MISMATCH"


def test_red_team_run_id_continuity_broken_blocks() -> None:
    lin = _good_lineage()
    lin["run_id"] = "rDIFFERENT"
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=lin
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_RUN_ID_MISMATCH"


def test_red_team_parent_artifact_chain_break_blocks() -> None:
    lin = _good_lineage()
    # Break: out-1 references parent that's never declared first
    lin["parent_chain"] = [
        {"artifact_id": "input-1", "parent_id": ""},
        {"artifact_id": "out-1", "parent_id": "ghost-parent"},
    ]
    lin["artifact_ids"] = ["input-1", "out-1"]
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=lin
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_PARENT_CHAIN_BREAK"


def test_red_team_replay_missing_blocks() -> None:
    res = verify_replay_lineage_join(
        replay_record=None, lineage_summary=_good_lineage()
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_REPLAY_MISSING"


def test_red_team_lineage_missing_blocks() -> None:
    res = verify_replay_lineage_join(
        replay_record=_good_replay(), lineage_summary=None
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_LINEAGE_MISSING"


def test_red_team_target_artifact_not_in_lineage_blocks() -> None:
    rep = _good_replay()
    rep["target_artifact_id"] = "ghost-out"
    res = verify_replay_lineage_join(
        replay_record=rep, lineage_summary=_good_lineage()
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "JOIN_PARENT_CHAIN_BREAK"


# ---- helper: build_replay_lineage_join_summary ----


def test_build_summary_collects_replay_ids() -> None:
    summary = build_replay_lineage_join_summary(
        summary_id="lin-1",
        trace_id="tA",
        run_id="rA",
        replay_records=[{"replay_id": "rpl-1"}, {"replay_id": "rpl-2"}],
        artifact_ids=["a", "b"],
    )
    assert summary["replay_record_ids"] == ["rpl-1", "rpl-2"]
    assert summary["artifact_ids"] == ["a", "b"]


def test_canonical_reason_codes_finite() -> None:
    assert "JOIN_OK" in CANONICAL_JOIN_REASON_CODES
    assert "JOIN_LINEAGE_NOT_REFERENCED_FROM_REPLAY" in CANONICAL_JOIN_REASON_CODES
    assert "JOIN_REPLAY_NOT_LINKED_FROM_LINEAGE" in CANONICAL_JOIN_REASON_CODES
