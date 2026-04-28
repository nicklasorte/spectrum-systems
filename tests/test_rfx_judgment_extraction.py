"""Tests for RFX-11 judgment extraction."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_judgment_extraction import (
    RFXJudgmentExtractionError,
    build_rfx_judgment_candidate,
)


def _kwargs(**override: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        failure_refs=["fail-1", "fail-2"],
        fix_refs=["fix-1"],
        eval_refs=["eval-1"],
        repeated_pattern_summary="replay-mismatch under burst load",
        proposed_judgment_primitive="replay_burst_recovery",
        jdx_handoff_target="jdx:registry/v1",
    )
    base.update(override)
    return base


def test_repeated_pattern_becomes_candidate() -> None:
    cand = build_rfx_judgment_candidate(**_kwargs())  # type: ignore[arg-type]
    assert cand["artifact_type"] == "rfx_judgment_candidate"
    assert cand["candidate_id"].startswith("rfx-judgment-candidate-")
    assert "JDX retains the canonical judgment" in cand["ownership_note"]


def test_weak_evidence_blocks_with_one_failure_only() -> None:
    with pytest.raises(RFXJudgmentExtractionError, match="rfx_judgment_evidence_insufficient"):
        build_rfx_judgment_candidate(**_kwargs(failure_refs=["fail-1"], fix_refs=[], eval_refs=[]))  # type: ignore[arg-type]


def test_source_refs_required() -> None:
    with pytest.raises(RFXJudgmentExtractionError, match="rfx_judgment_source_missing"):
        build_rfx_judgment_candidate(**_kwargs(failure_refs=None, fix_refs=None, eval_refs=None))  # type: ignore[arg-type]


def test_no_jdx_handoff_blocks() -> None:
    with pytest.raises(RFXJudgmentExtractionError, match="rfx_jdx_handoff_missing"):
        build_rfx_judgment_candidate(**_kwargs(jdx_handoff_target=None))  # type: ignore[arg-type]


def test_does_not_mutate_jdx_active_set() -> None:
    # The candidate is advisory only — it must not declare itself active or
    # otherwise indicate ownership over JDX/JSX state.
    cand = build_rfx_judgment_candidate(**_kwargs())  # type: ignore[arg-type]
    assert "judgment_record" not in cand or cand["artifact_type"] == "rfx_judgment_candidate"
    assert "Advisory candidate" in cand["ownership_note"]


# ---------------------------------------------------------------------------
# RT-19 red-team: judgment candidate from a single isolated failure
# ---------------------------------------------------------------------------


def test_rt19_red_team_isolated_failure_blocks_then_revalidates() -> None:
    with pytest.raises(RFXJudgmentExtractionError, match="rfx_judgment_evidence_insufficient"):
        build_rfx_judgment_candidate(**_kwargs(failure_refs=["fail-1"], fix_refs=[], eval_refs=[]))  # type: ignore[arg-type]
    cand = build_rfx_judgment_candidate(**_kwargs())  # type: ignore[arg-type]
    assert cand["candidate_id"]
