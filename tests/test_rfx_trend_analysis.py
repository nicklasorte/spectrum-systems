"""Tests for RFX-07 trend detection + hotspot mapping."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_trend_analysis import (
    RFXTrendAnalysisError,
    build_rfx_trend_report,
    detect_recurring_reason_codes,
)


def test_repeated_failures_produce_hotspot() -> None:
    failures = [
        {"reason_code": "rfx_obs_incomplete"},
        {"reason_code": "rfx_obs_incomplete"},
        {"reason_code": "rfx_obs_incomplete"},
    ]
    report = build_rfx_trend_report(
        failures=failures,
        repairs=None,
        replay_results=None,
        obs_records=None,
        freeze_records=None,
        authority_findings=None,
        eval_coverage_refs=None,
    )
    assert report["artifact_type"] == "rfx_trend_report"
    hotspot_kinds = {h["kind"] for h in report["hotspots"]}
    assert "recurring_reason_code" in hotspot_kinds


def test_isolated_failure_does_not_overtrigger() -> None:
    failures = [{"reason_code": "rfx_obs_incomplete"}]
    report = build_rfx_trend_report(
        failures=failures,
        repairs=None,
        replay_results=None,
        obs_records=None,
        freeze_records=None,
        authority_findings=None,
        eval_coverage_refs=None,
    )
    assert report["recurring_reason_codes"] == {}


def test_replay_drift_cluster_detected() -> None:
    replay = [
        {"trace_id": "t-1", "match": False},
        {"trace_id": "t-1", "match": False},
    ]
    report = build_rfx_trend_report(
        failures=None,
        repairs=None,
        replay_results=replay,
        obs_records=None,
        freeze_records=None,
        authority_findings=None,
        eval_coverage_refs=None,
    )
    assert "t-1" in report["replay_drift_clusters"]


def test_eval_blind_spot_detected() -> None:
    failures = [{"reason_code": "rfx_blind_spot_alpha"}]
    report = build_rfx_trend_report(
        failures=failures,
        repairs=None,
        replay_results=None,
        obs_records=None,
        freeze_records=None,
        authority_findings=None,
        eval_coverage_refs={"rfx_obs_incomplete"},
    )
    assert "rfx_blind_spot_alpha" in report["eval_blind_spots"]


def test_missing_trend_input_fails_closed() -> None:
    with pytest.raises(RFXTrendAnalysisError, match="rfx_trend_input_missing"):
        build_rfx_trend_report(
            failures=None,
            repairs=None,
            replay_results=None,
            obs_records=None,
            freeze_records=None,
            authority_findings=None,
            eval_coverage_refs=None,
        )


# ---------------------------------------------------------------------------
# RT-15 red-team: split reason-code variants to hide recurrence
# ---------------------------------------------------------------------------


def test_rt15_split_reason_code_variants_still_clusters() -> None:
    """Splitter renames same-class failures into v1/v2/v3 — must still cluster."""
    failures = [
        {"reason_code": "rfx_replay_mismatch_v1"},
        {"reason_code": "rfx_replay_mismatch_v2"},
        {"reason_code": "rfx_replay_mismatch_v3"},
    ]
    clustered = detect_recurring_reason_codes(failures, threshold=2)
    # All three should normalize to the same cluster key.
    assert sum(clustered.values()) >= 3
    assert any(k.startswith("rfx_replay_mismatch") for k in clustered)


def test_rt15_fix_follow_up_revalidation() -> None:
    """After classifier fix, the corpus reports correctly."""
    failures = [
        {"reason_code": "rfx_replay_mismatch"},
        {"reason_code": "rfx_replay_mismatch"},
    ]
    report = build_rfx_trend_report(
        failures=failures,
        repairs=None,
        replay_results=None,
        obs_records=None,
        freeze_records=None,
        authority_findings=None,
        eval_coverage_refs=None,
        recurrence_threshold=2,
    )
    kinds = {h["kind"] for h in report["hotspots"]}
    assert "recurring_reason_code" in kinds
