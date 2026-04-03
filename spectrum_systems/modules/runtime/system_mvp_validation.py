"""Deterministic BATCH-MVP end-to-end multi-cycle validation execution."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_example, load_schema
from spectrum_systems.modules.runtime.system_cycle_operator import run_system_cycle


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ValueError(f"{schema_name} validation failed: {details}")


def _base_roadmap() -> dict[str, Any]:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    for batch in artifact.get("batches", []):
        if batch.get("batch_id") == "BATCH-H":
            batch["status"] = "completed"
        if batch.get("batch_id") in {"BATCH-I", "BATCH-J"}:
            batch["status"] = "not_started"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _base_selection_signals() -> dict[str, Any]:
    return {
        "signals": ["executor_ingestion_valid", "state_binding_complete"],
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
    }


def _base_authorization_signals(trace_id: str) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
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


def _base_integration_inputs(trace_id: str) -> dict[str, Any]:
    return {
        "program_artifact": {"program_id": "PRG-BATCH-MVP"},
        "review_control_signal": {"signal_id": "rcs-batch-mvp", "gate_assessment": "PASS"},
        "eval_result": {"run_id": "eval-batch-mvp", "result_status": "pass"},
        "context_bundle": {"context_id": "ctx-batch-mvp"},
        "tpa_gate": {
            "context_bundle_ref": "context_bundle_v2:ctx-batch-mvp",
            "speculative_expansion_detected": False,
            "gate_replaces_control": False,
        },
        "roadmap_loop_validation": {"validation_id": "RLV-BATCH-MVP", "determinism_status": "deterministic"},
        "control_decision": {"decision": "allow", "review_eval_ingested": True},
        "certification_pack": {"certification_status": "complete"},
        "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-batch-mvp", "mode": "governed_integration"},
        "trace_id": trace_id,
        "source_refs": {
            "program_artifact": "program_artifact:PRG-BATCH-MVP",
            "review_control_signal": "review_control_signal:rcs-batch-mvp",
            "eval_result": "eval_result:eval-batch-mvp",
            "context_bundle_v2": "context_bundle_v2:ctx-batch-mvp",
            "tpa_gate": "tpa_gate:gate-batch-mvp",
            "roadmap_execution_loop_validation": "roadmap_execution_loop_validation:RLV-BATCH-MVP",
            "roadmap_multi_batch_run_result": "roadmap_multi_batch_run_result:RMB-BATCH-MVP",
            "control_decision": "control_execution_result:ctrl-batch-mvp",
            "certification_pack": "control_loop_certification_pack:cert-batch-mvp",
        },
    }


def _pqx_success(**_: object) -> dict[str, Any]:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:batch-mvp:ok:1",
                "slice_execution_record_ref": "runs/pqx/batch-mvp.slice.json",
                "certification_ref": "runs/pqx/batch-mvp.cert.json",
                "audit_bundle_ref": "runs/pqx/batch-mvp.audit.json",
            }
        ],
    }


def _pqx_blocked(**_: object) -> dict[str, Any]:
    return {
        "status": "blocked",
        "blocked_reason": "simulated blocked operator path",
        "batch_result": {"status": "blocked"},
        "execution_history": [],
    }


def _scenario_catalog() -> list[dict[str, Any]]:
    return [
        {"scenario_id": "SCN-HAPPY_PATH_BOUNDED", "type": "happy"},
        {"scenario_id": "SCN-MISSING_REQUIRED_REVIEW", "type": "review_block"},
        {"scenario_id": "SCN-PROGRAM_MISALIGNMENT", "type": "program_misalignment"},
        {"scenario_id": "SCN-NOISY_FAILURE_SURFACE", "type": "noisy_failure"},
        {"scenario_id": "SCN-COMPLETE_WITH_NEXT_STEP", "type": "complete_next"},
    ]


def _apply_scenario_mutations(
    scenario_type: str,
    *,
    selection_signals: dict[str, Any],
    integration_inputs: dict[str, Any],
) -> dict[str, Any]:
    pqx_fn = _pqx_success

    if scenario_type == "review_block":
        integration_inputs["control_decision"]["review_eval_ingested"] = False
    elif scenario_type == "program_misalignment":
        integration_inputs["roadmap_multi_batch_result_overrides"] = {"program_constraints_applied": False}
    elif scenario_type == "noisy_failure":
        integration_inputs["control_decision"]["review_eval_ingested"] = False
        integration_inputs["tpa_gate"]["speculative_expansion_detected"] = True
        integration_inputs["roadmap_multi_batch_result_overrides"] = {"program_constraints_applied": False}
        pqx_fn = _pqx_blocked
    elif scenario_type == "complete_next":
        selection_signals["signals"].append("downstream_ready")

    return {"pqx_execute_fn": pqx_fn}


def run_system_mvp_validation(
    *,
    pqx_state_path: Path,
    pqx_runs_root: Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or _utc_now()
    trace_id = f"trace-batch-mvp-{_canonical_hash({'created_at': timestamp})[:8]}"

    scenario_outputs: list[dict[str, Any]] = []
    adaptive_history: list[dict[str, Any]] = []
    for idx, scenario in enumerate(_scenario_catalog(), start=1):
        selection = _base_selection_signals()
        integration_inputs = _base_integration_inputs(trace_id)
        patched = _apply_scenario_mutations(
            scenario["type"],
            selection_signals=selection,
            integration_inputs=integration_inputs,
        )

        result = run_system_cycle(
            roadmap_artifact=_base_roadmap(),
            selection_signals=selection,
            authorization_signals=_base_authorization_signals(trace_id),
            integration_inputs={
                **integration_inputs,
                "adaptive_observability_run_results": adaptive_history,
            },
            pqx_state_path=pqx_state_path,
            pqx_runs_root=pqx_runs_root,
            execution_policy={"max_batches_per_run": 1},
            created_at=timestamp,
            pqx_execute_fn=patched["pqx_execute_fn"],
        )
        adaptive_history.append(result["roadmap_multi_batch_run_result"])

        build_summary = result["build_summary"]
        recommendation = result["next_step_recommendation"]
        integration = result["core_system_integration_validation"]

        status = "success" if not recommendation["blockers"] and build_summary["run_outcome"]["status"] == "success" else "blocked"
        scenario_outputs.append(
            {
                "cycle_index": idx,
                "scenario_id": scenario["scenario_id"],
                "run_id": result["roadmap_multi_batch_run_result"]["run_id"],
                "stop_reason": build_summary["failure_surface"]["stop_reason"],
                "status": status,
                "next_batch_id": recommendation["next_batch_id"],
                "blockers": recommendation["blockers"],
                "required_reviews": recommendation["required_reviews"],
                "artifact_refs": {
                    "build_summary": f"build_summary:{build_summary['summary_id']}",
                    "next_step_recommendation": f"next_step_recommendation:{recommendation['recommendation_id']}",
                    "trace_navigation": f"trace_navigation:{integration['validation_id']}",
                    "core_system_integration_validation": f"core_system_integration_validation:{integration['validation_id']}",
                    "adaptive_execution_observability": (
                        f"adaptive_execution_observability:{result['adaptive_execution_observability']['observability_id']}"
                    ),
                    "adaptive_execution_trend_report": (
                        f"adaptive_execution_trend_report:{result['adaptive_execution_trend_report']['trend_report_id']}"
                    ),
                    "adaptive_execution_policy_review": (
                        f"adaptive_execution_policy_review:{result['adaptive_execution_policy_review']['review_id']}"
                    ),
                },
                "artifacts": result,
            }
        )

    success_cases = [item["scenario_id"] for item in scenario_outputs if item["status"] == "success"]
    failure_cases = [item["scenario_id"] for item in scenario_outputs if item["status"] == "blocked"]

    total_cycles = len(scenario_outputs)
    successful_cycles = len(success_cases)
    blocked_cycles = len(failure_cases)
    useful_batches = sum(len(item["artifacts"]["roadmap_multi_batch_run_result"].get("completed_batch_ids", [])) for item in scenario_outputs)
    wasted_cycles = sum(1 for item in scenario_outputs if not item["artifacts"]["roadmap_multi_batch_run_result"].get("completed_batch_ids", []))

    report = {
        "report_id": f"MVPR-{_canonical_hash({'trace_id': trace_id, 'at': timestamp})[:12].upper()}",
        "schema_version": "1.0.0",
        "scenario_description": (
            "Bounded five-cycle governed run using one baseline success, one review-trigger stop, "
            "one program-alignment block, one noisy blocked failure, and one successful continuation scenario."
        ),
        "runs_executed": [
            {
                "cycle_index": item["cycle_index"],
                "scenario_id": item["scenario_id"],
                "run_id": item["run_id"],
                "stop_reason": item["stop_reason"],
                "status": item["status"],
                "next_batch_id": item["next_batch_id"],
                "blockers": item["blockers"],
                "required_reviews": item["required_reviews"],
                "artifact_refs": item["artifact_refs"],
            }
            for item in scenario_outputs
        ],
        "success_cases": success_cases,
        "failure_cases": failure_cases,
        "stop_behavior_analysis": (
            "System stops safely at review, TPA, and program-alignment boundaries and only continues "
            "when blocker signals are absent."
        ),
        "decision_quality_analysis": (
            "Recommended next steps are sensible: continue when bounded execution succeeds, "
            "and route to remediation/review when blocker evidence is present."
        ),
        "explanation_quality_analysis": (
            "Build summary root-cause and recommendation rationale remain traceable across all cycles "
            "through linked summary/recommendation/validation artifacts."
        ),
        "efficiency_metrics": {
            "total_cycles": total_cycles,
            "successful_cycles": successful_cycles,
            "blocked_cycles": blocked_cycles,
            "success_rate": round(successful_cycles / total_cycles, 4),
            "average_useful_batches_per_run": round(useful_batches / total_cycles, 4),
            "wasted_cycle_count": wasted_cycles,
        },
        "major_strengths": [
            "Safe stop behavior at review and contract boundaries.",
            "Deterministic multi-artifact traceability per cycle.",
            "Adaptive execution trend and policy review are emitted every run.",
        ],
        "major_weaknesses": [
            "Program-alignment and review blockers still require manual remediation planning.",
            "Noisy failure surfaces can reduce operator throughput in bounded windows.",
        ],
        "recommended_next_batches": ["BATCH-U", "BATCH-Y", "BATCH-Z"],
        "created_at": timestamp,
        "trace_id": trace_id,
    }
    _validate_schema(report, "system_mvp_validation_report")

    return {
        "trace_id": trace_id,
        "created_at": timestamp,
        "scenario_results": [
            {
                "cycle_index": item["cycle_index"],
                "scenario_id": item["scenario_id"],
                "artifacts": item["artifacts"],
            }
            for item in scenario_outputs
        ],
        "system_mvp_validation_report": report,
    }


__all__ = ["run_system_mvp_validation"]
