"""Tests for RFX-16 system-intelligence layer."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_system_intelligence import (
    RFXSystemIntelligenceError,
    build_rfx_system_intelligence_report,
)


def _kwargs(**override: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        failure_classifications=[{"reason_code": "rfx_replay_mismatch"}],
        eval_cases=[{"case_id": "rfx-eval-1"}],
        fix_integrity_proofs=[{"result": "preserved"}],
        trend_reports=[{"hotspots": [{"reason_code": "rfx_replay_mismatch"}]}],
        roadmap_recommendations=[
            {"recommendation_id": "rfx-roadmap-rec-1", "recommended_build_slice": "harden_replay"}
        ],
        reliability_posture={"status": "ok"},
        memory_index={"entry_count": 4},
        blocked_states=[],
        next_build_recommendation={"recommended_build_slice": "harden_replay"},
    )
    base.update(override)
    return base


def test_full_healthy_loop_produces_report() -> None:
    report = build_rfx_system_intelligence_report(**_kwargs())  # type: ignore[arg-type]
    assert report["artifact_type"] == "rfx_system_intelligence_report"
    assert report["report_id"].startswith("rfx-intel-")
    assert "Advisory report only" in report["ownership_note"]


def test_missing_failure_input_blocks() -> None:
    with pytest.raises(RFXSystemIntelligenceError, match="rfx_intelligence_incomplete_loop"):
        build_rfx_system_intelligence_report(**_kwargs(failure_classifications=[]))  # type: ignore[arg-type]


def test_missing_eval_input_blocks() -> None:
    with pytest.raises(RFXSystemIntelligenceError, match="rfx_intelligence_incomplete_loop"):
        build_rfx_system_intelligence_report(**_kwargs(eval_cases=[]))  # type: ignore[arg-type]


def test_unsupported_next_build_blocked() -> None:
    with pytest.raises(RFXSystemIntelligenceError, match="rfx_next_build_not_supported"):
        build_rfx_system_intelligence_report(
            **_kwargs(next_build_recommendation={"recommended_build_slice": "not_in_roadmap"})  # type: ignore[arg-type]
        )


def test_report_remains_advisory() -> None:
    report = build_rfx_system_intelligence_report(**_kwargs())  # type: ignore[arg-type]
    # Must not include any execution / promotion / certification verb.
    note = report["ownership_note"]
    for forbidden in ("authorize", "directly promote", "certifies"):
        assert forbidden not in note.lower() or "does not" in note.lower()


# ---------------------------------------------------------------------------
# RT-24 red-team: intelligence layer authorizing execution / promotion
# ---------------------------------------------------------------------------


def test_rt24_red_team_authority_violation_blocks_then_revalidates() -> None:
    bad = _kwargs(
        next_build_recommendation={
            "recommended_build_slice": "harden_replay",
            "rationale": "I authorize execution of this build immediately.",
        }
    )
    with pytest.raises(RFXSystemIntelligenceError, match="rfx_intelligence_authority_violation"):
        build_rfx_system_intelligence_report(**bad)  # type: ignore[arg-type]

    report = build_rfx_system_intelligence_report(**_kwargs())  # type: ignore[arg-type]
    assert report["artifact_type"] == "rfx_system_intelligence_report"
