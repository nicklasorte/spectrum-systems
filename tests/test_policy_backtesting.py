from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.policy_backtesting import (  # noqa: E402
    PolicyBacktestingError,
    run_policy_backtest,
)


_TRACE_ID = "11111111-1111-4111-8111-111111111111"


def _replay(*, replay_id: str, replay_success_rate: float = 0.95, drift_rate: float = 0.0, consistency: str = "match") -> dict:
    replay = copy.deepcopy(load_example("replay_result"))
    replay["replay_id"] = replay_id
    replay["replay_run_id"] = f"run-{replay_id}"
    replay["trace_id"] = _TRACE_ID
    replay["timestamp"] = "2026-03-28T00:00:00Z"
    replay["consistency_status"] = consistency
    drift_detected = drift_rate > 0.0 or consistency != "match"
    replay["drift_detected"] = drift_detected

    replay["provenance"]["trace_id"] = _TRACE_ID
    if isinstance(replay.get("drift_result"), dict) and isinstance(replay["drift_result"].get("provenance"), dict):
        replay["drift_result"]["provenance"]["trace_id"] = _TRACE_ID
        replay["drift_result"]["drift_detected"] = drift_detected
        replay["drift_result"]["drift_type"] = "status_mismatch" if drift_detected else "none"
    replay["observability_metrics"]["trace_refs"]["trace_id"] = _TRACE_ID
    replay["error_budget_status"]["trace_refs"]["trace_id"] = _TRACE_ID
    if isinstance(replay.get("alert_trigger"), dict):
        replay["alert_trigger"]["trace_refs"]["trace_id"] = _TRACE_ID

    replay["observability_metrics"]["metrics"]["replay_success_rate"] = replay_success_rate
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = drift_rate
    replay["error_budget_status"]["budget_status"] = "healthy"
    replay["error_budget_status"]["highest_severity"] = "healthy"
    replay["error_budget_status"]["triggered_conditions"] = []
    replay["error_budget_status"]["reasons"] = ["healthy"]

    return replay


def _eval_summary(eval_run_id: str) -> dict:
    summary = copy.deepcopy(load_example("eval_summary"))
    summary["trace_id"] = _TRACE_ID
    summary["eval_run_id"] = eval_run_id
    return summary


def _xrun_decision(*, intelligence_id: str = "XRI-AAAAAAAAAAAA") -> dict:
    return {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": intelligence_id,
        "timestamp": "2026-03-28T00:00:00Z",
        "input_refs": {
            "replay_results": ["rp-1"],
            "eval_summaries": ["ev-1"],
            "regression_results": ["rg-1"],
            "drift_results": ["dr-1"],
            "monitor_records": ["mr-1"],
            "policy_ref": "policy-v1",
        },
        "aggregated_metrics": {
            "failure_rate_trend": 0.0,
            "drift_trend": 0.0,
            "regression_density": 0.0,
            "reproducibility_variance": 0.0,
        },
        "detected_patterns": [],
        "recommended_actions": [],
        "system_signal": "stable",
        "trace_ids": [_TRACE_ID],
        "policy_version": "2026.03.28",
    }


def _policy_ref(policy_id: str, version: str, *, reliability: float, drift: float, trust: float) -> dict:
    return {
        "policy_id": policy_id,
        "policy_version": version,
        "thresholds": {
            "reliability_threshold": reliability,
            "drift_threshold": drift,
            "trust_threshold": trust,
        },
    }


def _input_payload(replay_results: list[dict], baseline: dict, candidate: dict) -> dict:
    return {
        "replay_results": replay_results,
        "eval_summaries": [_eval_summary(f"ev-{idx + 1}") for idx, _ in enumerate(replay_results)],
        "error_budget_statuses": [copy.deepcopy(replay["error_budget_status"]) for replay in replay_results],
        "cross_run_intelligence_decisions": [_xrun_decision()],
        "baseline_policy_ref": baseline,
        "candidate_policy_ref": candidate,
    }


def test_baseline_and_candidate_identical_have_no_changes() -> None:
    replay_results = [_replay(replay_id="rp-1")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.8)
    candidate = _policy_ref("policy-candidate", "v1", reliability=0.8, drift=0.2, trust=0.8)

    result = run_policy_backtest(_input_payload(replay_results, baseline, candidate))

    assert all(delta["change_type"] == "no_change" for delta in result["decision_deltas"])
    validate_artifact(result, "policy_backtest_result")


def test_candidate_improves_pass_rate_accepts() -> None:
    replay_results = [_replay(replay_id="rp-1", replay_success_rate=0.85, drift_rate=0.0, consistency="match")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.9, drift=0.2, trust=0.8)
    candidate = _policy_ref("policy-candidate", "v2", reliability=0.8, drift=0.2, trust=0.8)

    result = run_policy_backtest(_input_payload(replay_results, baseline, candidate))

    assert result["comparison_summary"]["candidate_pass_rate"] > result["comparison_summary"]["baseline_pass_rate"]
    assert result["recommended_action"] == "accept_policy"


def test_candidate_introduces_missed_failure_rejects() -> None:
    replay_results = [_replay(replay_id="rp-1", replay_success_rate=0.95, drift_rate=0.6, consistency="mismatch")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.0)
    candidate = _policy_ref("policy-candidate", "v2", reliability=0.8, drift=0.8, trust=0.0)

    result = run_policy_backtest(_input_payload(replay_results, baseline, candidate))

    assert "missed_failures" in result["detected_risks"]
    assert result["recommended_action"] == "reject_policy"


def test_candidate_increases_blocking_excessively_rejects() -> None:
    replay_results = [_replay(replay_id="rp-1", replay_success_rate=0.95, drift_rate=0.0, consistency="mismatch")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.0)
    candidate = _policy_ref("policy-candidate", "v2", reliability=0.8, drift=0.2, trust=0.8)

    result = run_policy_backtest(_input_payload(replay_results, baseline, candidate))

    assert "overblocking" in result["detected_risks"]
    assert result["recommended_action"] == "reject_policy"


def test_mixed_results_require_review() -> None:
    replay_results = [
        _replay(replay_id="rp-1", replay_success_rate=0.82, drift_rate=0.0, consistency="match"),
        _replay(replay_id="rp-2", replay_success_rate=0.82, drift_rate=0.0, consistency="match"),
    ]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.8)
    candidate = _policy_ref("policy-candidate", "v2", reliability=0.85, drift=0.2, trust=0.8)

    result = run_policy_backtest(_input_payload(replay_results, baseline, candidate))

    assert result["comparison_summary"]["candidate_pass_rate"] < result["comparison_summary"]["baseline_pass_rate"]
    assert result["detected_risks"] == []
    assert result["recommended_action"] == "require_review"


def test_missing_required_input_fails_closed() -> None:
    replay_results = [_replay(replay_id="rp-1")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.8)
    candidate = _policy_ref("policy-candidate", "v2", reliability=0.8, drift=0.2, trust=0.8)

    payload = _input_payload(replay_results, baseline, candidate)
    payload.pop("replay_results")

    with pytest.raises(PolicyBacktestingError, match="replay_results"):
        run_policy_backtest(payload)


def test_malformed_policy_fails_closed() -> None:
    replay_results = [_replay(replay_id="rp-1")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.8)
    candidate = {
        "policy_id": "policy-candidate",
        "policy_version": "v2",
        "thresholds": {"reliability_threshold": 0.8, "drift_threshold": 0.2},
    }

    with pytest.raises(PolicyBacktestingError, match="trust_threshold"):
        run_policy_backtest(_input_payload(replay_results, baseline, candidate))


def test_comparative_backtesting_decisions_include_threshold_context() -> None:
    replay_results = [_replay(replay_id="rp-ctx-1")]
    baseline = _policy_ref("policy-baseline", "v1", reliability=0.8, drift=0.2, trust=0.8)
    candidate = _policy_ref("policy-candidate", "v2", reliability=0.75, drift=0.25, trust=0.75)
    result = run_policy_backtest(_input_payload(replay_results, baseline, candidate))
    for decision_delta in result["decision_deltas"]:
        assert decision_delta["baseline_decision"] in {"allow", "warn", "freeze", "block"}
        assert decision_delta["candidate_decision"] in {"allow", "warn", "freeze", "block"}
