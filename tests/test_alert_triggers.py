"""Deterministic fail-closed tests for SRE-11 alert trigger artifact generation."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example, validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.alert_triggers import (  # noqa: E402
    AlertTriggerError,
    build_alert_trigger,
    load_alert_trigger_policy,
)


def _replay_example() -> dict:
    replay = copy.deepcopy(load_example("replay_result"))
    if "error_budget_status" not in replay:
        replay["error_budget_status"] = copy.deepcopy(load_example("error_budget_status"))
    return replay


def _policy_example() -> dict:
    return copy.deepcopy(load_example("alert_trigger_policy"))


def test_alert_trigger_contract_example_validates() -> None:
    validate_artifact(load_example("alert_trigger"), "alert_trigger")


def test_alert_trigger_unknown_alert_status_fails() -> None:
    artifact = load_example("alert_trigger")
    artifact["alert_status"] = "urgent"
    with pytest.raises(ValidationError):
        validate_artifact(artifact, "alert_trigger")


def test_alert_trigger_unknown_severity_fails() -> None:
    artifact = load_example("alert_trigger")
    artifact["severity"] = "sev0"
    with pytest.raises(ValidationError):
        validate_artifact(artifact, "alert_trigger")


def test_alert_trigger_additional_properties_rejected() -> None:
    artifact = load_example("alert_trigger")
    artifact["unexpected"] = True
    with pytest.raises(ValidationError):
        validate_artifact(artifact, "alert_trigger")


def test_invalid_policy_fails_closed() -> None:
    policy = _policy_example()
    del policy["recommended_actions"]
    with pytest.raises(AlertTriggerError):
        load_alert_trigger_policy(policy)


def test_healthy_replay_result_returns_no_alert() -> None:
    replay = _replay_example()
    replay.pop("baseline_gate_decision", None)
    replay.pop("drift_detection_result", None)
    result = build_alert_trigger(replay, policy=_policy_example())
    assert result["alert_status"] == "no_alert"
    assert result["severity"] == "none"
    assert result["recommended_action"] == "none"


def test_warning_budget_returns_warning_alert() -> None:
    replay = _replay_example()
    replay["error_budget_status"]["budget_status"] = "warning"
    result = build_alert_trigger(replay, policy=_policy_example())
    assert result["alert_status"] == "warning"
    assert result["severity"] in {"medium", "high"}
    assert "budget_warning" in result["triggered_conditions"]


def test_exhausted_budget_returns_critical_alert() -> None:
    replay = _replay_example()
    replay["error_budget_status"]["budget_status"] = "exhausted"
    result = build_alert_trigger(replay, policy=_policy_example())
    assert result["alert_status"] == "critical"
    assert result["severity"] == "critical"
    assert "budget_exhausted" in result["triggered_conditions"]


def test_missing_required_source_artifact_emits_invalid_alert() -> None:
    replay = _replay_example()
    replay.pop("error_budget_status", None)
    result = build_alert_trigger(replay, policy=_policy_example())
    assert result["alert_status"] == "invalid"
    assert result["recommended_action"] == "fix_input_contracts"
    assert result["reasons"] == ["missing_required_source_artifacts"]


def test_malformed_replay_result_fails_closed() -> None:
    with pytest.raises(AlertTriggerError):
        build_alert_trigger({"artifact_type": "replay_result"}, policy=_policy_example())


def test_alert_trigger_deterministic_for_repeated_runs() -> None:
    replay = _replay_example()
    policy = _policy_example()
    result_1 = build_alert_trigger(replay, policy=policy)
    result_2 = build_alert_trigger(replay, policy=policy)
    assert result_1 == result_2


def test_cli_golden_inputs_round_trip_serializable() -> None:
    replay = _replay_example()
    trigger = build_alert_trigger(replay, policy=_policy_example())
    encoded = json.dumps(trigger, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["artifact_id"] == trigger["artifact_id"]
