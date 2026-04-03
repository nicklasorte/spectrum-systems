from __future__ import annotations

import copy
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
import spectrum_systems.modules.runtime.roadmap_multi_batch_executor as multi_batch  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_multi_batch_executor import (  # noqa: E402
    execute_bounded_roadmap_run,
    should_continue_execution,
)


def _roadmap() -> dict:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "completed"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _selection_signals(*, include_j_signal: bool = True, risk_level: str = "medium", program_phase: str = "build") -> dict:
    signals = ["roadmap_authority_resolved", "executor_ingestion_valid"]
    if include_j_signal:
        signals.append("state_binding_complete")
    return {
        "signals": signals,
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
        "risk_level": risk_level,
        "program_phase": program_phase,
    }


def _authorization_signals() -> dict:
    return {
        "trace_id": "trace-rdx-006-test",
        "required_signals_satisfied": True,
        "hard_gate_state": "pass",
        "certification_state": "complete",
        "review_state": "complete",
        "eval_state": "complete",
        "replay_consistency": "match",
        "control_freeze_condition": False,
        "control_block_condition": False,
        "warning_states": [],
    }


def _pqx_success(**_: dict) -> dict:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:ok:1",
                "slice_execution_record_ref": "runs/pqx/slice.record.json",
                "certification_ref": "runs/pqx/cert.record.json",
                "audit_bundle_ref": "runs/pqx/audit.record.json",
            }
        ],
    }


def test_positive_bounded_run_executes_two_and_stops_at_max(tmp_path: Path) -> None:
    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={"max_batches_per_run": 2},
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["attempted_batch_ids"] == ["BATCH-I", "BATCH-J"]
    assert result["completed_batch_ids"] == ["BATCH-I", "BATCH-J"]
    assert result["batches_executed_count"] == 2
    assert result["stop_reason"] == "max_batches_reached"
    assert result["execution_efficiency_report"]["batches_executed_per_run"] == 2


def test_adaptive_policy_resolves_cap_from_risk_and_phase(tmp_path: Path) -> None:
    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(risk_level="low", program_phase="build"),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={
            "max_batches_per_run": {
                "min_cap": 1,
                "max_cap": 4,
                "risk_caps": {"low": 4, "medium": 2, "high": 1},
                "program_phase_caps": {"build": 3, "stabilization": 2},
            }
        },
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["resolved_max_batches_per_run"] == 3
    assert result["execution_efficiency_report"]["adaptive_factors"]["mode"] == "adaptive"


def test_hard_gate_stops_after_completed_batch(tmp_path: Path) -> None:
    roadmap = _roadmap()
    for batch in roadmap["batches"]:
        if batch["batch_id"] == "BATCH-I":
            batch["hard_gate_after"] = True

    result = execute_bounded_roadmap_run(
        roadmap,
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={"max_batches_per_run": 3, "stop_on_hard_gate": True},
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["attempted_batch_ids"] == ["BATCH-I"]
    assert result["completed_batch_ids"] == ["BATCH-I"]
    assert result["stop_reason"] == "hard_gate_stop"


def test_freeze_or_block_stops_without_third_attempt(tmp_path: Path, monkeypatch) -> None:
    real = multi_batch.validate_single_batch_execution_loop
    calls = {"count": 0}

    def _patched(*args, **kwargs):
        calls["count"] += 1
        payload = real(*args, **kwargs)
        if calls["count"] == 2:
            payload["authorization_result"]["control_decision"] = "freeze"
            payload["authorization_result"]["authorized_to_run"] = False
            payload["progress_update"] = None
        return payload

    monkeypatch.setattr(multi_batch, "validate_single_batch_execution_loop", _patched)

    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={"max_batches_per_run": 3},
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["stop_reason"] == "authorization_freeze"
    assert result["attempted_batch_ids"] == ["BATCH-I", "BATCH-J"]


def test_execution_failure_stops_immediately(tmp_path: Path) -> None:
    calls = {"count": 0}

    def _pqx_second_blocked(**_: dict) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            return _pqx_success()
        return {
            "status": "blocked",
            "blocked_reason": "pqx blocked second batch",
            "batch_result": {"status": "blocked"},
            "execution_history": [],
        }

    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={"max_batches_per_run": 3},
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_second_blocked,
    )["run_result"]

    assert result["completed_batch_ids"] == ["BATCH-I"]
    assert result["stop_reason"] == "execution_blocked"


def test_missing_signal_later_batch_stops_before_execution(tmp_path: Path) -> None:
    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(include_j_signal=False),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={"max_batches_per_run": 3},
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["completed_batch_ids"] == ["BATCH-I"]
    assert result["stop_reason"] == "missing_required_signal"


def test_should_continue_execution_supports_early_stop_reason_codes() -> None:
    decision = should_continue_execution(
        last_batch_result={"control_decision": "allow", "replay_integrity": "ready", "execution_status": "succeeded"},
        control_decision="allow",
        context_risk_signals={"risk_level": "medium"},
        program_alignment={"safety_critical": True},
        replay_integrity="ready",
        continuation_state={
            "consecutive_non_progress": 2,
            "repeated_failure_reason_count": 0,
            "unresolved_blocker_streak": 0,
            "risk_accumulation": 0,
            "risk_accumulation_stop_threshold": 6,
        },
    )
    assert decision == {"continue": False, "reason_code": "diminishing_returns_detected"}


def test_determinism_same_inputs_identical_run_result(tmp_path: Path) -> None:
    kwargs = {
        "roadmap_artifact": _roadmap(),
        "selection_signals": _selection_signals(),
        "authorization_signals": _authorization_signals(),
        "pqx_state_path": tmp_path / "pqx" / "state.json",
        "pqx_runs_root": tmp_path / "pqx",
        "execution_policy": {"max_batches_per_run": 2},
        "evaluated_at": "2026-04-03T20:00:00Z",
        "executed_at": "2026-04-03T20:01:00Z",
        "validated_at": "2026-04-03T20:02:00Z",
        "run_executed_at": "2026-04-03T20:03:00Z",
        "pqx_execute_fn": _pqx_success,
    }
    first = execute_bounded_roadmap_run(**kwargs)["run_result"]
    second = execute_bounded_roadmap_run(**kwargs)["run_result"]
    assert first == second


def test_no_reprioritization_and_never_exceeds_max(tmp_path: Path) -> None:
    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={"max_batches_per_run": 1},
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["attempted_batch_ids"] == ["BATCH-I"]
    assert result["batches_executed_count"] == 1
    assert result["max_batches_per_run"] == 1


def test_tuned_non_progress_threshold_stops_earlier(tmp_path: Path) -> None:
    decision = should_continue_execution(
        last_batch_result={"control_decision": "allow", "replay_integrity": "ready", "execution_status": "succeeded"},
        control_decision="allow",
        context_risk_signals={"risk_level": "medium"},
        program_alignment={"safety_critical": True},
        replay_integrity="ready",
        continuation_state={
            "consecutive_non_progress": 1,
            "consecutive_non_progress_stop_threshold": 1,
            "repeated_failure_reason_count": 0,
            "repeated_failure_reason_stop_threshold": 2,
            "unresolved_blocker_streak": 0,
            "unresolved_blocker_stop_threshold": 2,
            "risk_accumulation": 0,
            "risk_accumulation_stop_threshold": 6,
        },
    )
    assert decision == {"continue": False, "reason_code": "diminishing_returns_detected"}


def test_low_risk_bonus_batch_applies_when_enabled(tmp_path: Path) -> None:
    result = execute_bounded_roadmap_run(
        _roadmap(),
        _selection_signals(risk_level="low", program_phase="build"),
        _authorization_signals(),
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        execution_policy={
            "max_batches_per_run": {
                "min_cap": 1,
                "max_cap": 4,
                "risk_caps": {"low": 2, "medium": 2, "high": 1},
                "program_phase_caps": {"build": 2},
                "enable_low_risk_bonus_batch": True,
            }
        },
        evaluated_at="2026-04-03T20:00:00Z",
        executed_at="2026-04-03T20:01:00Z",
        validated_at="2026-04-03T20:02:00Z",
        run_executed_at="2026-04-03T20:03:00Z",
        pqx_execute_fn=_pqx_success,
    )["run_result"]

    assert result["attempted_batch_ids"] == ["BATCH-I", "BATCH-J"]
    assert result["resolved_max_batches_per_run"] == 3
    assert "low_risk_bonus_batch" in result["execution_efficiency_report"]["adaptive_factors"]["resolved_from"]
