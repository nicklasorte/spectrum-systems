"""Tests for RFX-09 chaos campaign engine."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_chaos_campaign import (
    REQUIRED_CHAOS_SCENARIOS,
    RFXChaosCampaignError,
    RFXChaosCase,
    run_rfx_chaos_campaign,
)


def _make_blocking_case(name: str, code: str) -> RFXChaosCase:
    def invoke() -> None:
        raise ValueError(f"{code}: chaos {name} blocked")

    return RFXChaosCase(name=name, expected_reason_codes=(code,), invoke=invoke)


def _full_campaign() -> list[RFXChaosCase]:
    return [
        _make_blocking_case(name, f"reason_{name}")
        for name in REQUIRED_CHAOS_SCENARIOS
    ]


def test_every_chaos_case_blocks_deterministically() -> None:
    record = run_rfx_chaos_campaign(cases=_full_campaign())
    assert record["artifact_type"] == "rfx_chaos_campaign_record"
    assert record["case_count"] == len(REQUIRED_CHAOS_SCENARIOS)
    assert record["blocked_count"] == len(REQUIRED_CHAOS_SCENARIOS)


def test_failed_open_case_fails_campaign() -> None:
    cases = _full_campaign()
    # Replace one case with a no-op (does not raise).
    cases[0] = RFXChaosCase(
        name=cases[0].name,
        expected_reason_codes=cases[0].expected_reason_codes,
        invoke=lambda: None,
    )
    with pytest.raises(RFXChaosCampaignError, match="rfx_chaos_case_failed_open"):
        run_rfx_chaos_campaign(cases=cases)


def test_missing_reason_code_fails_campaign() -> None:
    cases = _full_campaign()
    name = cases[0].name

    def wrong_message() -> None:
        raise ValueError("some_other_problem: not the expected code")

    cases[0] = RFXChaosCase(
        name=name, expected_reason_codes=("rfx_specific_code",), invoke=wrong_message
    )
    with pytest.raises(RFXChaosCampaignError, match="rfx_chaos_reason_code_missing"):
        run_rfx_chaos_campaign(cases=cases)


def test_incomplete_campaign_blocks() -> None:
    partial = _full_campaign()[:5]
    with pytest.raises(RFXChaosCampaignError, match="rfx_chaos_campaign_incomplete"):
        run_rfx_chaos_campaign(cases=partial)


def test_valid_campaign_emits_complete_artifact() -> None:
    record = run_rfx_chaos_campaign(cases=_full_campaign())
    assert set(record["covered_scenarios"]) == set(REQUIRED_CHAOS_SCENARIOS)
    assert record["campaign_id"].startswith("rfx-chaos-")


# ---------------------------------------------------------------------------
# RT-17 red-team: inject a known-bad case that passes
# ---------------------------------------------------------------------------


def test_rt17_red_team_known_bad_case_that_passes_fails_campaign() -> None:
    cases = _full_campaign()
    cases[0] = RFXChaosCase(
        name=cases[0].name,
        expected_reason_codes=cases[0].expected_reason_codes,
        invoke=lambda: None,  # known-bad input that erroneously passes
    )
    with pytest.raises(RFXChaosCampaignError, match="rfx_chaos_case_failed_open"):
        run_rfx_chaos_campaign(cases=cases)


def test_rt17_fix_follow_up_revalidation() -> None:
    """After the fix, the same cases must now block deterministically."""
    record = run_rfx_chaos_campaign(cases=_full_campaign())
    assert record["blocked_count"] == record["case_count"]
