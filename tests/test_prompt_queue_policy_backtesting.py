from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.prompt_queue.policy_backtesting import (
    QueuePolicyBacktestingError,
    run_queue_policy_backtest,
)


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def _step(step_id: str, decision: str = "allow", trace_id: str = "trace-001") -> dict:
    return {
        "decision_id": f"decision-{step_id}",
        "step_id": step_id,
        "queue_id": "queue-01",
        "trace_linkage": trace_id,
        "decision": decision,
        "reason_codes": ["clean_findings"] if decision == "allow" else ["warnings_detected"],
        "blocking_reasons": [] if decision != "block" else ["fail_closed"],
        "derived_from_artifacts": ["artifact-1"],
        "validation_result_refs": [f"validation_result_record:vr-{step_id}"],
        "review_evidence_ref": f"review_result_artifact:rqx-{step_id}",
        "preflight_decision": "ALLOW",
        "timestamp": "2026-03-29T00:00:00Z",
        "generator_version": "1.0.0",
    }


def _transition(step_id: str, status: str = "allowed", action: str = "continue", trace_id: str = "trace-001") -> dict:
    return {
        "transition_decision_id": f"transition-{step_id}",
        "step_id": step_id,
        "queue_id": "queue-01",
        "trace_linkage": trace_id,
        "source_decision_ref": f"decision-{step_id}",
        "batch_decision_artifact_ref": f"queue-01:{step_id}",
        "transition_action": action,
        "transition_status": status,
        "reason_codes": ["allow_clean_findings_continue"] if status == "allowed" else ["blocked_conflicting_inputs"],
        "blocking_reasons": [] if status == "allowed" else ["ambiguous_transition"],
        "derived_from_artifacts": ["artifact-1"],
        "timestamp": "2026-03-29T00:00:00Z",
    }


def _replay_ref(tmp_path: Path, *, step_decision: dict, transition_decision: dict, name: str = "run") -> str:
    step_ref = _write(tmp_path / f"{name}.step.json", step_decision)
    transition_ref = _write(tmp_path / f"{name}.transition.json", transition_decision)
    replay_ref = _write(
        tmp_path / f"{name}.audit.json",
        {
            "step_decision_refs": [step_ref],
            "transition_decision_refs": [transition_ref],
        },
    )
    return replay_ref


def _input(replay_run_refs: list[str], baseline: str = "permissive", candidate: str = "permissive") -> dict:
    return {
        "replay_run_refs": replay_run_refs,
        "baseline_policy_ref": {"policy_id": baseline, "policy_version": "1.0.0"},
        "policy_under_test_ref": {"policy_id": candidate, "policy_version": "1.0.0"},
        "timestamp": "2026-03-29T00:00:00Z",
    }


def test_identical_policy_results_in_full_match(tmp_path: Path) -> None:
    replay_ref = _replay_ref(
        tmp_path,
        step_decision=_step("step-001", decision="allow"),
        transition_decision=_transition("step-001"),
    )
    report = run_queue_policy_backtest(_input([replay_ref]))
    assert report["aggregate_summary"]["mismatches"] == 0
    assert report["comparison_results"][0]["parity_status"] == "match"


def test_changed_policy_detects_mismatch(tmp_path: Path) -> None:
    replay_ref = _replay_ref(
        tmp_path,
        step_decision=_step("step-001", decision="warn"),
        transition_decision=_transition("step-001", action="request_review"),
    )
    report = run_queue_policy_backtest(_input([replay_ref], baseline="permissive", candidate="decision_grade"))
    assert report["aggregate_summary"]["mismatches"] == 1
    assert report["comparison_results"][0]["parity_status"] == "mismatch"
    assert "warnings are not permitted" in str(report["comparison_results"][0]["difference_summary"])


def test_missing_replay_artifact_fails_closed() -> None:
    with pytest.raises(QueuePolicyBacktestingError, match="missing replay data"):
        run_queue_policy_backtest(_input(["/tmp/does-not-exist.json"]))


def test_deterministic_comparison(tmp_path: Path) -> None:
    replay_ref = _replay_ref(
        tmp_path,
        step_decision=_step("step-001", decision="warn"),
        transition_decision=_transition("step-001", action="request_review"),
    )
    payload = _input([replay_ref], baseline="permissive", candidate="decision_grade")
    a = run_queue_policy_backtest(payload)
    b = run_queue_policy_backtest(payload)
    assert a == b


def test_schema_and_example_validation() -> None:
    payload = load_example("prompt_queue_policy_backtest_report")
    validate_artifact(payload, "prompt_queue_policy_backtest_report")


def test_cli_returns_non_zero_for_invalid_inputs(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    cmd = [
        sys.executable,
        "scripts/run_prompt_queue_policy_backtest.py",
        "--replay-run-ref",
        str(tmp_path / "missing.audit.json"),
        "--baseline-policy-id",
        "permissive",
        "--baseline-policy-version",
        "1.0.0",
        "--candidate-policy-id",
        "decision_grade",
        "--candidate-policy-version",
        "1.0.0",
        "--output-path",
        str(output),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert completed.returncode != 0
