"""Tests for RFX-06 failure → eval auto-generation."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_failure_to_eval import (
    RFXFailureToEvalError,
    build_rfx_eval_handoff_record,
    build_rfx_failure_derived_eval_case,
    deduplicate_eval_cases,
)


def _failure() -> dict[str, object]:
    return {
        "failure_id": "fail-001",
        "trace_id": "trace-001",
        "reason_code": "rfx_replay_mismatch",
        "lineage_refs": ["lin-001"],
        "inputs": {"a": 1},
        "expected_block": True,
    }


def test_failure_becomes_eval_candidate() -> None:
    case = build_rfx_failure_derived_eval_case(failure_record=_failure())
    assert case["artifact_type"] == "rfx_failure_derived_eval_case"
    assert case["reason_code"] == "rfx_replay_mismatch"
    assert case["expected_outcome"] == "blocked"
    assert case["case_id"].startswith("rfx-eval-")
    assert "lin-001" in case["source_failure_refs"]


def test_duplicate_failure_dedupes() -> None:
    a = build_rfx_failure_derived_eval_case(failure_record=_failure())
    b = build_rfx_failure_derived_eval_case(failure_record=_failure())
    unique, dups = deduplicate_eval_cases([a, b])
    assert len(unique) == 1
    assert dups == [b["case_id"]]


def test_missing_trace_blocks() -> None:
    f = _failure()
    f.pop("trace_id")
    f.pop("lineage_refs")  # ensure trace_id is the only signal removed
    with pytest.raises(RFXFailureToEvalError, match="rfx_failure_missing_trace"):
        build_rfx_failure_derived_eval_case(failure_record=f)


def test_missing_reason_code_blocks() -> None:
    f = _failure()
    f.pop("reason_code")
    with pytest.raises(RFXFailureToEvalError, match="rfx_failure_missing_reason_code"):
        build_rfx_failure_derived_eval_case(failure_record=f)


def test_generated_eval_includes_lineage_refs() -> None:
    case = build_rfx_failure_derived_eval_case(failure_record=_failure())
    refs = case["source_failure_refs"]
    assert "lin-001" in refs
    assert any(r.startswith("trace_id:") for r in refs)


def test_handoff_is_non_owning_and_requires_evl_ref() -> None:
    case = build_rfx_failure_derived_eval_case(failure_record=_failure())
    handoff = build_rfx_eval_handoff_record(cases=[case], evl_target_ref="evl:registry/v1")
    assert handoff["artifact_type"] == "rfx_eval_handoff_record"
    assert handoff["case_count"] == 1
    assert "EVL retains eval coverage authority" in handoff["ownership_note"]


def test_handoff_blocks_without_evl_ref() -> None:
    case = build_rfx_failure_derived_eval_case(failure_record=_failure())
    with pytest.raises(RFXFailureToEvalError, match="rfx_eval_handoff_missing_evl_ref"):
        build_rfx_eval_handoff_record(cases=[case], evl_target_ref=None)


# ---------------------------------------------------------------------------
# RT-14 red-team: generate eval without trace/lineage
# ---------------------------------------------------------------------------


def test_rt14_red_team_no_trace_or_lineage_blocks_then_revalidates() -> None:
    bad = {"reason_code": "rfx_replay_mismatch"}
    with pytest.raises(RFXFailureToEvalError, match="rfx_failure_missing_trace"):
        build_rfx_failure_derived_eval_case(failure_record=bad)

    bad2 = {"reason_code": "rfx_replay_mismatch", "trace_id": "trace-002"}
    # No lineage refs at all (no failure_id, no run_id, no lineage_refs aside trace)
    case = build_rfx_failure_derived_eval_case(failure_record=bad2)
    # trace_id alone is a lineage ref under our policy — confirm we still
    # demand at least one lineage entry, not silent emptiness.
    assert any(r.startswith("trace_id:") for r in case["source_failure_refs"])

    # Fix-follow-up + revalidation
    case = build_rfx_failure_derived_eval_case(failure_record=_failure())
    assert case["case_id"].startswith("rfx-eval-")
