"""Tests for BAG deterministic control replay engine."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_loop import run_control_loop  # noqa: E402
from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision  # noqa: E402
from spectrum_systems.modules.runtime.replay_engine import (  # noqa: E402
    ReplayEngineError,
    run_replay,
)


def _artifact() -> dict:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260322T000000Z",
        "pass_rate": 0.99,
        "failure_rate": 0.01,
        "drift_rate": 0.01,
        "reproducibility_score": 0.99,
        "system_status": "healthy",
    }


def _trace_context() -> dict:
    return {
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "execution_id": "exec-001",
        "stage": "runtime_gate",
        "runtime_environment": "test",
    }


def _originals(artifact: dict | None = None, trace_context: dict | None = None) -> tuple[dict, dict]:
    payload = copy.deepcopy(artifact or _artifact())
    context = copy.deepcopy(trace_context or _trace_context())
    decision = run_control_loop(payload, context)["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    return decision, enforcement


def test_matching_replay_returns_match_and_no_drift() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert result["consistency_status"] == "match"
    assert result["drift_detected"] is False
    assert result["failure_reason"] is None
    assert "drift_result" in result
    assert result["drift_result"]["drift_type"] == "none"
    assert result["drift_result"]["drift_detected"] is False


def test_mismatched_replay_returns_mismatch_and_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    def _force_mismatch(_decision: dict) -> dict:
        return {
            "artifact_type": "enforcement_result",
            "schema_version": "1.1.0",
            "enforcement_result_id": "ENF-MISMATCH-001",
            "timestamp": "2026-03-22T00:00:00Z",
            "trace_id": original_enforcement["trace_id"],
            "run_id": original_enforcement["run_id"],
            "input_decision_reference": original_enforcement["input_decision_reference"],
            "enforcement_action": "deny_execution",
            "final_status": "deny",
            "rationale_code": "deny_reliability_breach",
            "fail_closed": True,
            "enforcement_path": "baf_single_path",
            "provenance": {
                "source_artifact_type": "evaluation_control_decision",
                "source_artifact_id": original_enforcement["input_decision_reference"],
            },
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _force_mismatch,
    )

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    assert result["consistency_status"] == "mismatch"
    assert result["drift_detected"] is True
    assert result["failure_reason"] is None
    assert "drift_result" in result
    assert result["drift_result"]["drift_type"] in {"status_mismatch", "action_mismatch"}
    assert result["drift_result"]["drift_detected"] is True


def test_invalid_original_decision_fails_closed() -> None:
    artifact = _artifact()
    _, original_enforcement = _originals(artifact)
    with pytest.raises(ReplayEngineError):
        run_replay(artifact, {"artifact_type": "evaluation_control_decision"}, original_enforcement, _trace_context())


def test_invalid_original_enforcement_fails_closed() -> None:
    artifact = _artifact()
    original_decision, _ = _originals(artifact)
    with pytest.raises(ReplayEngineError):
        run_replay(artifact, original_decision, {"artifact_type": "enforcement_result"}, _trace_context())


def test_malformed_input_artifact_fails_closed() -> None:
    original_decision, original_enforcement = _originals()
    malformed = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "eval_run_id": "missing-required-fields"
    }
    with pytest.raises(ReplayEngineError):
        run_replay(malformed, original_decision, original_enforcement, _trace_context())


def test_deterministic_outcome_classification_and_no_input_mutation() -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    artifact_before = copy.deepcopy(artifact)
    decision_before = copy.deepcopy(original_decision)
    enforcement_before = copy.deepcopy(original_enforcement)

    result_1 = run_replay(artifact, original_decision, original_enforcement, _trace_context())
    result_2 = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert result_1["consistency_status"] == result_2["consistency_status"]
    assert result_1["drift_detected"] == result_2["drift_detected"]
    assert result_1["replay_id"] == result_2["replay_id"]

    assert artifact == artifact_before
    assert original_decision == decision_before
    assert original_enforcement == enforcement_before


def test_replay_uses_canonical_enforcement_path_not_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    original_decision, original_enforcement = _originals(artifact)

    called = {"canonical": 0, "legacy": 0}
    original_canonical = enforce_control_decision

    def _canonical_spy(decision: dict) -> dict:
        called["canonical"] += 1
        return original_canonical(decision)

    def _legacy_forbidden(_decision: dict) -> dict:
        called["legacy"] += 1
        raise AssertionError("legacy enforcement path must not be called")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_control_decision",
        _canonical_spy,
    )
    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.enforcement_engine.enforce_budget_decision",
        _legacy_forbidden,
    )

    result = run_replay(artifact, original_decision, original_enforcement, _trace_context())

    assert result["replay_path"] == "bag_replay_engine"
    assert called["canonical"] == 1
    assert called["legacy"] == 0
