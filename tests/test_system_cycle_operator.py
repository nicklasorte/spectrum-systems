from __future__ import annotations

import copy
import json
from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.roadmap_selector import load_active_roadmap, select_next_batch
from spectrum_systems.modules.runtime import system_cycle_operator as sco
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
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    first = run_system_cycle(**kwargs)
    second = run_system_cycle(**kwargs)
    assert first == second

    validate_artifact(first["next_step_recommendation"], "next_step_recommendation")
    validate_artifact(first["build_summary"], "build_summary")
    validate_artifact(first["batch_delivery_report"], "batch_delivery_report")
    validate_artifact(first["batch_handoff_bundle"], "batch_handoff_bundle")
    validate_artifact(first["capability_readiness_record"], "capability_readiness_record")
    validate_artifact(first["autonomy_decision_record"], "autonomy_decision_record")
    validate_artifact(first["decision_proof_record"], "decision_proof_record")
    validate_artifact(first["allow_decision_proof"], "allow_decision_proof")
    for signal in first["unknown_state_signals"]:
        validate_artifact(signal, "unknown_state_signal")
    validate_artifact(first["exception_classification_record"], "exception_classification_record")
    validate_artifact(first["exception_resolution_record"], "exception_resolution_record")
    validate_artifact(first["failure_taxonomy_record"], "failure_taxonomy_record")
    if first["correction_pattern_record"] is not None:
        validate_artifact(first["correction_pattern_record"], "correction_pattern_record")
    validate_artifact(first["rollback_plan_record"], "rollback_plan_record")
    validate_artifact(first["promotion_consistency_record"], "promotion_consistency_record")
    for record in first["continuous_eval_run_records"]:
        validate_artifact(record, "continuous_eval_run_record")
    validate_artifact(first["system_budget_status"], "system_budget_status")
    validate_artifact(first["canary_rollout_record"], "canary_rollout_record")
    validate_artifact(first["trust_posture_snapshot"], "trust_posture_snapshot")
    validate_artifact(first["artifact_family_health_report"], "artifact_family_health_report")
    validate_artifact(first["evidence_gap_hotspot_report"], "evidence_gap_hotspot_report")
    validate_artifact(first["override_hotspot_report"], "override_hotspot_report")

    assert first["next_step_recommendation"]["next_batch_id"] == "BATCH-J"
    assert first["next_step_recommendation"]["schema_version"] == "1.7.0"
    assert first["build_summary"]["schema_version"] == "1.11.0"
    assert first["next_step_recommendation"]["continuation_decision"] in {"continue", "stop", "escalate"}
    assert first["build_summary"]["continuation_decision"] in {"continue", "stop", "escalate"}
    assert first["next_step_recommendation"]["next_batch_candidate"] == first["next_step_recommendation"]["next_batch_id"]
    assert first["build_summary"]["next_batch_candidate"] == first["next_step_recommendation"]["next_batch_id"]
    assert first["next_step_recommendation"]["execution_path_type"] == "positive_path"
    assert first["next_step_recommendation"]["program_alignment_status"] == "aligned"
    assert first["next_step_recommendation"]["program_stop_cause"] == "none"
    assert first["next_step_recommendation"]["program_drift_severity"] in {"low", "medium", "high"}
    assert first["build_summary"]["execution_path_type"] == "positive_path"
    assert first["build_summary"]["program_alignment_status"] == "aligned"
    assert first["build_summary"]["program_stop_cause"] == "none"
    assert first["build_summary"]["program_drift_severity"] in {"low", "medium", "high"}
    assert first["build_summary"]["failure_surface"]["stop_reason"] == "max_batches_reached"
    assert first["next_step_recommendation"]["next_cycle_decision"] == "run_next_cycle"
    assert first["build_summary"]["next_cycle_decision"] == "run_next_cycle"
    assert first["next_step_recommendation"]["next_cycle_inputs_ref"].startswith("next_cycle_input_bundle:NCB-")
    assert first["build_summary"]["next_cycle_inputs_ref"] == first["next_step_recommendation"]["next_cycle_inputs_ref"]
    assert first["build_summary"]["autonomy_decision"] in {"continue", "stop", "require_human_review", "escalate"}
    assert first["build_summary"]["autonomy_reason_codes"]
    assert first["build_summary"]["autonomy_decision_ref"].startswith("autonomy_decision_record:ADR-")
    assert first["next_cycle_input_bundle"]["autonomy_decision_ref"] == first["build_summary"]["autonomy_decision_ref"]
    assert isinstance(first["next_cycle_input_bundle"]["autonomy_blockers"], list)
    assert first["build_summary"]["exception_class"] == first["exception_classification_record"]["exception_class"]
    assert first["build_summary"]["recommended_exception_action"] == first["exception_resolution_record"]["recommended_action"]
    assert first["next_cycle_input_bundle"]["latest_exception_class"] == first["exception_classification_record"]["exception_class"]
    assert first["next_cycle_input_bundle"]["latest_exception_resolution_action"] == first["exception_resolution_record"]["recommended_action"]
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
    assert first["adaptive_execution_policy_review"]["schema_version"] == "1.0.0"
    assert any(item.startswith("adaptive_guardrail_status=") for item in first["next_step_recommendation"]["why"])
    assert any(item.startswith("adaptive_safety_trend=") for item in first["build_summary"]["watch_next"])
    assert any(item.startswith("adaptive_policy_tuning_signal=") for item in first["build_summary"]["watch_next"])
    remediation = first["next_step_recommendation"]["remediation_plan"]
    assert first["next_step_recommendation"]["remediation_plan_ref"] == f"remediation_plan:{remediation['plan_id']}"
    assert first["next_step_recommendation"]["remediation_steps"] == remediation["remediation_steps"]
    assert remediation["trace_id"] == first["next_step_recommendation"]["trace_id"]
    assert remediation["required_artifacts"]
    validate_artifact(first["next_cycle_decision"], "next_cycle_decision")
    validate_artifact(first["next_cycle_input_bundle"], "next_cycle_input_bundle")
    assert first["next_cycle_decision"]["allow_decision_proof_ref"].startswith("allow_decision_proof:ADP-")
    assert first["next_cycle_input_bundle"]["decision_proof_ref"].startswith("decision_proof_record:DPR-")
    assert first["next_cycle_input_bundle"]["allow_decision_proof_ref"] == first["next_cycle_decision"]["allow_decision_proof_ref"]
    assert first["build_summary"]["decision_proof_ref"] == first["next_cycle_input_bundle"]["decision_proof_ref"]
    assert first["build_summary"]["allow_decision_proof_ref"] == first["next_cycle_decision"]["allow_decision_proof_ref"]
    assert first["next_cycle_decision"]["next_cycle_inputs_ref"] == first["next_step_recommendation"]["next_cycle_inputs_ref"]
    assert first["next_cycle_input_bundle"]["bundle_id"] in first["next_step_recommendation"]["next_cycle_inputs_ref"]
    assert "required_reviews" in first["next_cycle_input_bundle"]
    assert first["next_cycle_input_bundle"]["continuation_depth"] == 1
    assert first["next_cycle_input_bundle"]["source_cycle_runner_result_ref"].startswith("cycle_runner_result:CRR-")
    assert first["batch_handoff_bundle"]["source_delivery_report_ref"] == f"batch_delivery_report:{first['batch_delivery_report']['report_id']}"
    assert first["batch_handoff_bundle"]["autonomy_decision_ref"] == first["build_summary"]["autonomy_decision_ref"]
    assert first["batch_handoff_bundle"]["latest_exception_class"] == first["exception_classification_record"]["exception_class"]
    assert first["batch_handoff_bundle"]["latest_exception_resolution_action"] == first["exception_resolution_record"]["recommended_action"]
    assert first["batch_handoff_bundle"]["decision_proof_ref"] == first["build_summary"]["decision_proof_ref"]
    assert first["batch_handoff_bundle"]["allow_decision_proof_ref"] == first["build_summary"]["allow_decision_proof_ref"]
    assert first["build_summary"]["capability_readiness_ref"].startswith("capability_readiness_record:CRD-")
    assert first["build_summary"]["capability_readiness_state"] in {"unsafe", "constrained", "supervised", "autonomous"}
    assert first["batch_handoff_bundle"]["capability_readiness_ref"] == first["build_summary"]["capability_readiness_ref"]
    assert first["batch_handoff_bundle"]["capability_readiness_state"] == first["build_summary"]["capability_readiness_state"]
    assert first["build_summary"]["failure_taxonomy_ref"].startswith("failure_taxonomy_record:FTX-")
    assert first["build_summary"]["rollback_plan_ref"].startswith("rollback_plan_record:RBP-")
    assert first["build_summary"]["promotion_consistency_ref"].startswith("promotion_consistency_record:PCR-")
    assert first["build_summary"]["system_budget_status_ref"].startswith("system_budget_status:SBS-")
    assert first["build_summary"]["canary_rollout_ref"].startswith("canary_rollout_record:CNR-")
    assert len(first["build_summary"]["continuous_eval_run_refs"]) == 4
    assert first["build_summary"]["trust_posture_snapshot_ref"].startswith("trust_posture_snapshot:TPS-")
    assert first["batch_handoff_bundle"]["failure_taxonomy_ref"] == first["build_summary"]["failure_taxonomy_ref"]
    assert first["batch_handoff_bundle"]["rollback_plan_ref"] == first["build_summary"]["rollback_plan_ref"]
    assert first["batch_handoff_bundle"]["promotion_consistency_ref"] == first["build_summary"]["promotion_consistency_ref"]
    assert first["batch_handoff_bundle"]["system_budget_status_ref"] == first["build_summary"]["system_budget_status_ref"]
    assert first["batch_handoff_bundle"]["canary_rollout_ref"] == first["build_summary"]["canary_rollout_ref"]
    assert first["batch_handoff_bundle"]["continuous_eval_run_refs"] == first["build_summary"]["continuous_eval_run_refs"]
    assert first["batch_handoff_bundle"]["trust_posture_snapshot_ref"] == first["build_summary"]["trust_posture_snapshot_ref"]
    assert first["promotion_consistency_record"]["promotion_state"] in {"deny", "hold", "allow"}


def test_prior_handoff_auto_ingested_and_required_validations_propagated(tmp_path: Path) -> None:
    handoff_root = tmp_path / "handoffs"
    handoff_root.mkdir(parents=True, exist_ok=True)
    prior = copy.deepcopy(load_example("batch_handoff_bundle"))
    prior["bundle_id"] = "BHB-AAAAAAAAAAAA"
    prior["created_at"] = "2026-04-03T23:58:00Z"
    prior["required_validations_next"] = ["validation:pytest tests/test_contract_enforcement.py"]
    prior["recommended_next_batch"] = "BATCH-J"
    (handoff_root / "prior.json").write_text(json.dumps(prior), encoding="utf-8")

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={**_integration_inputs(), "handoff_bundle_root": str(handoff_root)},
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    assert result["prior_batch_handoff_bundle"]["bundle_id"] == "BHB-AAAAAAAAAAAA"
    assert any(
        item == "required_validation:validation:pytest tests/test_contract_enforcement.py"
        for item in result["next_step_recommendation"]["next_step"]["watchouts"]
    )
    assert any(
        item == "required_validation:validation:pytest tests/test_contract_enforcement.py"
        for item in result["build_summary"]["watch_next"]
    )


def test_required_prior_handoff_fails_closed_on_malformed_bundle(tmp_path: Path) -> None:
    handoff_root = tmp_path / "handoffs"
    handoff_root.mkdir(parents=True, exist_ok=True)
    bad = {"bundle_id": "BHB-AAAAAAAAAAAA", "schema_version": "1.0.0"}
    (handoff_root / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    try:
        run_system_cycle(
            roadmap_artifact=_roadmap(),
            selection_signals=_selection_signals(),
            authorization_signals=_authorization_signals(),
            integration_inputs={**_integration_inputs(), "handoff_bundle_root": str(handoff_root), "require_prior_handoff": True},
            pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
            pqx_runs_root=Path("tests/fixtures/pqx_runs"),
            execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
            created_at="2026-04-03T23:59:00Z",
            pqx_execute_fn=_pqx_stub,
        )
    except sco.SystemCycleOperatorError as exc:
        assert "required prior batch_handoff_bundle unavailable" in str(exc)
    else:
        raise AssertionError("expected fail-closed error for malformed required prior handoff bundle")


def test_critical_prior_handoff_risk_prevents_unsafe_continuation(tmp_path: Path) -> None:
    handoff_root = tmp_path / "handoffs"
    handoff_root.mkdir(parents=True, exist_ok=True)
    prior = copy.deepcopy(load_example("batch_handoff_bundle"))
    prior["bundle_id"] = "BHB-BBBBBBBBBBBB"
    prior["created_at"] = "2026-04-03T23:59:30Z"
    prior["must_carry_forward_risks"] = ["critical_risk:AUTH_HUMAN_SIGNOFF_MISSING"]
    (handoff_root / "critical.json").write_text(json.dumps(prior), encoding="utf-8")

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={**_integration_inputs(), "handoff_bundle_root": str(handoff_root)},
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    assert result["next_cycle_decision"]["decision"] == "stop"
    assert result["roadmap_multi_batch_run_result"]["stop_reason"] in {
        "authorization_block",
        "program_priority_violation",
    }


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
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
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
    assert recommendation["artifact_refs"]["next_cycle_decision"].startswith("next_cycle_decision:NCD-")
    assert recommendation["artifact_refs"]["next_cycle_input_bundle"].startswith("next_cycle_input_bundle:NCB-")
    assert any(item.startswith("adaptive_execution_observability:AEO-") for item in recommendation["artifact_refs"]["related_artifacts"])
    assert any(item.startswith("adaptive_execution_trend_report:AET-") for item in recommendation["artifact_refs"]["related_artifacts"])
    assert any(item.startswith("adaptive_execution_policy_review:AEPR-") for item in recommendation["artifact_refs"]["related_artifacts"])
    assert summary["artifact_index"]["upstream_refs"]
    assert summary["artifact_index"]["downstream_refs"]


def test_cycle_applies_roadmap_adjustments_and_exposes_artifacts() -> None:
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={**_integration_inputs(), "eval_coverage_signal": {"coverage_gap_detected": True}},
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    assert result["roadmap_adjustments"]
    assert result["next_step_recommendation"]["next_batch_id"] == "BATCH-R"
    assert result["next_cycle_input_bundle"]["recommended_start_batch"] == "BATCH-R"
    assert result["batch_handoff_bundle"]["recommended_next_batch"] == "BATCH-R"
    assert any(ref.startswith("roadmap_adjustment_record:RADJ-") for ref in result["build_summary"]["source_refs"])
    assert any(ref.startswith("roadmap_adjustment_record:RADJ-") for ref in result["batch_handoff_bundle"]["must_carry_forward_artifacts"])
    summary = result["build_summary"]
    assert summary["artifact_index"]["next_cycle_decision"].startswith("next_cycle_decision:NCD-")
    assert summary["artifact_index"]["next_cycle_input_bundle"].startswith("next_cycle_input_bundle:NCB-")
    assert any(item.startswith("adaptive_execution_observability:AEO-") for item in summary["artifact_index"]["related_artifacts"])
    assert any(item.startswith("adaptive_execution_trend_report:AET-") for item in summary["artifact_index"]["related_artifacts"])
    assert any(item.startswith("adaptive_execution_policy_review:AEPR-") for item in summary["artifact_index"]["related_artifacts"])


def test_candidate_ranking_is_deterministic_and_sorted() -> None:
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
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
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
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
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
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
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )

    assert result["core_system_integration_validation"]["authority_boundary_status"] == "violated"
    assert result["next_step_recommendation"]["risk_summary"]["level"] == "high"
    assert "control_authority_review" in result["next_step_recommendation"]["required_reviews"]
    assert any(
        "control_authority_review" in item for item in result["next_step_recommendation"]["next_step"]["watchouts"]
    )


def test_remediation_steps_are_deterministic_and_stop_reason_mapped() -> None:
    kwargs = {
        "stop_reason": "missing_required_signal",
        "root_cause_chain": [{"step": "bounded_execution", "reason": "missing_required_signal"}],
        "blocking_conditions": ["PROP_REVIEW_EVAL_NOT_INGESTED"],
        "required_reviews": ["cross_layer_propagation_review"],
        "required_artifacts": ["roadmap_multi_batch_run_result:RMB-EXAMPLE0001"],
        "review_control_signal": {"signal_id": "rcs-1"},
        "trace_id": "trace-batch-u-test",
    }
    first = sco._build_remediation_steps(**kwargs)
    second = sco._build_remediation_steps(**kwargs)
    assert first == second
    actions = [item["action"] for item in first]
    assert actions[0] == "confirm_root_cause_chain"
    assert any(action.startswith("run_required_review:cross_layer_propagation_review") for action in actions)
    assert any(action.startswith("fix_missing_artifact_or_signal:") for action in actions)
    assert actions[-1] == "rerun_bounded_batch_cycle"


def test_repeated_failure_pattern_reuses_known_playbook_step() -> None:
    steps = sco._build_remediation_steps(
        stop_reason="repeated_failure_pattern",
        root_cause_chain=[{"step": "bounded_execution", "reason": "repeated_failure_pattern"}],
        blocking_conditions=[],
        required_reviews=[],
        required_artifacts=["roadmap_multi_batch_run_result:RMB-EXAMPLE0001"],
        review_control_signal={"signal_id": "rcs-1"},
        trace_id="trace-batch-u-test",
    )
    assert any(step["action"] == "reuse_known_repeated_failure_playbook" for step in steps)


def test_operator_artifacts_surface_program_alignment_and_program_caused_stop_state() -> None:
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals={**_selection_signals(), "disallowed_targets": ["BATCH-I"]},
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    summary = result["build_summary"]
    recommendation = result["next_step_recommendation"]
    assert any(item.startswith("program_alignment_status=") for item in summary["what_changed"])
    assert any(item.startswith("program_caused_stop=") for item in summary["watch_next"])
    assert any(item.startswith("program_alignment_status=") for item in recommendation["why"])
    assert any(item.startswith("program_caused_stop=") for item in recommendation["next_step"]["watchouts"])


def test_next_cycle_decision_stops_on_program_misalignment() -> None:
    bundle = {
        "bundle_id": "NCB-1234567890AB",
        "unresolved_blockers": [],
    }
    decision = sco.decide_next_cycle(
        current_cycle_id="RMB-EXAMPLE",
        stop_reason="program_alignment_invalid",
        program_constraint_signal={"enforcement_mode": "block"},
        program_feedback_record={},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
        batch_continuation_records=[],
        eval_control_state={"decision": "allow", "health": "healthy"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        drift_signal={"drift_level": "low"},
        operator_summary={"program_alignment_status": "misaligned", "program_stop_cause": "program_alignment_invalid"},
        required_artifacts_for_next_cycle=["roadmap_multi_batch_run_result:RMB-EXAMPLE"],
        next_cycle_input_bundle=bundle,
        allow_decision_proof_ref="allow_decision_proof:ADP-1234567890AB",
        created_at="2026-04-03T23:59:00Z",
        trace_id="trace-batch-u-test",
    )
    assert decision["decision"] == "stop"
    assert "program_misalignment" in decision["decision_reason_codes"]


def test_next_cycle_decision_escalates_on_high_drift_and_is_deterministic() -> None:
    kwargs = dict(
        current_cycle_id="RMB-EXAMPLE",
        stop_reason="max_batches_reached",
        program_constraint_signal={"enforcement_mode": "block"},
        program_feedback_record={},
        roadmap_state={"current_batch_id": "BATCH-I", "next_candidate_batch_id": "BATCH-J"},
        batch_continuation_records=[],
        eval_control_state={"decision": "allow", "health": "healthy"},
        failure_pattern_record={"repeated_failure_count": 0, "stop_threshold": 2},
        drift_signal={"drift_level": "high"},
        operator_summary={"program_alignment_status": "aligned", "program_stop_cause": "none"},
        required_artifacts_for_next_cycle=["roadmap_multi_batch_run_result:RMB-EXAMPLE"],
        next_cycle_input_bundle={"bundle_id": "NCB-1234567890AB", "unresolved_blockers": []},
        allow_decision_proof_ref="allow_decision_proof:ADP-1234567890AB",
        created_at="2026-04-03T23:59:00Z",
        trace_id="trace-batch-u-test",
    )
    first = sco.decide_next_cycle(**kwargs)
    second = sco.decide_next_cycle(**kwargs)
    assert first == second
    assert first["decision"] == "escalate"
    assert "program_drift_high" in first["decision_reason_codes"]


def test_invalid_execution_policy_fails_closed() -> None:
    try:
        run_system_cycle(
            roadmap_artifact=_roadmap(),
            selection_signals=_selection_signals(),
            authorization_signals=_authorization_signals(),
            integration_inputs=_integration_inputs(),
            pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
            pqx_runs_root=Path("tests/fixtures/pqx_runs"),
            execution_policy={"max_batches_per_run": 1, "max_continuation_depth": -1},
            created_at="2026-04-03T23:59:00Z",
            pqx_execute_fn=_pqx_stub,
        )
        assert False, "expected SystemCycleOperatorError"
    except sco.SystemCycleOperatorError as exc:
        assert "execution_policy" in str(exc)


def test_malformed_autonomy_policy_fails_closed_and_propagates_blockers() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["autonomy_policy"] = {"autonomy_policy_id": "AP-INVALID"}

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["autonomy_decision_record"]["decision"] == "stop"
    assert "malformed_autonomy_policy" in result["autonomy_decision_record"]["reason_codes"]
    assert result["next_cycle_input_bundle"]["autonomy_blockers"]
    assert any(item.startswith("autonomy_blocker:autonomy:") for item in result["batch_handoff_bundle"]["autonomy_blockers"])


def test_capability_readiness_high_failure_rate_marks_unsafe() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["eval_result"] = {"run_id": "eval-1", "result_status": "fail"}
    integration_inputs["capability_readiness_inputs"] = {
        "eval_results": [{"result_status": "fail"}, {"result_status": "fail"}],
        "batch_delivery_reports": [{"status": "blocked"}],
        "autonomy_decisions": [{"decision": "stop"}],
        "exception_routing_outputs": [{"action_type": "escalate"}],
        "drift_signals": [{"drift_level": "high"}],
        "replay_metrics": [{"status": "mismatch"}],
        "unresolved_risks": ["critical_risk:AUTH_REVIEW_PENDING"],
    }
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["capability_readiness_record"]["readiness_state"] == "unsafe"
    assert result["build_summary"]["autonomy_decision"] == "stop"


def test_capability_readiness_high_drift_marks_constrained() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["capability_readiness_inputs"] = {
        "batch_delivery_reports": [{"status": "completed_with_risk"}],
        "eval_results": [{"result_status": "pass"}, {"result_status": "pass"}, {"result_status": "pass"}],
        "autonomy_decisions": [{"decision": "continue"}],
        "exception_routing_outputs": [{"action_type": "queue_review"}],
        "drift_signals": [{"drift_level": "high"}, {"drift_level": "medium"}],
        "replay_metrics": [{"status": "match"}, {"status": "match"}],
    }
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["capability_readiness_record"]["readiness_state"] in {"constrained", "unsafe"}


def test_capability_readiness_stable_runs_mark_autonomous() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["capability_readiness_inputs"] = {
        "batch_delivery_reports": [{"status": "completed"}, {"status": "completed"}, {"status": "completed"}],
        "eval_results": [{"result_status": "pass"}, {"result_status": "pass"}, {"result_status": "pass"}],
        "autonomy_decisions": [{"decision": "continue"}, {"decision": "continue"}],
        "exception_routing_outputs": [{"action_type": "queue_review"}],
        "drift_signals": [{"drift_level": "low"}, {"drift_level": "low"}],
        "replay_metrics": [{"status": "match"}, {"status": "match"}, {"status": "match"}],
        "recent_batches_considered": 3,
    }
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["capability_readiness_record"]["readiness_state"] == "autonomous"


def test_capability_readiness_replay_mismatch_degrades_readiness() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["capability_readiness_inputs"] = {
        "batch_delivery_reports": [{"status": "completed"}],
        "eval_results": [{"result_status": "pass"}],
        "autonomy_decisions": [{"decision": "continue"}],
        "exception_routing_outputs": [{"action_type": "queue_review"}],
        "drift_signals": [{"drift_level": "low"}],
        "replay_metrics": [{"status": "mismatch"}],
    }
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["capability_readiness_record"]["readiness_state"] == "unsafe"
    assert "replay_consistency_low" in result["capability_readiness_record"]["reason_codes"]


def test_capability_readiness_missing_inputs_fail_closed() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["capability_readiness_inputs"] = {}
    integration_inputs["eval_result"] = {}
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["capability_readiness_record"]["readiness_state"] in {"unsafe", "constrained"}
    assert result["capability_readiness_record"]["readiness_state"] != "autonomous"


def test_governed_system_roadmap_selection_wires_to_single_cycle_execution() -> None:
    governed = load_active_roadmap(Path("contracts/examples/system_roadmap.json"))
    selected = select_next_batch(
        governed,
        program_aligned_batch_ids={"BATCH-CL-02", "BATCH-CL-03"},
        continuation_allowed=True,
    )
    assert selected == "BATCH-CL-02"

    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 0},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["roadmap_multi_batch_run_result"]["batches_executed_count"] == 1


def test_failure_taxonomy_recurrence_and_correction_pattern_threshold() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["promotion_consistency_evidence"] = [
        {"determinism_status": "deterministic", "replay_status": "match", "eval_status": "pass", "drift_detected": False},
        {"determinism_status": "deterministic", "replay_status": "match", "eval_status": "pass", "drift_detected": False},
    ]
    seed_result = run_system_cycle(
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
    integration_inputs["prior_failure_taxonomy_records"] = [seed_result["failure_taxonomy_record"]]
    integration_inputs["correction_recurrence_threshold"] = 2
    result = run_system_cycle(
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
    assert result["failure_taxonomy_record"]["recurrence_count"] >= 2
    assert result["correction_pattern_record"] is not None
    assert result["correction_pattern_record"]["recurrence_threshold_met"] is True


def test_promotion_consistency_denies_unstable_or_non_reversible_paths() -> None:
    integration_inputs = _integration_inputs()
    integration_inputs["promotion_consistency_evidence"] = [
        {"determinism_status": "nondeterministic", "replay_status": "mismatch", "eval_status": "fail", "drift_detected": True},
        {"determinism_status": "deterministic", "replay_status": "match", "eval_status": "pass", "drift_detected": False},
    ]
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals={**_selection_signals(), "disallowed_targets": ["BATCH-I"]},
        authorization_signals=_authorization_signals(),
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-04T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["promotion_consistency_record"]["promotion_state"] in {"deny", "hold"}
    assert result["next_cycle_decision"]["decision"] != "run_next_cycle"


def test_budget_breach_triggers_freeze_path() -> None:
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={
            **_integration_inputs(),
            "budget_inputs": {
                "threshold_values": {"cost": 10.0, "latency_ms": 100.0, "error_rate": 0.01},
                "current_values": {"cost": 20.0, "latency_ms": 200.0, "error_rate": 0.2},
                "breach_action": "freeze",
            },
        },
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["system_budget_status"]["budget_exhausted"] is True
    assert "budget_exhausted" in result["autonomy_decision_record"]["reason_codes"]


def test_canary_block_prevents_unsafe_promotion() -> None:
    result = run_system_cycle(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs={
            **_integration_inputs(),
            "continuous_eval_inputs": {
                "canary_eval_run": {
                    "eval_case_ids": ["EC-FAIL"],
                    "pass_rate": 0.2,
                    "fail_rate": 0.7,
                    "indeterminate_rate": 0.1,
                    "drift_delta": 0.5,
                }
            },
        },
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    assert result["canary_rollout_record"]["promotion_decision"] in {"block", "rollback"}


def test_observability_artifacts_are_deterministic() -> None:
    kwargs = dict(
        roadmap_artifact=_roadmap(),
        selection_signals=_selection_signals(),
        authorization_signals=_authorization_signals(),
        integration_inputs=_integration_inputs(),
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-03T23:59:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    first = run_system_cycle(**kwargs)
    second = run_system_cycle(**kwargs)
    assert first["trust_posture_snapshot"] == second["trust_posture_snapshot"]
    assert first["artifact_family_health_report"] == second["artifact_family_health_report"]
    assert first["evidence_gap_hotspot_report"] == second["evidence_gap_hotspot_report"]
    assert first["override_hotspot_report"] == second["override_hotspot_report"]
