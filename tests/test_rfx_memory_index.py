"""Tests for RFX-15 institutional-memory layer."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_memory_index import (
    RFXMemoryIndexError,
    build_rfx_memory_index_record,
    lookup_rfx_memory,
)


def _eval_case() -> dict[str, object]:
    return {
        "artifact_type": "rfx_failure_derived_eval_case",
        "case_id": "rfx-eval-aaa",
        "reason_code": "rfx_replay_mismatch",
        "source_failure_refs": ["fail-1"],
    }


def _trend_report() -> dict[str, object]:
    return {
        "artifact_type": "rfx_trend_report",
        "report_id": "rfx-trend-bbb",
        "lineage_refs": ["fail-1", "fail-2"],
        "recurring_reason_codes": {"rfx_replay_mismatch": 3},
    }


def test_artifacts_indexed_by_reason_code() -> None:
    index = build_rfx_memory_index_record(artifacts=[_eval_case(), _trend_report()])
    assert index["entry_count"] == 2
    assert "rfx_failure_derived_eval_case" in index["by_artifact_type"]
    assert "rfx_replay_mismatch" in index["by_reason_code"]


def test_lookup_returns_source_refs() -> None:
    index = build_rfx_memory_index_record(artifacts=[_eval_case()])
    result = lookup_rfx_memory(index=index, reason_code="rfx_replay_mismatch")
    assert result["match_count"] == 1
    assert "rfx-eval-aaa" in result["matched_artifact_ids"]


def test_ambiguous_lookup_blocks() -> None:
    index = build_rfx_memory_index_record(artifacts=[_eval_case()])
    with pytest.raises(RFXMemoryIndexError, match="rfx_memory_lookup_ambiguous"):
        lookup_rfx_memory(index=index)


def test_missing_lineage_blocks_index() -> None:
    bad = {"artifact_type": "rfx_trend_report", "report_id": "rfx-trend-no-lineage"}
    with pytest.raises(RFXMemoryIndexError, match="rfx_memory_lineage_missing"):
        build_rfx_memory_index_record(artifacts=[bad])


def test_unsupported_type_blocks() -> None:
    bad = {"artifact_type": "unknown_type", "id": "x"}
    with pytest.raises(RFXMemoryIndexError, match="rfx_memory_index_invalid"):
        build_rfx_memory_index_record(artifacts=[bad])


def test_empty_corpus_blocks() -> None:
    with pytest.raises(RFXMemoryIndexError, match="rfx_memory_source_missing"):
        build_rfx_memory_index_record(artifacts=[])


# ---------------------------------------------------------------------------
# RT-23 red-team: index unsupported memory without source refs
# ---------------------------------------------------------------------------


def test_rt23_red_team_no_source_refs_blocks_then_revalidates() -> None:
    bad = {"artifact_type": "rfx_trend_report", "report_id": "rfx-trend-only"}
    with pytest.raises(RFXMemoryIndexError, match="rfx_memory_lineage_missing"):
        build_rfx_memory_index_record(artifacts=[bad])

    fixed = {
        "artifact_type": "rfx_trend_report",
        "report_id": "rfx-trend-only",
        "lineage_refs": ["fail-1"],
    }
    index = build_rfx_memory_index_record(artifacts=[fixed])
    assert index["entry_count"] == 1
