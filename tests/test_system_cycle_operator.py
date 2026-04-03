from __future__ import annotations

import copy
from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.system_cycle_operator import run_system_cycle


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
        "control_loop": {
            "eval_present": True,
            "trace_present": True,
            "schema_valid": True,
        },
    }


def _authorization_signals() -> dict:
    return {
        "trace_id": "trace-batch-u-test",
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
        "trace_id": "trace-batch-u-test",
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


def test_full_cycle_deterministic_and_contract_valid() -> None:
    kwargs = dict(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    first = run_system_cycle(**kwargs)
    second = run_system_cycle(**kwargs)
    assert first == second

    validate_artifact(first["next_step_recommendation"], "next_step_recommendation")
    validate_artifact(first["build_summary"], "build_summary")

    assert first["next_step_recommendation"]["next_batch_id"] == "BATCH-J"
    assert first["next_step_recommendation"]["schema_version"] == "1.3.0"
    assert first["build_summary"]["schema_version"] == "1.2.0"
    assert first["build_summary"]["failure_surface"]["stop_reason"] == "max_batches_reached"
    assert first["core_system_integration_validation"]["authority_boundary_status"] == "bounded"
    assert first["build_summary"]["run_outcome"]["status"] == "success"
    assert first["build_summary"]["artifact_index"]["next_step_recommendation"].startswith("next_step_recommendation:NSR-")
    candidate_eval = first["next_step_recommendation"]["candidate_evaluation"]
    assert candidate_eval["ranking_policy"].startswith("program_alignment>")
    assert candidate_eval["candidates"][0]["candidate_id"] == "NSC-EXECUTE-NEXT-BATCH"
    assert first["next_step_recommendation"]["trace_navigation"] == first["core_system_integration_validation"]["trace_navigation"]
    assert first["build_summary"]["trace_navigation"] == first["core_system_integration_validation"]["trace_navigation"]
    assert len(first["build_summary"]["quick_links"]) == 3
    assert len(first["next_step_recommendation"]["quick_links"]) == 3
    assert first["adaptive_execution_observability"]["schema_version"] == "1.0.0"
    assert first["adaptive_execution_trend_report"]["schema_version"] == "1.0.0"
    assert any(item.startswith("adaptive_guardrail_status=") for item in first["next_step_recommendation"]["why"])
    assert any(item.startswith("adaptive_safety_trend=") for item in first["build_summary"]["watch_next"])


def test_failure_surface_exposes_root_cause_and_action() -> None:
    integration_inputs = copy.deepcopy(_integration_inputs())
    integration_inputs["control_decision"]["review_eval_ingested"] = False

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    summary = result["build_summary"]
    assert summary["failure_surface"]["stop_reason"] == "max_batches_reached"
    assert "blocking_condition:PROP_REVIEW_EVAL_NOT_INGESTED" in summary["failure_surface"]["root_cause"]
    assert summary["failure_surface"]["root_cause_chain"] == [
        {"step": "review_or_input_condition", "reason": "PROP_REVIEW_EVAL_NOT_INGESTED"},
        {"step": "evaluation_or_propagation_gap", "reason": "eval_or_propagation_missing"},
        {"step": "control_gate", "reason": "control_block"},
    ]
    assert "resolve blocker PROP_REVIEW_EVAL_NOT_INGESTED" in summary["failure_surface"]["next_action"]
    assert summary["failure_surface"]["blocker_refs"] == ["PROP_REVIEW_EVAL_NOT_INGESTED"]
    assert any(ref.startswith("core_system_integration_validation:") for ref in summary["failure_surface"]["source_refs"])
    assert summary["run_outcome"]["status"] == "blocked"

    recommendation = result["next_step_recommendation"]
    assert "PROP_REVIEW_EVAL_NOT_INGESTED" in recommendation["blockers"]
    assert "cross_layer_propagation_review" in recommendation["required_reviews"]
    assert recommendation["next_step"]["action"].startswith("resolve blocker PROP_REVIEW_EVAL_NOT_INGESTED")
    assert recommendation["next_step"]["blocked_by"] == summary["failure_surface"]["blocker_refs"]
    assert any(item.startswith("primary_blocker=PROP_REVIEW_EVAL_NOT_INGESTED") for item in recommendation["next_step"]["watchouts"])
    assert recommendation["artifact_refs"]["trace_id"] == recommendation["trace_id"]
    assert recommendation["candidate_evaluation"]["why_not_selected"]
    for key in ("replay_from_context", "replay_from_plan", "replay_from_execution", "replay_from_failure"):
        assert recommendation["replay_entry_points"][key]["required_artifacts"]
        assert recommendation["trace_id"] in recommendation["replay_entry_points"][key]["trace_refs"]
        assert summary["trace_id"] in summary["replay_entry_points"][key]["trace_refs"]
    assert recommendation["artifact_refs"]["upstream_refs"]
    assert recommendation["artifact_refs"]["downstream_refs"]
    assert any(item.startswith("adaptive_execution_observability:AEO-") for item in recommendation["artifact_refs"]["related_artifacts"])
    assert any(item.startswith("adaptive_execution_trend_report:AET-") for item in recommendation["artifact_refs"]["related_artifacts"])
    assert summary["artifact_index"]["upstream_refs"]
    assert summary["artifact_index"]["downstream_refs"]
    assert any(item.startswith("adaptive_execution_observability:AEO-") for item in summary["artifact_index"]["related_artifacts"])
    assert any(item.startswith("adaptive_execution_trend_report:AET-") for item in summary["artifact_index"]["related_artifacts"])


def test_candidate_ranking_is_deterministic_and_sorted() -> None:
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    candidates = result["next_step_recommendation"]["candidate_evaluation"]["candidates"]
    scores = [item["score"] for item in candidates]
    assert scores == sorted(scores, reverse=True)
    assert candidates[0]["candidate_id"] == "NSC-EXECUTE-NEXT-BATCH"
    assert result["next_step_recommendation"]["next_step"]["action"] == candidates[0]["action"]


def test_blocked_candidates_prioritize_unblock_path() -> None:
    integration_inputs = copy.deepcopy(_integration_inputs())
    integration_inputs["control_decision"]["review_eval_ingested"] = False

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    selected = result["next_step_recommendation"]["candidate_evaluation"]["candidates"][0]
    assert selected["candidate_id"] == "NSC-RESOLVE-PROP_REVIEW_EVAL_NOT_INGESTED"
    assert result["next_step_recommendation"]["next_step"]["blocked_by"] == ["PROP_REVIEW_EVAL_NOT_INGESTED"]


def test_candidate_generation_consumes_prg_ctx_rvw_signals() -> None:
    integration_inputs = copy.deepcopy(_integration_inputs())
    integration_inputs["program_artifact"]["priority"] = "risk_reduction"
    integration_inputs["context_bundle"]["risks"] = ["replay_drift"]
    integration_inputs["control_decision"]["review_eval_ingested"] = False

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    execute_candidate = next(
        item
        for item in result["next_step_recommendation"]["candidate_evaluation"]["candidates"]
        if item["candidate_id"] == "NSC-EXECUTE-NEXT-BATCH"
    )
    assert execute_candidate["alignment_with_program"]["priority"] == "risk_reduction"
    assert "context_risk=replay_drift" in execute_candidate["risk_profile"]["signals"]
    assert "cross_layer_propagation_review" in result["next_step_recommendation"]["required_reviews"]


def test_authority_boundary_breaks_raise_risk_level() -> None:
    integration_inputs = copy.deepcopy(_integration_inputs())
    integration_inputs["review_control_signal"]["authorizes_execution"] = True

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    assert result["core_system_integration_validation"]["authority_boundary_status"] == "violated"
    assert result["next_step_recommendation"]["risk_summary"]["level"] == "high"
    assert "control_authority_review" in result["next_step_recommendation"]["required_reviews"]
    assert any(
        "control_authority_review" in item for item in result["next_step_recommendation"]["next_step"]["watchouts"]
    )
