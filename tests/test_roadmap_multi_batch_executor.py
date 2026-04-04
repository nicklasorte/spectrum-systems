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
from spectrum_systems.modules.runtime.controlled_multi_cycle_runner import (  # noqa: E402
    run_controlled_multi_cycle,
    run_full_roadmap_execution,
)
from spectrum_systems.modules.runtime.system_cycle_operator import derive_batch_handoff_bundle  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_adjustment_engine import (  # noqa: E402
    RoadmapAdjustmentError,
    apply_roadmap_adjustments,
    derive_roadmap_adjustments,
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


def _authorization_signals_with_decision(decision: str) -> dict:
    base = _authorization_signals()
    base["control_decision"] = decision
    return base


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


def _system_roadmap_for_execution() -> dict:
    return {
        "roadmap_id": "RDX-MULTI-CYCLE-TEST",
        "version": "1.0.0",
        "created_at": "2026-04-04T00:00:00Z",
        "trace_id": "trace-rdx-006-test",
        "batches": [
            {
                "batch_id": "BATCH-I",
                "title": "I",
                "description": "I",
                "priority": 1,
                "status": "not_started",
                "dependencies": [],
            },
            {
                "batch_id": "BATCH-J",
                "title": "J",
                "description": "J",
                "priority": 2,
                "status": "not_started",
                "dependencies": ["BATCH-I"],
            },
            {
                "batch_id": "BATCH-K",
                "title": "K",
                "description": "K",
                "priority": 3,
                "status": "not_started",
                "dependencies": ["BATCH-J"],
            },
            {
                "batch_id": "BATCH-L",
                "title": "L",
                "description": "L",
                "priority": 4,
                "status": "not_started",
                "dependencies": ["BATCH-K"],
            },
            {
                "batch_id": "BATCH-M",
                "title": "M",
                "description": "M",
                "priority": 5,
                "status": "not_started",
                "dependencies": ["BATCH-L"],
            },
        ],
    }


def _roadmap_for_full_execution() -> dict:
    artifact = _roadmap()
    artifact["batches"] = [batch for batch in artifact["batches"] if batch["batch_id"] in {"BATCH-I", "BATCH-J"}]
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-I":
            batch["dependencies"] = []
        if batch["batch_id"] == "BATCH-J":
            batch["dependencies"] = ["BATCH-I"]
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _system_roadmap_for_full_execution() -> dict:
    return {
        "roadmap_id": "RDX-MULTI-CYCLE-TEST",
        "version": "1.0.0",
        "created_at": "2026-04-04T00:00:00Z",
        "trace_id": "trace-rdx-006-test",
        "batches": [
            {"batch_id": "BATCH-I", "title": "I", "description": "I", "priority": 1, "status": "not_started", "dependencies": []},
            {"batch_id": "BATCH-J", "title": "J", "description": "J", "priority": 2, "status": "not_started", "dependencies": ["BATCH-I"]},
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
        {**_selection_signals(), "disallowed_targets": ["BATCH-Z"]},
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
        last_control_decision="freeze",
        program_constraint_signal={},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )
    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["control_freeze"]


def test_should_continue_stops_on_repeated_failure_pattern() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 3, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )
    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["repeated_failure_pattern"]


def test_should_continue_stops_on_program_violation() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={"allowed_targets": ["BATCH-J"]},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-I"},
    )
    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["program_violation_disallowed_target"]


def test_should_continue_safe_path_continues() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={"allowed_targets": ["BATCH-I", "BATCH-J"], "priority_ordering": ["BATCH-I", "BATCH-J"]},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "low"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-I"},
    )
    assert decision["decision"] == "continue"


def test_controlled_multi_cycle_is_deterministic_and_contract_valid(tmp_path: Path) -> None:
    kwargs = dict(
        system_roadmap=_system_roadmap_for_execution(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={
            "program_artifact": {"program_id": "PRG-1"},
            "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
            "eval_result": {"run_id": "eval-1", "result_status": "pass"},
            "context_bundle": {"context_id": "ctx-1"},
            "tpa_gate": {"context_bundle_ref": "context_bundle_v2:ctx-1", "speculative_expansion_detected": False, "gate_replaces_control": False},
            "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
            "control_decision": {"decision": "allow", "review_eval_ingested": True},
            "certification_pack": {"certification_status": "complete"},
            "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
            "trace_id": "trace-rdx-006-test",
            "source_refs": {},
        },
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        max_cycles_per_invocation=2,
        stop_on_first_refusal=False,
        stop_on_blocked_batch=True,
        pqx_execute_fn=_pqx_success,
    )
    first = run_controlled_multi_cycle(**kwargs)
    second = run_controlled_multi_cycle(**kwargs)
    assert first["multi_cycle_execution_report"] == second["multi_cycle_execution_report"]
    assert first["multi_cycle_execution_report"]["executed_batch_ids"] == ["BATCH-I", "BATCH-J"]
    assert first["multi_cycle_execution_report"]["stop_reason"] == "max_cycles_reached"


def test_controlled_multi_cycle_stops_on_blocked_batch_when_configured(tmp_path: Path) -> None:
    def _blocked(**_: dict) -> dict:
        return {"status": "blocked", "blocked_reason": "blocked", "batch_result": {"status": "blocked"}, "execution_history": []}

    result = run_controlled_multi_cycle(
        system_roadmap=_system_roadmap_for_execution(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={
            "program_artifact": {"program_id": "PRG-1"},
            "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
            "eval_result": {"run_id": "eval-1", "result_status": "pass"},
            "context_bundle": {"context_id": "ctx-1"},
            "tpa_gate": {"context_bundle_ref": "context_bundle_v2:ctx-1", "speculative_expansion_detected": False, "gate_replaces_control": False},
            "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
            "control_decision": {"decision": "allow", "review_eval_ingested": True},
            "certification_pack": {"certification_status": "complete"},
            "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
            "trace_id": "trace-rdx-006-test",
            "source_refs": {},
        },
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        max_cycles_per_invocation=3,
        stop_on_first_refusal=True,
        stop_on_blocked_batch=True,
        pqx_execute_fn=_blocked,
    )
    report = result["multi_cycle_execution_report"]
    assert report["stop_reason"] == "blocked_batch"
    assert report["total_cycles_refused"] >= 1


def test_full_roadmap_execution_completes_under_all_allow_path(tmp_path: Path, monkeypatch) -> None:
    calls = {"index": 0}

    def _fake_run_controlled_multi_cycle(**kwargs):
        calls["index"] += 1
        batch = "BATCH-I" if calls["index"] == 1 else "BATCH-J"
        updated_system = copy.deepcopy(kwargs["system_roadmap"])
        for item in updated_system["batches"]:
            if item["batch_id"] == batch:
                item["status"] = "completed"
        return {
            "multi_cycle_execution_report": {
                "executed_batch_ids": [batch],
                "refused_batch_ids": [],
                "stop_reason": "max_cycles_reached",
            },
            "updated_system_roadmap": updated_system,
            "updated_roadmap": kwargs["roadmap_artifact"],
            "cycle_outputs": [],
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.controlled_multi_cycle_runner.run_controlled_multi_cycle",
        _fake_run_controlled_multi_cycle,
    )

    result = run_full_roadmap_execution(
        system_roadmap=_system_roadmap_for_full_execution(),
        roadmap_artifact=_roadmap_for_full_execution(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals_with_decision("allow"),
        integration_inputs={
            "program_artifact": {"program_id": "PRG-1"},
            "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
            "eval_result": {"run_id": "eval-1", "result_status": "pass"},
            "context_bundle": {"context_id": "ctx-1"},
            "tpa_gate": {"context_bundle_ref": "context_bundle_v2:ctx-1", "speculative_expansion_detected": False, "gate_replaces_control": False},
            "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
            "control_decision": {"decision": "allow", "review_eval_ingested": True},
            "certification_pack": {"certification_status": "complete"},
            "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
            "trace_id": "trace-rdx-006-test",
            "source_refs": {},
        },
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        max_cycles=5,
        max_continuation_depth=5,
        pqx_execute_fn=_pqx_success,
    )
    report = result["roadmap_execution_report"]
    assert report["stop_reason"] == "roadmap_complete"
    assert report["batches_executed"] == 2
    assert report["batches_blocked"] == 0
    assert report["final_control_decision"] == "allow"


def test_full_roadmap_execution_stops_on_block(tmp_path: Path) -> None:
    report = run_full_roadmap_execution(
        system_roadmap=_system_roadmap_for_full_execution(),
        roadmap_artifact=_roadmap_for_full_execution(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals_with_decision("block"),
        integration_inputs={},
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_success,
    )["roadmap_execution_report"]
    assert report["stop_reason"] == "control_block"
    assert report["final_control_decision"] == "block"
    assert report["execution_sequence"] == []


def test_full_roadmap_execution_stops_on_freeze(tmp_path: Path) -> None:
    report = run_full_roadmap_execution(
        system_roadmap=_system_roadmap_for_full_execution(),
        roadmap_artifact=_roadmap_for_full_execution(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals_with_decision("freeze"),
        integration_inputs={},
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_success,
    )["roadmap_execution_report"]
    assert report["stop_reason"] == "control_freeze"
    assert report["final_control_decision"] == "freeze"


def test_full_roadmap_execution_warn_path_continues(tmp_path: Path, monkeypatch) -> None:
    calls = {"index": 0}

    def _fake_run_controlled_multi_cycle(**kwargs):
        calls["index"] += 1
        batch = "BATCH-I" if calls["index"] == 1 else "BATCH-J"
        updated_system = copy.deepcopy(kwargs["system_roadmap"])
        for item in updated_system["batches"]:
            if item["batch_id"] == batch:
                item["status"] = "completed"
        return {
            "multi_cycle_execution_report": {
                "executed_batch_ids": [batch],
                "refused_batch_ids": [],
                "stop_reason": "max_cycles_reached",
            },
            "updated_system_roadmap": updated_system,
            "updated_roadmap": kwargs["roadmap_artifact"],
            "cycle_outputs": [],
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.controlled_multi_cycle_runner.run_controlled_multi_cycle",
        _fake_run_controlled_multi_cycle,
    )

    report = run_full_roadmap_execution(
        system_roadmap=_system_roadmap_for_full_execution(),
        roadmap_artifact=_roadmap_for_full_execution(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals_with_decision("warn"),
        integration_inputs={
            "program_artifact": {"program_id": "PRG-1"},
            "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
            "eval_result": {"run_id": "eval-1", "result_status": "pass"},
            "context_bundle": {"context_id": "ctx-1"},
            "tpa_gate": {"context_bundle_ref": "context_bundle_v2:ctx-1", "speculative_expansion_detected": False, "gate_replaces_control": False},
            "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
            "control_decision": {"decision": "warn", "review_eval_ingested": True},
            "certification_pack": {"certification_status": "complete"},
            "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
            "trace_id": "trace-rdx-006-test",
            "source_refs": {},
        },
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        max_cycles=5,
        max_continuation_depth=5,
        pqx_execute_fn=_pqx_success,
    )["roadmap_execution_report"]
    assert report["stop_reason"] == "roadmap_complete"
    assert report["final_control_decision"] == "warn"
    assert report["batches_warned"] > 0
    assert report["batches_executed"] == 2


def test_full_roadmap_execution_sequence_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    def _fake_run_controlled_multi_cycle(**kwargs):
        pending = [b["batch_id"] for b in kwargs["system_roadmap"]["batches"] if b["status"] != "completed"]
        batch = pending[0]
        updated_system = copy.deepcopy(kwargs["system_roadmap"])
        for item in updated_system["batches"]:
            if item["batch_id"] == batch:
                item["status"] = "completed"
        return {
            "multi_cycle_execution_report": {
                "executed_batch_ids": [batch],
                "refused_batch_ids": [],
                "stop_reason": "max_cycles_reached",
            },
            "updated_system_roadmap": updated_system,
            "updated_roadmap": kwargs["roadmap_artifact"],
            "cycle_outputs": [],
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.controlled_multi_cycle_runner.run_controlled_multi_cycle",
        _fake_run_controlled_multi_cycle,
    )

    kwargs = dict(
        system_roadmap=_system_roadmap_for_full_execution(),
        roadmap_artifact=_roadmap_for_full_execution(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals_with_decision("allow"),
        integration_inputs={
            "program_artifact": {"program_id": "PRG-1"},
            "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
            "eval_result": {"run_id": "eval-1", "result_status": "pass"},
            "context_bundle": {"context_id": "ctx-1"},
            "tpa_gate": {"context_bundle_ref": "context_bundle_v2:ctx-1", "speculative_expansion_detected": False, "gate_replaces_control": False},
            "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
            "control_decision": {"decision": "allow", "review_eval_ingested": True},
            "certification_pack": {"certification_status": "complete"},
            "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
            "trace_id": "trace-rdx-006-test",
            "source_refs": {},
        },
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        max_cycles=5,
        max_continuation_depth=5,
        pqx_execute_fn=_pqx_success,
    )
    first = run_full_roadmap_execution(**kwargs)["roadmap_execution_report"]
    second = run_full_roadmap_execution(**kwargs)["roadmap_execution_report"]
    assert first == second
    assert [step["batch_id"] for step in first["execution_sequence"]] == ["BATCH-I", "BATCH-J"]


def test_full_roadmap_execution_report_correctness(tmp_path: Path, monkeypatch) -> None:
    calls = {"index": 0}

    def _fake_run_controlled_multi_cycle(**kwargs):
        calls["index"] += 1
        batch = "BATCH-I" if calls["index"] == 1 else "BATCH-J"
        updated_system = copy.deepcopy(kwargs["system_roadmap"])
        for item in updated_system["batches"]:
            if item["batch_id"] == batch:
                item["status"] = "completed"
        return {
            "multi_cycle_execution_report": {
                "executed_batch_ids": [batch],
                "refused_batch_ids": [],
                "stop_reason": "max_cycles_reached",
            },
            "updated_system_roadmap": updated_system,
            "updated_roadmap": kwargs["roadmap_artifact"],
            "cycle_outputs": [],
        }

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.controlled_multi_cycle_runner.run_controlled_multi_cycle",
        _fake_run_controlled_multi_cycle,
    )

    report = run_full_roadmap_execution(
        system_roadmap=_system_roadmap_for_full_execution(),
        roadmap_artifact=_roadmap_for_full_execution(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals_with_decision("allow"),
        integration_inputs={
            "program_artifact": {"program_id": "PRG-1"},
            "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
            "eval_result": {"run_id": "eval-1", "result_status": "pass"},
            "context_bundle": {"context_id": "ctx-1"},
            "tpa_gate": {"context_bundle_ref": "context_bundle_v2:ctx-1", "speculative_expansion_detected": False, "gate_replaces_control": False},
            "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
            "control_decision": {"decision": "allow", "review_eval_ingested": True},
            "certification_pack": {"certification_status": "complete"},
            "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
            "trace_id": "trace-rdx-006-test",
            "source_refs": {},
        },
        pqx_state_path=tmp_path / "pqx" / "state.json",
        pqx_runs_root=tmp_path / "pqx",
        created_at="2026-04-04T00:00:00Z",
        max_cycles=5,
        max_continuation_depth=5,
        pqx_execute_fn=_pqx_success,
    )["roadmap_execution_report"]
    assert report["roadmap_id"] == "RDX-MULTI-CYCLE-TEST"
    assert report["total_batches"] == 2
    assert report["batches_executed"] == len(report["execution_sequence"])
    assert report["determinism_status"] == "deterministic"
    assert report["replay_status"] == "parity_verified"
    assert report["trace_integrity_status"] == "complete"
    assert report["trace_id"].startswith("trace-")


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


def test_eval_health_degraded_stops(tmp_path: Path) -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "degraded"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-I"},
    )
    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["eval_health_degraded"]


def test_adjustments_missing_eval_insert_and_deterministic() -> None:
    roadmap = _roadmap()
    exception_resolution = copy.deepcopy(load_example("exception_resolution_record"))
    handoff = copy.deepcopy(load_example("batch_handoff_bundle"))
    handoff["source_batch_id"] = "BATCH-I"
    handoff["roadmap_id"] = roadmap["roadmap_id"]
    handoff["latest_exception_class"] = "missing_eval_coverage"
    handoff["trace_id"] = "trace-a4-adjust-1"
    first = derive_roadmap_adjustments(
        roadmap_artifact=roadmap,
        exception_resolution_record=exception_resolution,
        batch_handoff_bundle=handoff,
        eval_coverage_signal={"coverage_gap_detected": True},
        drift_signals={"drift_detected": False, "repeated_failure": False},
        unresolved_risks=[],
        created_at="2026-04-04T00:00:00Z",
    )
    second = derive_roadmap_adjustments(
        roadmap_artifact=roadmap,
        exception_resolution_record=exception_resolution,
        batch_handoff_bundle=handoff,
        eval_coverage_signal={"coverage_gap_detected": True},
        drift_signals={"drift_detected": False, "repeated_failure": False},
        unresolved_risks=[],
        created_at="2026-04-04T00:00:00Z",
    )
    assert first == second
    assert any(item["adjustment_type"] == "insert" for item in first)
    updated = apply_roadmap_adjustments(roadmap_artifact=roadmap, adjustments=first, created_at="2026-04-04T00:00:00Z")
    ids = [row["batch_id"] for row in updated["batches"]]
    assert "BATCH-R" in ids
    target = next(row for row in updated["batches"] if row["batch_id"] == "BATCH-I")
    assert target["depends_on"] == ["BATCH-R"]


def test_adjustments_drift_defer_block_review_and_repeated_failure() -> None:
    roadmap = _roadmap()
    exception_resolution = copy.deepcopy(load_example("exception_resolution_record"))
    exception_resolution["requires_human_review"] = True
    handoff = copy.deepcopy(load_example("batch_handoff_bundle"))
    handoff["source_batch_id"] = "BATCH-I"
    handoff["roadmap_id"] = roadmap["roadmap_id"]
    handoff["latest_exception_class"] = "drift_detected"
    handoff["trace_id"] = "trace-a4-adjust-2"
    adjustments = derive_roadmap_adjustments(
        roadmap_artifact=roadmap,
        exception_resolution_record=exception_resolution,
        batch_handoff_bundle=handoff,
        eval_coverage_signal={"coverage_gap_detected": False},
        drift_signals={"drift_detected": True, "repeated_failure": True},
        unresolved_risks=["critical_risk:AUTH_SIGNOFF_MISSING"],
        created_at="2026-04-04T00:00:00Z",
    )
    kinds = {item["adjustment_type"] for item in adjustments}
    assert {"defer", "block", "annotate", "reorder"}.issubset(kinds)


def test_invalid_adjustment_fails_closed() -> None:
    roadmap = _roadmap()
    bad = {
        "adjustment_id": "RADJ-ABCDEF123456",
        "roadmap_id": roadmap["roadmap_id"],
        "source_batch_id": "BATCH-I",
        "source_exception_ref": "exception_classification_record:ECR-ABCDEF123456",
        "adjustment_type": "insert",
        "target_batch_id": "BATCH-Z",
        "new_position": 1,
        "reason_codes": ["missing_eval_coverage"],
        "supporting_signals": ["eval_coverage_gap"],
        "affected_dependencies": [],
        "safety_classification": "governed_change",
        "requires_human_review": True,
        "created_at": "2026-04-04T00:00:00Z",
        "trace_id": "trace-a4-bad",
    }
    try:
        apply_roadmap_adjustments(roadmap_artifact=roadmap, adjustments=[bad], created_at="2026-04-04T00:00:00Z")
    except RoadmapAdjustmentError as exc:
        assert "target batch does not exist" in str(exc)
    else:
        raise AssertionError("expected fail-closed adjustment error")


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


def test_should_continue_returns_escalate_when_manual_review_required() -> None:
    decision = should_continue_execution(
        last_control_decision="require_review",
        program_constraint_signal={},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium", "escalation_required": True},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )

    assert decision["decision"] == "escalate"
    assert decision["reason_codes"] == ["manual_review_required"]


def test_should_continue_stops_on_program_priority_violation() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={"priority_ordering": ["BATCH-K"]},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )

    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["program_priority_violation"]


def test_should_continue_stops_on_disallowed_target() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={"disallowed_targets": ["BATCH-I"]},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )
    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["program_disallowed_target"]


def test_should_continue_priority_warn_mode_escalates() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={"priority_ordering": ["BATCH-K"], "enforcement_mode": "warn"},
        program_drift_signal={"drift_level": "low"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )
    assert decision["decision"] == "escalate"
    assert decision["reason_codes"] == ["program_priority_violation_warn"]


def test_execute_bounded_run_blocks_when_roadmap_program_alignment_invalid(tmp_path: Path) -> None:
    roadmap = _roadmap()
    for batch in roadmap["batches"]:
        if batch["batch_id"] == "BATCH-I":
            batch["batch_id"] = "BATCH-Z"
            break
    result = execute_bounded_roadmap_run(
        roadmap,
        {**_selection_signals(), "disallowed_targets": ["BATCH-Z"]},
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
    assert result["stop_reason"] == "program_alignment_invalid"
    assert result["stop_reason_codes"] == ["program_alignment_invalid"]
    assert result["execution_path_type"] == "negative_path"
    assert result["program_alignment_status"] == "misaligned"
    assert result["program_stop_cause"] == "program_alignment_invalid"
    assert result["program_drift_severity"] == "low"
    assert result["attempted_batch_ids"] == []


def test_should_continue_stops_on_program_drift_detected() -> None:
    decision = should_continue_execution(
        last_control_decision="allow",
        program_constraint_signal={},
        program_drift_signal={"drift_level": "high"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        eval_summary={"health": "healthy"},
        risk_signals={"risk_level": "medium"},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
    )
    assert decision["decision"] == "stop"
    assert decision["reason_codes"] == ["program_drift_detected"]


def test_delivery_to_handoff_derivation_is_deterministic_and_stale_items_removed() -> None:
    delivery = {
        "report_id": "BDR-111111111111",
        "schema_version": "1.0.0",
        "batch_id": "BATCH-I",
        "roadmap_id": "RDX-CANVAS-2026-04-04",
        "intent": "deterministic test",
        "status": "completed_with_risk",
        "files_changed": [],
        "contracts_added_or_updated": [],
        "tests_run": [],
        "results_summary": ["ok"],
        "remaining_risks": ["critical_risk:AUTH_REVIEW_PENDING", "risk:minor"],
        "open_followups": [
            "validation:pytest tests/test_contract_enforcement.py",
            "contract:batch_handoff_bundle@1.0.0",
            "autonomy_blocker:autonomy:review_gate_required",
        ],
        "recommended_next_batch": "BATCH-J",
        "blocking_issues": ["PROP_REVIEW_EVAL_NOT_INGESTED"],
        "evidence_refs": [
            "roadmap_multi_batch_run_result:RMB-111111111111",
            "autonomy_decision_record:ADR-8B9C0D1E2F3A",
        ],
        "source_refs": ["roadmap_artifact:inline"],
        "trace_id": "trace-derive-test",
        "created_at": "2026-04-04T00:00:00Z",
    }
    first = derive_batch_handoff_bundle(delivery)
    second = derive_batch_handoff_bundle(delivery)
    assert first == second
    assert first["must_carry_forward_risks"] == ["critical_risk:AUTH_REVIEW_PENDING", "risk:minor"]
    assert first["required_validations_next"] == ["validation:pytest tests/test_contract_enforcement.py"]
    assert first["autonomy_blockers"] == ["autonomy_blocker:autonomy:review_gate_required"]
    assert first["autonomy_decision_ref"] == "autonomy_decision_record:ADR-8B9C0D1E2F3A"
    assert first["capability_readiness_state"] == "constrained"
    assert first["capability_readiness_ref"] == "capability_readiness_record:CRD-000000000000"
    assert first["failure_taxonomy_ref"] == "failure_taxonomy_record:FTX-000000000000"
    assert first["rollback_plan_ref"] == "rollback_plan_record:RBP-000000000000"
    assert first["promotion_consistency_ref"] == "promotion_consistency_record:PCR-000000000000"

    resolved_delivery = dict(delivery)
    resolved_delivery["remaining_risks"] = []
    resolved_delivery["open_followups"] = []
    resolved_delivery["blocking_issues"] = []
    resolved_delivery["report_id"] = "BDR-222222222222"
    resolved = derive_batch_handoff_bundle(resolved_delivery)
    assert resolved["must_carry_forward_risks"] == []
    assert resolved["open_contract_work"] == []
    assert resolved["open_review_findings"] == []
    assert resolved["autonomy_blockers"] == []


def test_derived_handoff_bundle_carries_ltv_a_refs() -> None:
    delivery = load_example("batch_delivery_report")
    delivery["evidence_refs"] = sorted(set(list(delivery["evidence_refs"]) + [
        "judgment_lifecycle_record:JLC-1234567890AB",
        "precedent_selection_record:PSL-1234567890AB",
        "precedent_conflict_record:PCF-1234567890AB",
        "override_governance_record:OVG-1234567890AB",
    ]))
    bundle = derive_batch_handoff_bundle(delivery)
    assert "judgment_lifecycle_record:JLC-1234567890AB" in bundle["judgment_lifecycle_refs"]
    assert "precedent_selection_record:PSL-1234567890AB" in bundle["precedent_selection_refs"]
    assert "precedent_conflict_record:PCF-1234567890AB" in bundle["precedent_conflict_refs"]
    assert "override_governance_record:OVG-1234567890AB" in bundle["override_governance_refs"]
