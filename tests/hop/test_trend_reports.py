"""Tests for trend_reports.py — store summarisation."""

from __future__ import annotations

from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from spectrum_systems.modules.hop.trend_reports import (
    TrendReportConfig,
    build_trend_report,
    emit_trend_report,
)
from tests.hop.conftest import make_baseline_candidate


def test_trend_report_on_empty_store(store):
    report = build_trend_report(store)
    validate_hop_artifact(report, "hop_harness_trend_report")
    assert report["window_run_count"] == 0
    assert report["top_failure_modes"] == []
    assert report["frontier_movement"]["frontier_count"] == 0
    assert report["frontier_movement"]["best_score_seen"] == 0.0


def test_trend_report_after_baseline_run(store, eval_set):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    evaluate_candidate(candidate_payload=candidate, eval_set=eval_set, store=store)
    report = build_trend_report(store)
    validate_hop_artifact(report, "hop_harness_trend_report")
    assert report["window_run_count"] >= 1
    assert report["frontier_movement"]["best_score_seen"] == 1.0
    assert report["cost_trend"]["sample_count"] >= 1
    assert report["cost_trend"]["min_cost"] >= 0.0


def test_emit_trend_report_idempotent_on_unchanged_store(store):
    a = emit_trend_report(store)
    b = emit_trend_report(store)
    assert a["artifact_id"] == b["artifact_id"]


def test_trend_report_pattern_effectiveness_caps(store, eval_set):
    cfg = TrendReportConfig(max_pattern_effectiveness_rows=1)
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    evaluate_candidate(candidate_payload=candidate, eval_set=eval_set, store=store)
    report = build_trend_report(store, config=cfg)
    assert len(report["pattern_effectiveness"]) <= 1


def test_trend_report_advisory_only(store):
    report = build_trend_report(store)
    assert report["advisory_only"] is True
