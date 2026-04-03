from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.repo_health_eval import (  # noqa: E402
    RepoHealthEvalError,
    build_repo_health_control_decision,
    build_repo_health_eval,
    compute_repo_health_metrics,
)


def _snapshot() -> dict:
    return copy.deepcopy(load_example("repo_review_snapshot"))


def test_repo_health_eval_emits_governed_eval_artifacts() -> None:
    artifacts = build_repo_health_eval(_snapshot())
    validate_artifact(artifacts["eval_result"], "eval_result")
    validate_artifact(artifacts["eval_summary"], "eval_summary")


def test_repo_health_metrics_are_deterministic() -> None:
    first = compute_repo_health_metrics(_snapshot())
    second = compute_repo_health_metrics(_snapshot())
    assert first == second


def test_repo_health_control_pass_behavior() -> None:
    snapshot = _snapshot()
    snapshot["findings_summary"] = {
        "redundancy_findings": 0,
        "drift_findings": 0,
        "eval_coverage_gaps": 0,
        "control_bypass_findings": 0,
    }
    artifacts = build_repo_health_eval(snapshot)
    decision = build_repo_health_control_decision(snapshot=snapshot, eval_summary=artifacts["eval_summary"])
    assert decision["system_response"] == "allow"


def test_repo_health_control_warn_behavior() -> None:
    snapshot = _snapshot()
    snapshot["findings_summary"] = {
        "redundancy_findings": 1,
        "drift_findings": 0,
        "eval_coverage_gaps": 0,
        "control_bypass_findings": 0,
    }
    artifacts = build_repo_health_eval(snapshot)
    decision = build_repo_health_control_decision(snapshot=snapshot, eval_summary=artifacts["eval_summary"])
    assert decision["system_response"] == "warn"


def test_repo_health_control_freeze_behavior() -> None:
    snapshot = _snapshot()
    snapshot["findings_summary"] = {
        "redundancy_findings": 0,
        "drift_findings": 2,
        "eval_coverage_gaps": 0,
        "control_bypass_findings": 0,
    }
    artifacts = build_repo_health_eval(snapshot)
    decision = build_repo_health_control_decision(snapshot=snapshot, eval_summary=artifacts["eval_summary"])
    assert decision["system_response"] == "freeze"


def test_repo_health_control_block_behavior() -> None:
    snapshot = _snapshot()
    snapshot["findings_summary"] = {
        "redundancy_findings": 0,
        "drift_findings": 0,
        "eval_coverage_gaps": 0,
        "control_bypass_findings": 1,
    }
    artifacts = build_repo_health_eval(snapshot)
    decision = build_repo_health_control_decision(snapshot=snapshot, eval_summary=artifacts["eval_summary"])
    assert decision["system_response"] == "block"


def test_repo_health_missing_review_artifact_fails_closed() -> None:
    with pytest.raises(RepoHealthEvalError, match="missing review artifact"):
        build_repo_health_control_decision(snapshot=None, eval_summary={})


def test_repo_health_missing_required_eval_fails_closed() -> None:
    with pytest.raises(RepoHealthEvalError, match="missing required eval"):
        build_repo_health_control_decision(snapshot=_snapshot(), eval_summary=None)


def test_repo_health_severe_review_risk_path_blocks() -> None:
    snapshot = _snapshot()
    snapshot["findings_summary"] = {
        "redundancy_findings": 1,
        "drift_findings": 1,
        "eval_coverage_gaps": 1,
        "control_bypass_findings": 2,
    }
    artifacts = build_repo_health_eval(snapshot)
    decision = build_repo_health_control_decision(snapshot=snapshot, eval_summary=artifacts["eval_summary"])
    assert decision["decision"] == "deny"
    assert decision["system_response"] == "block"
