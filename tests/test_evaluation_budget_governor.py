"""Tests for BT — Evaluation Budget Governor (evaluation_budget_governor.py).

Covers:
 1.  load_monitor_summary loads a valid summary
 2.  load_monitor_summary raises on missing file
 3.  load_monitor_summary raises InvalidSummaryError on invalid JSON structure
 4.  validate_summary returns empty list for valid summary
 5.  validate_summary returns errors for invalid summary
 6.  evaluate_budget_status — healthy path
 7.  evaluate_budget_status — warning (drift_rate threshold)
 8.  evaluate_budget_status — warning (failure_rate threshold)
 9.  evaluate_budget_status — warning (burn_rate elevated)
10.  evaluate_budget_status — warning (degrading trend)
11.  evaluate_budget_status — exhausted (burn_rate exhausting)
12.  evaluate_budget_status — exhausted (critical alerts + degrading trend)
13.  evaluate_budget_status — blocked (critical alerts + critical failure rate)
14.  evaluate_budget_status — blocked (critical drift rate + critical failure rate)
15.  evaluate_budget_status records triggered_thresholds correctly
16.  determine_system_response — healthy → allow
17.  determine_system_response — warning (no critical) → allow_with_warning
18.  determine_system_response — warning (critical alerts) → require_review
19.  determine_system_response — exhausted (no critical+degrading) → freeze_changes
20.  determine_system_response — exhausted (critical+degrading) → require_review
21.  determine_system_response — blocked → block_release
22.  build_decision_artifact produces schema-valid artifact
23.  build_decision_artifact includes all required fields
24.  validate_decision returns empty list for valid decision
25.  validate_decision returns errors for invalid decision
26.  run_budget_governor — healthy fixture produces allow decision
27.  run_budget_governor — warning fixture produces caution decision
28.  run_budget_governor — exhausted fixture produces freeze_changes decision
29.  run_budget_governor — blocked fixture produces block_release decision
30.  run_budget_governor raises on missing file
31.  run_budget_governor raises InvalidSummaryError on invalid summary
32.  run_budget_governor respects threshold overrides
33.  CLI exit 0 — healthy
34.  CLI exit 1 — warning
35.  CLI exit 2 — freeze / blocked
36.  CLI exit 2 — invalid input
37.  CLI writes decision artifact to output-dir
38.  All produced artifacts are schema-valid
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_budget_governor import (  # noqa: E402
    EvaluationBudgetGovernorError,
    InvalidSummaryError,
    build_decision_artifact,
    determine_system_response,
    evaluate_budget_status,
    load_monitor_summary,
    run_budget_governor,
    translate_to_legacy_response,
    validate_decision,
    validate_summary,
)
from spectrum_systems.modules.runtime.evaluation_control import map_control_loop_status_to_response  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "evaluation_budget_governor"
_HEALTHY = _FIXTURE_DIR / "healthy_summary.json"
_WARNING = _FIXTURE_DIR / "warning_summary.json"
_EXHAUSTED = _FIXTURE_DIR / "exhausted_summary.json"
_BLOCKED = _FIXTURE_DIR / "blocked_summary.json"
_INVALID = _FIXTURE_DIR / "invalid_summary.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _make_summary(
    *,
    summary_id: str = "test-summary-001",
    total_runs: int = 4,
    avg_pass_rate: float = 1.0,
    avg_drift_rate: float = 0.0,
    avg_repro: float = 0.9,
    total_failed_runs: int = 0,
    total_critical_alerts: int = 0,
    pass_rate_trend: str = "stable",
    drift_rate_trend: str = "stable",
    repro_trend: str = "stable",
    burn_status: str = "normal",
    burn_reasons: list | None = None,
    recommended_action: str = "none",
) -> Dict[str, Any]:
    if burn_reasons is None:
        burn_reasons = []
    return {
        "summary_id": summary_id,
        "created_at": "2025-01-01T00:00:00Z",
        "window": {
            "start_at": "2025-01-01T00:00:00Z",
            "end_at": "2025-01-01T01:00:00Z",
            "total_runs": total_runs,
        },
        "aggregates": {
            "average_pass_rate": avg_pass_rate,
            "average_drift_rate": avg_drift_rate,
            "average_reproducibility_score": avg_repro,
            "total_failed_runs": total_failed_runs,
            "total_critical_alerts": total_critical_alerts,
        },
        "trend_analysis": {
            "pass_rate_trend": pass_rate_trend,
            "drift_rate_trend": drift_rate_trend,
            "reproducibility_trend": repro_trend,
        },
        "burn_rate_assessment": {
            "status": burn_status,
            "reasons": burn_reasons,
        },
        "recommended_action": recommended_action,
        "source_run_ids": [f"run-{i:03d}" for i in range(1, total_runs + 1)],
    }


# ---------------------------------------------------------------------------
# 1–3. load_monitor_summary
# ---------------------------------------------------------------------------


def test_load_monitor_summary_valid():
    summary = load_monitor_summary(_HEALTHY)
    assert summary["summary_id"] == "summary-healthy-001"


def test_load_monitor_summary_missing_file():
    with pytest.raises(EvaluationBudgetGovernorError, match="not found"):
        load_monitor_summary("/nonexistent/path/summary.json")


def test_load_monitor_summary_invalid_raises():
    with pytest.raises(InvalidSummaryError):
        load_monitor_summary(_INVALID)


# ---------------------------------------------------------------------------
# 4–5. validate_summary
# ---------------------------------------------------------------------------


def test_validate_summary_valid():
    summary = _load_json(_HEALTHY)
    errors = validate_summary(summary)
    assert errors == [], f"Unexpected errors: {errors}"


def test_validate_summary_invalid():
    errors = validate_summary({"bad": "data"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 6–15. evaluate_budget_status
# ---------------------------------------------------------------------------


def test_evaluate_budget_status_healthy():
    summary = _make_summary()
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "healthy"
    assert triggered == []
    assert len(reasons) >= 1


def test_evaluate_budget_status_warning_drift_rate():
    summary = _make_summary(avg_drift_rate=0.15)
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "warning"
    assert "drift_rate_warning" in triggered


def test_evaluate_budget_status_warning_failure_rate():
    # 1 failed out of 4 = 25% ≥ 20% threshold
    summary = _make_summary(total_runs=4, total_failed_runs=1)
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "warning"
    assert "failure_rate_warning" in triggered


def test_evaluate_budget_status_warning_burn_rate_elevated():
    summary = _make_summary(burn_status="elevated", burn_reasons=["elevated burn"])
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "warning"
    assert "burn_rate_elevated" in triggered


def test_evaluate_budget_status_warning_degrading_trend():
    summary = _make_summary(pass_rate_trend="degrading")
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "warning"
    assert "degrading_trend" in triggered


def test_evaluate_budget_status_exhausted_burn_rate():
    summary = _make_summary(
        burn_status="exhausting",
        burn_reasons=["2/4 runs failed"],
    )
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "exhausted"
    assert "burn_rate_exhausting" in triggered


def test_evaluate_budget_status_exhausted_critical_alerts_degrading():
    summary = _make_summary(
        total_critical_alerts=2,
        pass_rate_trend="degrading",
    )
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "exhausted"
    assert "critical_alerts_with_degrading_trend" in triggered


def test_evaluate_budget_status_blocked_critical_alerts_high_failure():
    # critical alerts + critical failure rate (≥50%) → blocked
    summary = _make_summary(
        total_runs=4,
        total_failed_runs=2,
        total_critical_alerts=1,
    )
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "blocked"
    assert "critical_alerts_with_critical_failure_rate" in triggered


def test_evaluate_budget_status_blocked_critical_drift_and_failure():
    # critical drift rate ≥25% + critical failure rate ≥50% → blocked
    summary = _make_summary(
        total_runs=4,
        total_failed_runs=2,
        avg_drift_rate=0.30,
    )
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "blocked"
    assert "critical_drift_rate_with_critical_failure_rate" in triggered


def test_evaluate_budget_status_triggered_thresholds_recorded():
    summary = _make_summary(avg_drift_rate=0.15, pass_rate_trend="degrading")
    _, _, triggered = evaluate_budget_status(summary)
    assert "drift_rate_warning" in triggered
    assert "degrading_trend" in triggered


# ---------------------------------------------------------------------------
# 16–21. determine_system_response
# ---------------------------------------------------------------------------


def test_determine_system_response_healthy():
    response = determine_system_response("healthy", [])
    assert response == "allow"


def test_determine_system_response_warning():
    response = determine_system_response("warning", ["drift_rate_warning"])
    assert response == "warn"


def test_determine_system_response_exhausted():
    response = determine_system_response("exhausted", ["burn_rate_exhausting"])
    assert response == "freeze"


def test_determine_system_response_blocked():
    response = determine_system_response("blocked", ["critical_alerts_with_critical_failure_rate"])
    assert response == "block"


def test_only_canonical_mapping_used():
    for status in ("healthy", "warning", "exhausted", "blocked", "unknown"):
        _, canonical = map_control_loop_status_to_response(status)
        assert determine_system_response(status, ["any-trigger"]) == canonical


def test_no_duplicate_mapping_logic_exists():
    import inspect

    source = inspect.getsource(determine_system_response)
    assert "allow_with_warning" not in source
    assert "freeze_changes" not in source
    assert "require_review" not in source
    assert "map_control_loop_status_to_response" in source


# ---------------------------------------------------------------------------
# 22–25. build_decision_artifact and validate_decision
# ---------------------------------------------------------------------------


def test_build_decision_artifact_schema_valid():
    decision = build_decision_artifact(
        summary_id="test-summary-001",
        status="healthy",
        system_response="allow",
        reasons=["All signals within acceptable thresholds."],
        triggered_thresholds=[],
        required_actions=["No immediate action required. Continue monitoring."],
    )
    errors = validate_decision(decision)
    assert errors == [], f"Schema errors: {errors}"


def test_build_decision_artifact_required_fields():
    decision = build_decision_artifact(
        summary_id="test-summary-002",
        status="warning",
        system_response="allow_with_warning",
        reasons=["Drift rate elevated."],
        triggered_thresholds=["drift_rate_warning"],
        required_actions=["Review warning signals."],
    )
    for field in (
        "decision_dialect", "decision_id", "summary_id", "status", "system_response",
        "reasons", "triggered_thresholds", "required_actions", "created_at",
    ):
        assert field in decision, f"Missing field: {field}"
    assert decision["summary_id"] == "test-summary-002"
    assert decision["decision_dialect"] == "legacy"


def test_validate_decision_valid():
    decision = build_decision_artifact(
        summary_id="test-summary-003",
        status="blocked",
        system_response="block_release",
        reasons=["Critical failure."],
        triggered_thresholds=["critical_alerts_with_critical_failure_rate"],
        required_actions=["Block all release activity immediately."],
    )
    errors = validate_decision(decision)
    assert errors == []


def test_validate_decision_invalid():
    errors = validate_decision({"status": "bad_value"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 26–32. run_budget_governor
# ---------------------------------------------------------------------------


def test_run_budget_governor_healthy():
    decision = run_budget_governor(_HEALTHY)
    assert decision["status"] == "healthy"
    assert decision["system_response"] == "allow"
    assert decision["summary_id"] == "summary-healthy-001"


def test_run_budget_governor_warning():
    decision = run_budget_governor(_WARNING)
    assert decision["status"] == "warning"
    assert decision["system_response"] == "allow_with_warning"


def test_run_budget_governor_exhausted():
    decision = run_budget_governor(_EXHAUSTED)
    assert decision["status"] == "exhausted"
    assert decision["system_response"] == "freeze_changes"


def test_run_budget_governor_blocked():
    decision = run_budget_governor(_BLOCKED)
    assert decision["status"] == "blocked"
    assert decision["system_response"] == "block_release"


def test_run_budget_governor_raises_on_missing_file():
    with pytest.raises(EvaluationBudgetGovernorError, match="not found"):
        run_budget_governor("/nonexistent/path/summary.json")


def test_run_budget_governor_raises_on_invalid_summary():
    with pytest.raises(InvalidSummaryError):
        run_budget_governor(_INVALID)


def test_run_budget_governor_threshold_override():
    # Override drift_rate_warning to a very high value so that a 15% drift rate
    # no longer triggers a warning.
    summary = _make_summary(avg_drift_rate=0.15)

    # Temporarily write this to a tmp file and call via in-process API.
    thresholds = {"drift_rate_warning": 0.99}
    status, reasons, triggered = evaluate_budget_status(summary, thresholds=thresholds)
    # With threshold=0.99 a drift of 0.15 should not trigger the drift warning
    assert "drift_rate_warning" not in triggered


# ---------------------------------------------------------------------------
# 33–37. CLI
# ---------------------------------------------------------------------------


def test_cli_exit_0_healthy(tmp_path):
    from scripts.run_evaluation_budget_governor import main  # noqa: PLC0415

    exit_code = main(["--input", str(_HEALTHY), "--output-dir", str(tmp_path)])
    assert exit_code == 0


def test_cli_exit_1_warning(tmp_path):
    from scripts.run_evaluation_budget_governor import main  # noqa: PLC0415

    exit_code = main(["--input", str(_WARNING), "--output-dir", str(tmp_path)])
    assert exit_code == 1


def test_cli_exit_2_blocked(tmp_path):
    from scripts.run_evaluation_budget_governor import main  # noqa: PLC0415

    exit_code = main(["--input", str(_BLOCKED), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_invalid_input(tmp_path):
    from scripts.run_evaluation_budget_governor import main  # noqa: PLC0415

    exit_code = main(["--input", str(_INVALID), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_writes_decision_artifact(tmp_path):
    from scripts.run_evaluation_budget_governor import main  # noqa: PLC0415

    main(["--input", str(_HEALTHY), "--output-dir", str(tmp_path)])
    decision_path = tmp_path / "evaluation_budget_decision.json"
    assert decision_path.is_file()
    with decision_path.open() as fh:
        decision = json.load(fh)
    errors = validate_decision(decision)
    assert errors == [], f"Written decision is not schema-valid: {errors}"


# ---------------------------------------------------------------------------
# 38. All produced artifacts are schema-valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    [_HEALTHY, _WARNING, _EXHAUSTED, _BLOCKED],
    ids=["healthy", "warning", "exhausted", "blocked"],
)
def test_all_decisions_schema_valid(fixture: Path):
    decision = run_budget_governor(fixture)
    errors = validate_decision(decision)
    assert errors == [], f"Schema errors for {fixture.name}: {errors}"


def test_decision_determinism():
    summary = _make_summary(total_runs=4, total_failed_runs=2, avg_drift_rate=0.30)
    first = evaluate_budget_status(summary)
    second = evaluate_budget_status(summary)
    assert first == second


def test_threshold_precedence():
    summary = _make_summary(
        total_runs=10,
        total_failed_runs=6,
        total_critical_alerts=2,
        avg_drift_rate=0.35,
        burn_status="exhausting",
        pass_rate_trend="degrading",
    )
    status, reasons, triggered = evaluate_budget_status(summary)
    assert status == "blocked"
    assert "critical_alerts_with_critical_failure_rate" in triggered
    assert "burn_rate_exhausting" not in triggered
    assert reasons


def test_translate_to_legacy_response_is_isolated():
    assert translate_to_legacy_response("allow") == "allow"
    assert translate_to_legacy_response("warn") == "allow_with_warning"
    assert translate_to_legacy_response("freeze") == "freeze_changes"
    assert translate_to_legacy_response("block") == "block_release"


def test_schema_blocks_mixed_dialects():
    mixed = {
        "decision_dialect": "control_loop",
        "decision_id": "x",
        "summary_id": "y",
        "trace_id": "t",
        "timestamp": "2026-03-22T00:00:00Z",
        "status": "warning",
        "system_response": "allow_with_warning",
        "triggered_thresholds": ["drift_rate_warning"],
        "reasons": ["warning"],
    }
    errors = validate_decision(mixed)
    assert errors

