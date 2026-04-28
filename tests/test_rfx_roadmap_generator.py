"""Tests for RFX-08 trend → roadmap recommendation generator."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_roadmap_generator import (
    RFXRoadmapGeneratorError,
    build_rfx_roadmap_recommendation,
)


def _kwargs(**override: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        source_trend_refs=["rfx-trend-1"],
        source_hotspot_refs=["rfx-hotspot-1"],
        reason_codes=["rfx_recurrence_threshold_exceeded"],
        recommended_build_slice="harden_replay_consistency_v2",
        affected_systems=["REP", "OBS"],
        required_owners=["REP", "OBS"],
        dependencies=["LOOP-08"],
        acceptance_criteria=["replay match preserved across 100 runs"],
        red_team_requirement="RT replay drift",
        fix_follow_up_requirement="restore replay match",
        revalidation_requirement="rerun replay corpus",
    )
    base.update(override)
    return base


def test_trend_becomes_recommendation() -> None:
    rec = build_rfx_roadmap_recommendation(**_kwargs())  # type: ignore[arg-type]
    assert rec["artifact_type"] == "rfx_roadmap_recommendation"
    assert rec["red_team_requirement"]
    assert rec["fix_follow_up_requirement"]
    assert rec["revalidation_requirement"]


def test_missing_source_trend_blocks() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_source_missing"):
        build_rfx_roadmap_recommendation(**_kwargs(source_trend_refs=None, source_hotspot_refs=None))  # type: ignore[arg-type]


def test_missing_dependency_list_blocks() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_dependency_missing"):
        build_rfx_roadmap_recommendation(**_kwargs(dependencies=None))  # type: ignore[arg-type]


def test_empty_dependency_list_blocks() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_dependency_missing"):
        build_rfx_roadmap_recommendation(**_kwargs(dependencies=[]))  # type: ignore[arg-type]


def test_explicit_no_dependencies_sentinel_passes() -> None:
    rec = build_rfx_roadmap_recommendation(**_kwargs(dependencies=["no_external_dependencies"]))  # type: ignore[arg-type]
    assert "no_external_dependencies" in rec["dependencies"]


def test_recommendation_does_not_mutate_canonical_roadmap() -> None:
    rec = build_rfx_roadmap_recommendation(**_kwargs())  # type: ignore[arg-type]
    # The recommendation is advisory — its ownership note must be present.
    assert "Advisory recommendation only" in rec["ownership_note"]


def test_authority_unsafe_language_blocked() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_authority_unsafe"):
        build_rfx_roadmap_recommendation(**_kwargs(rationale="This is the primary roadmap."))  # type: ignore[arg-type]


def test_red_team_requirement_required() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_recommendation_invalid"):
        build_rfx_roadmap_recommendation(**_kwargs(red_team_requirement=None))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RT-16 red-team: missing owner/dependency/red-team triad
# ---------------------------------------------------------------------------


def test_rt16_missing_owner_blocks_then_revalidates() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_recommendation_invalid"):
        build_rfx_roadmap_recommendation(**_kwargs(required_owners=None))  # type: ignore[arg-type]
    rec = build_rfx_roadmap_recommendation(**_kwargs())  # type: ignore[arg-type]
    assert rec["required_owners"]


def test_rt16_missing_dependency_blocks_then_revalidates() -> None:
    with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_dependency_missing"):
        build_rfx_roadmap_recommendation(**_kwargs(dependencies=[]))  # type: ignore[arg-type]
    rec = build_rfx_roadmap_recommendation(**_kwargs())  # type: ignore[arg-type]
    assert rec["dependencies"]


def test_rt16_missing_red_team_or_fix_or_revalidate_blocks() -> None:
    for kwargs in [
        _kwargs(red_team_requirement=None),
        _kwargs(fix_follow_up_requirement=None),
        _kwargs(revalidation_requirement=None),
    ]:
        with pytest.raises(RFXRoadmapGeneratorError, match="rfx_roadmap_recommendation_invalid"):
            build_rfx_roadmap_recommendation(**kwargs)  # type: ignore[arg-type]
