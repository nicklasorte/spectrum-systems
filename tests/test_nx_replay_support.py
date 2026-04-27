"""NX-07..09: Replay support primitives + adversarial fixtures.

These tests exercise the new ``replay_support`` module to ensure replay
mismatch, missing-record, missing-hash, and non-replayable artifact paths
all produce canonical reason codes and ``decision = "block"``.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.replay.replay_support import (
    CANONICAL_REASON_CODES,
    ReplaySupportError,
    build_replay_coverage_summary,
    build_replay_record,
    canonical_hash,
    classify_replay_mismatch,
    is_artifact_replayable,
)


def _record(input_payload, output_payload, **kwargs) -> dict:
    base = build_replay_record(
        replay_id="rpl-1",
        original_run_id="run-orig",
        trace_id="trace-1",
        input_payload=input_payload,
        output_payload=output_payload,
        artifact_type="eval_result",
    )
    base.update(kwargs)
    return base


def test_canonical_hash_is_deterministic_for_dicts() -> None:
    a = canonical_hash({"a": 1, "b": 2})
    b = canonical_hash({"b": 2, "a": 1})
    assert a == b


def test_canonical_hash_distinguishes_distinct_payloads() -> None:
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_build_replay_record_rejects_blank_fields() -> None:
    with pytest.raises(ReplaySupportError):
        build_replay_record(
            replay_id="",
            original_run_id="r",
            trace_id="t",
            input_payload={"x": 1},
            output_payload={"y": 1},
            artifact_type="eval_result",
        )


def test_classify_replay_match() -> None:
    rec = _record({"in": 1}, {"out": 1})
    rec_replay = _record({"in": 1}, {"out": 1})
    res = classify_replay_mismatch(original=rec, replayed=rec_replay)
    assert res["reason_code"] == "REPLAY_HASH_MATCH"
    assert res["decision"] == "allow"
    assert res["consistency_status"] == "match"


# ---- NX-08: red-team replay integrity fixtures ----


def test_red_team_replay_hash_mismatch_output_only_blocks() -> None:
    rec = _record({"in": 1}, {"out": 1})
    rec_replay = _record({"in": 1}, {"out": 2})
    res = classify_replay_mismatch(original=rec, replayed=rec_replay)
    assert res["reason_code"] == "REPLAY_HASH_MISMATCH_OUTPUT"
    assert res["decision"] == "block"
    assert res["input_hash_match"] is True
    assert res["output_hash_match"] is False
    assert "deterministic" in res["debug_message"]


def test_red_team_replay_hash_mismatch_input_only_blocks() -> None:
    rec = _record({"in": 1}, {"out": 1})
    rec_replay = _record({"in": 2}, {"out": 1})
    res = classify_replay_mismatch(original=rec, replayed=rec_replay)
    assert res["reason_code"] == "REPLAY_HASH_MISMATCH_INPUT"
    assert res["decision"] == "block"


def test_red_team_replay_hash_mismatch_both_blocks() -> None:
    rec = _record({"in": 1}, {"out": 1})
    rec_replay = _record({"in": 2}, {"out": 2})
    res = classify_replay_mismatch(original=rec, replayed=rec_replay)
    assert res["reason_code"] == "REPLAY_HASH_MISMATCH_BOTH"
    assert res["decision"] == "block"
    assert "non-determinism" in res["debug_message"]


def test_red_team_missing_original_record_blocks() -> None:
    res = classify_replay_mismatch(original=None, replayed=_record({"in": 1}, {"out": 1}))
    assert res["reason_code"] == "REPLAY_MISSING_ORIGINAL_RECORD"
    assert res["decision"] == "block"


def test_red_team_missing_replay_record_blocks() -> None:
    res = classify_replay_mismatch(original=_record({"in": 1}, {"out": 1}), replayed=None)
    assert res["reason_code"] == "REPLAY_MISSING_ORIGINAL_RECORD"
    assert res["decision"] == "block"


def test_red_team_missing_input_hash_blocks() -> None:
    rec = _record({"in": 1}, {"out": 1})
    rec_replay = _record({"in": 1}, {"out": 1})
    rec_replay["input_hash"] = ""
    res = classify_replay_mismatch(original=rec, replayed=rec_replay)
    assert res["reason_code"] == "REPLAY_MISSING_INPUT_HASH"
    assert res["decision"] == "block"


def test_red_team_missing_output_hash_blocks() -> None:
    rec = _record({"in": 1}, {"out": 1})
    rec_replay = _record({"in": 1}, {"out": 1})
    rec_replay["output_hash"] = ""
    res = classify_replay_mismatch(original=rec, replayed=rec_replay)
    assert res["reason_code"] == "REPLAY_MISSING_OUTPUT_HASH"
    assert res["decision"] == "block"


def test_red_team_non_replayable_artifact_classification() -> None:
    """An artifact lacking both hashes and trace lineage is non-replayable."""
    replayable, reason = is_artifact_replayable({"artifact_type": "eval_result"})
    assert replayable is False
    assert reason.startswith("REPLAY_NON_REPLAYABLE_ARTIFACT")


def test_artifact_with_lineage_is_replayable() -> None:
    replayable, _ = is_artifact_replayable(
        {"artifact_type": "eval_result", "trace_id": "t", "run_id": "r"}
    )
    assert replayable is True


def test_artifact_with_hashes_is_replayable() -> None:
    replayable, _ = is_artifact_replayable(
        {"artifact_type": "eval_result", "input_hash": "a", "output_hash": "b"}
    )
    assert replayable is True


def test_replay_coverage_summary_blocks_when_any_mismatch() -> None:
    records = [
        {"consistency_status": "match", "reason_code": "REPLAY_HASH_MATCH"},
        {"consistency_status": "mismatch", "reason_code": "REPLAY_HASH_MISMATCH_OUTPUT"},
        {"consistency_status": "match", "reason_code": "REPLAY_HASH_MATCH"},
    ]
    summary = build_replay_coverage_summary(records)
    assert summary["status"] == "blocked"
    assert summary["mismatch"] == 1
    assert summary["match"] == 2
    assert summary["match_rate"] == pytest.approx(2 / 3)
    assert summary["reason_codes"]["REPLAY_HASH_MISMATCH_OUTPUT"] == 1


def test_replay_coverage_summary_degrades_on_indeterminate() -> None:
    records = [
        {"consistency_status": "match", "reason_code": "REPLAY_HASH_MATCH"},
        {"consistency_status": "indeterminate", "reason_code": "REPLAY_MISSING_INPUT_HASH"},
    ]
    summary = build_replay_coverage_summary(records)
    assert summary["status"] == "degraded"


def test_replay_coverage_empty_blocks() -> None:
    summary = build_replay_coverage_summary([])
    assert summary["status"] == "blocked"
    assert summary["total"] == 0


def test_canonical_reason_codes_complete_set() -> None:
    """Every reason code returned by classify_replay_mismatch must be canonical."""
    cases = [
        classify_replay_mismatch(original=None, replayed=_record({"a": 1}, {"b": 1})),
        classify_replay_mismatch(original=_record({"a": 1}, {"b": 1}), replayed=None),
        classify_replay_mismatch(
            original=_record({"a": 1}, {"b": 1}),
            replayed=_record({"a": 1}, {"b": 2}),
        ),
        classify_replay_mismatch(
            original=_record({"a": 1}, {"b": 1}),
            replayed=_record({"a": 2}, {"b": 1}),
        ),
        classify_replay_mismatch(
            original=_record({"a": 1}, {"b": 1}),
            replayed=_record({"a": 2}, {"b": 2}),
        ),
        classify_replay_mismatch(
            original=_record({"a": 1}, {"b": 1}),
            replayed=_record({"a": 1}, {"b": 1}),
        ),
    ]
    for result in cases:
        assert result["reason_code"] in CANONICAL_REASON_CODES, result
