from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.next_governed_cycle_runner import run_next_governed_cycle


def _roadmap() -> dict:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "completed"
        if batch["batch_id"] == "BATCH-I":
            batch["status"] = "not_started"
        if batch["batch_id"] == "BATCH-J":
            batch["status"] = "not_started"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _selection_signals() -> dict:
    return {
        "signals": ["executor_ingestion_valid", "state_binding_complete"],
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
    }


def _authorization_signals() -> dict:
    return {
        "trace_id": "trace-next-cycle-example",
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


def _integration_inputs() -> dict:
    return {
        "known_cycle_runner_result_ids": ["CRR-1A2B3C4D5E6F"],
        "program_artifact": {"program_id": "PRG-1"},
        "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
        "eval_result": {"run_id": "eval-1", "result_status": "pass"},
        "context_bundle": {"context_id": "ctx-1"},
        "tpa_gate": {
            "context_bundle_ref": "context_bundle_v2:ctx-1",
            "speculative_expansion_detected": False,
            "gate_replaces_control": False,
        },
        "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
        "control_decision": {"decision": "allow", "review_eval_ingested": True},
        "certification_pack": {"certification_status": "complete"},
        "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
        "trace_id": "trace-next-cycle-example",
        "source_refs": {
            "program_artifact": "program_artifact:PRG-1",
            "review_control_signal": "review_control_signal:rcs-1",
            "eval_result": "eval_result:eval-1",
            "context_bundle_v2": "context_bundle_v2:ctx-1",
            "tpa_gate": "tpa_gate:gate-1",
            "roadmap_execution_loop_validation": "roadmap_execution_loop_validation:RLV-TEST-001",
            "roadmap_multi_batch_run_result": "roadmap_multi_batch_run_result:RMB-TEST-001",
            "control_decision": "control_execution_result:ctrl-1",
            "certification_pack": "control_loop_certification_pack:cert-1",
        },
    }


def _pqx_stub(**_: object) -> dict:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:queue-batch-i:RDX-002:1",
                "slice_execution_record_ref": "runs/pqx/RDX-002.pqx_slice_execution_record.json",
                "certification_ref": "runs/pqx/RDX-002.done_certification_record.json",
                "audit_bundle_ref": "runs/pqx/RDX-002.pqx_slice_audit_bundle.json",
            }
        ],
    }


def _decision(decision: str = "run_next_cycle") -> dict:
    payload = copy.deepcopy(load_example("next_cycle_decision"))
    payload["decision"] = decision
    return payload


def _bundle() -> dict:
    return copy.deepcopy(load_example("next_cycle_input_bundle"))


def test_runner_refuses_when_decision_stop() -> None:
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("stop"),
        next_cycle_input_bundle=_bundle(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    artifact = result["cycle_runner_result"]
    validate_artifact(artifact, "cycle_runner_result")
    assert artifact["execution_status"] == "refused"
    assert artifact["attempted_execution"] is False
    assert "decision_stop" in artifact["refusal_reason_codes"]
    assert result["executed_cycle"] is None


def test_runner_refuses_when_decision_escalate() -> None:
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("escalate"),
        next_cycle_input_bundle=_bundle(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    artifact = result["cycle_runner_result"]
    assert artifact["execution_status"] == "refused"
    assert "decision_escalate" in artifact["refusal_reason_codes"]


def test_runner_refuses_on_missing_bundle_fields() -> None:
    bundle = _bundle()
    bundle.pop("context_refs", None)
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=bundle,
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    artifact = result["cycle_runner_result"]
    assert artifact["execution_status"] == "refused"
    assert "input_bundle_missing_required_field" in artifact["refusal_reason_codes"]


def test_runner_refuses_when_continuation_depth_exceeded() -> None:
    bundle = _bundle()
    bundle["continuation_depth"] = 5
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=bundle,
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    artifact = result["cycle_runner_result"]
    assert artifact["execution_status"] == "refused"
    assert "continuation_depth_exceeded" in artifact["refusal_reason_codes"]
    assert artifact["refusal_severity"] == "abnormal"


def test_runner_refuses_on_provenance_chain_mismatch() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["known_cycle_runner_result_ids"] = ["CRR-FFFFFFFFFFFF"]
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=_bundle(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    artifact = result["cycle_runner_result"]
    assert artifact["execution_status"] == "refused"
    assert "provenance_chain_invalid" in artifact["refusal_reason_codes"]


def test_required_reviews_do_not_block_execution() -> None:
    bundle = _bundle()
    bundle["required_reviews"] = ["cross_layer_propagation_review"]
    bundle["unresolved_blockers"] = []
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=bundle,
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    assert result["cycle_runner_result"]["execution_status"] == "executed"


def test_runner_executes_exactly_one_cycle_when_allowed() -> None:
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=_bundle(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    artifact = result["cycle_runner_result"]
    validate_artifact(artifact, "cycle_runner_result")
    assert artifact["execution_status"] == "executed"
    assert artifact["replay_entry_point"]["input_artifact_refs"]
    assert artifact["attempted_execution"] is True
    assert artifact["executed_cycle_id"].startswith("RMB-")
    assert result["executed_cycle"] is not None
    assert len(result["executed_cycle"]["roadmap_multi_batch_run_result"]["attempted_batch_ids"]) == 1


def test_runner_result_is_deterministic_for_same_inputs() -> None:
    kwargs = dict(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=_bundle(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    first = run_next_governed_cycle(**kwargs)
    second = run_next_governed_cycle(**kwargs)
    assert first["cycle_runner_result"] == second["cycle_runner_result"]


def test_runner_does_not_recurse_into_second_cycle() -> None:
    result = run_next_governed_cycle(
        next_cycle_decision=_decision("run_next_cycle"),
        next_cycle_input_bundle=_bundle(),
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    executed_cycle = result["executed_cycle"]
    assert executed_cycle is not None
    assert executed_cycle["next_cycle_decision"]["decision"] in {"run_next_cycle", "stop", "escalate"}
    # boundedness: runner emits refs for a single executed cycle and stops
    assert len([ref for ref in result["cycle_runner_result"]["emitted_artifact_refs"] if ref.startswith("roadmap_multi_batch_run_result:")]) == 1


def test_cli_help_and_basic_invocation(tmp_path: Path) -> None:
    help_run = subprocess.run(
        [sys.executable, "scripts/run_next_governed_cycle.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_run.returncode == 0
    assert "--next-cycle-decision" in help_run.stdout

    decision_path = tmp_path / "next_cycle_decision.json"
    bundle_path = tmp_path / "next_cycle_input_bundle.json"
    roadmap_path = tmp_path / "roadmap.json"
    selection_path = tmp_path / "selection.json"
    auth_path = tmp_path / "auth.json"
    integration_path = tmp_path / "integration.json"
    result_path = tmp_path / "cycle_runner_result.json"

    decision_path.write_text(json.dumps(_decision("stop")), encoding="utf-8")
    bundle_path.write_text(json.dumps(_bundle()), encoding="utf-8")
    roadmap_path.write_text(json.dumps(_roadmap()), encoding="utf-8")
    selection_path.write_text(json.dumps(_selection_signals()), encoding="utf-8")
    auth_path.write_text(json.dumps(_authorization_signals()), encoding="utf-8")
    integration_path.write_text(json.dumps(_integration_inputs()), encoding="utf-8")

    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_next_governed_cycle.py",
            "--next-cycle-decision",
            str(decision_path),
            "--next-cycle-input-bundle",
            str(bundle_path),
            "--roadmap-artifact",
            str(roadmap_path),
            "--selection-signals",
            str(selection_path),
            "--authorization-signals",
            str(auth_path),
            "--integration-inputs",
            str(integration_path),
            "--pqx-state-path",
            "tests/fixtures/pqx_runs/state.json",
            "--pqx-runs-root",
            "tests/fixtures/pqx_runs",
            "--output-cycle-runner-result",
            str(result_path),
            "--created-at",
            "2026-04-04T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    validate_artifact(payload, "cycle_runner_result")
    assert payload["execution_status"] == "refused"
