from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_control import (  # noqa: E402
    build_evaluation_control_decision,
)


def _eval_summary() -> Dict[str, Any]:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260321T120000Z",
        "pass_rate": 0.95,
        "failure_rate": 0.05,
        "drift_rate": 0.05,
        "reproducibility_score": 0.95,
        "system_status": "healthy",
    }


def test_healthy_summary_allows() -> None:
    decision = build_evaluation_control_decision(_eval_summary())
    assert decision["system_status"] == "healthy"
    assert decision["system_response"] == "allow"
    assert decision["triggered_signals"] == []


def test_low_pass_rate_warns() -> None:
    summary = _eval_summary()
    summary["pass_rate"] = 0.70
    summary["failure_rate"] = 0.30

    decision = build_evaluation_control_decision(summary)
    assert decision["system_status"] == "warning"
    assert decision["system_response"] == "warn"
    assert "reliability_breach" in decision["triggered_signals"]


def test_high_drift_rate_freezes() -> None:
    summary = _eval_summary()
    summary["drift_rate"] = 0.45

    decision = build_evaluation_control_decision(summary)
    assert decision["system_status"] == "exhausted"
    assert decision["system_response"] == "freeze"
    assert "stability_breach" in decision["triggered_signals"]


def test_low_reproducibility_blocks() -> None:
    summary = _eval_summary()
    summary["reproducibility_score"] = 0.40

    decision = build_evaluation_control_decision(summary)
    assert decision["system_status"] == "blocked"
    assert decision["system_response"] == "block"
    assert "trust_breach" in decision["triggered_signals"]


def test_malformed_eval_summary_fails_closed() -> None:
    malformed = {"artifact_type": "eval_summary", "eval_run_id": "x"}
    decision = build_evaluation_control_decision(malformed)

    assert decision["system_status"] == "blocked"
    assert decision["system_response"] == "block"
    assert "malformed_eval_summary" in decision["triggered_signals"]


def test_indeterminate_derived_failure_summary_is_non_allow() -> None:
    # In BAY, indeterminate outcomes are converted into failures before summary.
    # A low pass_rate therefore must never produce allow here.
    summary = _eval_summary()
    summary["pass_rate"] = 0.40
    summary["failure_rate"] = 0.60

    decision = build_evaluation_control_decision(summary)
    assert decision["system_response"] != "allow"
