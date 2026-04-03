from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.adaptive_execution_observability import (
    build_adaptive_execution_observability,
    build_adaptive_execution_trend_report,
)


def _run(run_id: str, *, stop_reason: str, early_stop: int, useful: int, attempted: int, risk_level: str) -> dict:
    artifact = copy.deepcopy(load_example("roadmap_multi_batch_run_result"))
    artifact["run_id"] = run_id
    artifact["stop_reason"] = stop_reason
    artifact["stop_reason_codes"] = [stop_reason]
    artifact["resolved_max_batches_per_run"] = 3 if risk_level == "low" else (2 if risk_level == "medium" else 1)
    artifact["execution_efficiency_report"]["early_stops"] = early_stop
    artifact["execution_efficiency_report"]["useful_batches"] = useful
    artifact["execution_efficiency_report"]["batches_executed_per_run"] = attempted
    artifact["execution_efficiency_report"]["adaptive_factors"]["risk_level"] = risk_level
    artifact["source_refs"] = sorted(set(artifact["source_refs"]))
    return artifact


def test_examples_validate() -> None:
    validate_artifact(load_example("adaptive_execution_observability"), "adaptive_execution_observability")
    validate_artifact(load_example("adaptive_execution_trend_report"), "adaptive_execution_trend_report")


def test_aggregation_is_deterministic_and_distribution_correct() -> None:
    runs = [
        _run("RMB-111111111111", stop_reason="max_batches_reached", early_stop=0, useful=2, attempted=2, risk_level="low"),
        _run("RMB-222222222222", stop_reason="repeated_failure_pattern", early_stop=1, useful=1, attempted=2, risk_level="high"),
        _run("RMB-333333333333", stop_reason="max_batches_reached", early_stop=0, useful=2, attempted=2, risk_level="medium"),
    ]

    first = build_adaptive_execution_observability(
        runs,
        trace_id="trace-adaptive-observability",
        created_at="2026-04-03T23:59:00Z",
    )
    second = build_adaptive_execution_observability(
        list(reversed(runs)),
        trace_id="trace-adaptive-observability",
        created_at="2026-04-03T23:59:00Z",
    )

    assert first == second
    assert first["runs_observed"] == 3
    assert first["early_stop_rate"] == 0.3333
    assert first["stop_reason_distribution"]["max_batches_reached"] == 0.6667
    assert first["risk_level_distribution"]["high"] == 0.3333
    assert first["average_useful_batches_per_run"] == 1.6667


def test_guardrails_trigger_for_risky_drift_pattern() -> None:
    runs = [
        _run("RMB-AAAAAA000001", stop_reason="max_batches_reached", early_stop=0, useful=2, attempted=2, risk_level="low"),
        _run("RMB-AAAAAA000002", stop_reason="risk_accumulation_threshold_exceeded", early_stop=1, useful=0, attempted=2, risk_level="high"),
        _run("RMB-AAAAAA000003", stop_reason="risk_accumulation_threshold_exceeded", early_stop=1, useful=0, attempted=2, risk_level="high"),
    ]
    observability = build_adaptive_execution_observability(
        runs,
        trace_id="trace-adaptive-observability",
        created_at="2026-04-03T23:59:00Z",
    )
    report = build_adaptive_execution_trend_report(
        runs,
        observability=observability,
        trace_id="trace-adaptive-observability",
        created_at="2026-04-03T23:59:00Z",
    )

    triggered = {check["check_id"] for check in report["guardrail_checks"] if check["status"] == "triggered"}
    assert "risk_triggered_stops_rising" in triggered
    assert "useful_batches_stagnant_or_degrading" in triggered
    assert report["guardrail_status"] == "alert"
    assert report["tuning_warranted"] is True
    assert report["safety_trend"] in {"watch", "riskier"}


def test_trend_report_contract_and_authority_boundary_intact() -> None:
    runs = [_run("RMB-BBBBBB000001", stop_reason="authorization_block", early_stop=1, useful=0, attempted=1, risk_level="medium")]
    observability = build_adaptive_execution_observability(
        runs,
        trace_id="trace-adaptive-observability",
        created_at="2026-04-03T23:59:00Z",
    )
    report = build_adaptive_execution_trend_report(
        runs,
        observability=observability,
        trace_id="trace-adaptive-observability",
        created_at="2026-04-03T23:59:00Z",
    )

    validate_artifact(observability, "adaptive_execution_observability")
    validate_artifact(report, "adaptive_execution_trend_report")
    assert observability["control_boundary_integrity_status"] in {"bounded", "watch", "violated"}
    assert report["observability_ref"].startswith("adaptive_execution_observability:AEO-")
