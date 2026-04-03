"""Deterministic BATCH-Y operator shakeout execution and friction/backlog artifact generation."""

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
        "control_loop": {
            "eval_present": True,
            "trace_present": True,
            "schema_valid": True,
        },
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
        "program_artifact": {"program_id": "PRG-BATCH-Y"},
        "review_control_signal": {"signal_id": "rcs-batch-y", "gate_assessment": "PASS"},
        "eval_result": {"run_id": "eval-batch-y", "result_status": "pass"},
        "context_bundle": {"context_id": "ctx-batch-y"},
        "tpa_gate": {
            "context_bundle_ref": "context_bundle_v2:ctx-batch-y",
            "speculative_expansion_detected": False,
            "gate_replaces_control": False,
        },
        "roadmap_loop_validation": {
            "validation_id": "RLV-BATCH-Y",
            "determinism_status": "deterministic",
        },
        "control_decision": {"decision": "allow", "review_eval_ingested": True},
        "certification_pack": {"certification_status": "complete"},
        "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-batch-y", "mode": "governed_integration"},
        "trace_id": trace_id,
        "source_refs": {
            "program_artifact": "program_artifact:PRG-BATCH-Y",
            "review_control_signal": "review_control_signal:rcs-batch-y",
            "eval_result": "eval_result:eval-batch-y",
            "context_bundle_v2": "context_bundle_v2:ctx-batch-y",
            "tpa_gate": "tpa_gate:gate-batch-y",
            "roadmap_execution_loop_validation": "roadmap_execution_loop_validation:RLV-BATCH-Y",
            "roadmap_multi_batch_run_result": "roadmap_multi_batch_run_result:RMB-BATCH-Y",
            "control_decision": "control_execution_result:ctrl-batch-y",
            "certification_pack": "control_loop_certification_pack:cert-batch-y",
        },
    }


def _pqx_success(**_: object) -> dict[str, Any]:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:batch-y:ok:1",
                "slice_execution_record_ref": "runs/pqx/batch-y.slice.json",
                "certification_ref": "runs/pqx/batch-y.cert.json",
                "audit_bundle_ref": "runs/pqx/batch-y.audit.json",
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
        {"scenario_id": "SCN-HAPPY_PATH_BOUNDED", "type": "happy", "execution_policy": {"max_batches_per_run": 1}},
        {
            "scenario_id": "SCN-MISSING_REQUIRED_REVIEW",
            "type": "review_block",
            "execution_policy": {"max_batches_per_run": 1},
        },
        {
            "scenario_id": "SCN-PROGRAM_MISALIGNMENT",
            "type": "program_misalignment",
            "execution_policy": {"max_batches_per_run": 1},
        },
        {
            "scenario_id": "SCN-REPEATED_RISK_TPA_GATE",
            "type": "tpa_repeated_risk",
            "execution_policy": {"max_batches_per_run": 1},
        },
        {"scenario_id": "SCN-COMPLETE_WITH_NEXT_STEP", "type": "complete_next", "execution_policy": {"max_batches_per_run": 1}},
        {
            "scenario_id": "SCN-NOISY_FAILURE_SURFACE",
            "type": "noisy_failure",
            "execution_policy": {"max_batches_per_run": 1},
        },
        {
            "scenario_id": "SCN-WEAK_RECOMMENDATION_QUALITY",
            "type": "weak_recommendation",
            "execution_policy": {"max_batches_per_run": 1},
        },
    ]


def _apply_scenario_mutations(
    scenario_type: str,
    *,
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    integration_inputs: dict[str, Any],
) -> dict[str, Any]:
    pqx_fn = _pqx_success

    if scenario_type == "review_block":
        integration_inputs["control_decision"]["review_eval_ingested"] = False
    elif scenario_type == "program_misalignment":
        integration_inputs["roadmap_multi_batch_result_overrides"] = {"program_constraints_applied": False}
    elif scenario_type == "tpa_repeated_risk":
        integration_inputs["tpa_gate"]["speculative_expansion_detected"] = True
    elif scenario_type == "noisy_failure":
        integration_inputs["control_decision"]["review_eval_ingested"] = False
        integration_inputs["tpa_gate"]["speculative_expansion_detected"] = True
        integration_inputs["roadmap_multi_batch_result_overrides"] = {"program_constraints_applied": False}
        pqx_fn = _pqx_blocked
    elif scenario_type == "weak_recommendation":
        selection_signals["signals"] = ["executor_ingestion_valid"]
        integration_inputs["source_refs"].pop("certification_pack", None)

    return {"pqx_execute_fn": pqx_fn}


def _classify_friction(result: dict[str, Any]) -> tuple[str, str, str]:
    summary = result["build_summary"]
    recommendation = result["next_step_recommendation"]
    integration = result["core_system_integration_validation"]
    stop_reason = summary["failure_surface"]["stop_reason"]
    blockers = recommendation["blockers"]

    if stop_reason == "execution_blocked" and not blockers:
        return ("insufficient root-cause visibility", "high", "runtime")
    if len(summary["what_failed"]) >= 3:
        return ("noisy summary artifact", "high", "runtime")
    if any(item.startswith("PROP_REVIEW_EVAL") for item in blockers):
        return ("review/context surfacing quality", "high", "documentation")
    if any(item.startswith("PROP_") for item in blockers):
        return ("weak failure explanation", "medium", "runtime")
    if stop_reason == "missing_required_signal":
        return ("operator command ergonomics", "medium", "operator_cli")
    if integration["replay_status"] == "not_replayable":
        return ("trace/replay discoverability", "high", "documentation")
    if recommendation["next_batch_id"] is None:
        return ("weak prioritization", "medium", "runtime")
    return ("unclear next-step recommendation", "low", "documentation")


def _layer_for_friction(friction_type: str) -> str:
    mapping = {
        "review/context surfacing quality": "RVW/RPT",
        "weak failure explanation": "BATCH-Z",
        "trace/replay discoverability": "BATCH-U",
        "operator command ergonomics": "BATCH-U",
        "noisy summary artifact": "BATCH-U",
        "insufficient root-cause visibility": "PQX/RDX",
        "weak prioritization": "PQX/RDX",
        "unclear next-step recommendation": "BATCH-U",
        "too much manual artifact hunting": "BATCH-U",
    }
    return mapping.get(friction_type, "BATCH-U")


def run_operator_shakeout(
    *,
    pqx_state_path: Path,
    pqx_runs_root: Path,
    created_at: str | None = None,
    scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    timestamp = created_at or _utc_now()
    trace_id = f"trace-batch-y-{_canonical_hash({'created_at': timestamp})[:8]}"
    scenarios = _scenario_catalog()
    if scenario_ids is not None:
        allowed = set(scenario_ids)
        scenarios = [item for item in scenarios if item["scenario_id"] in allowed]
    if not scenarios:
        raise ValueError("at least one scenario must be selected")

    scenario_results: list[dict[str, Any]] = []
    friction_items: list[dict[str, Any]] = []

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        selection = _base_selection_signals()
        authorization = _base_authorization_signals(trace_id)
        integration = _base_integration_inputs(trace_id)
        patched = _apply_scenario_mutations(
            scenario["type"],
            selection_signals=selection,
            authorization_signals=authorization,
            integration_inputs=integration,
        )
        result = run_system_cycle(
            roadmap_artifact=_base_roadmap(),
            selection_signals=selection,
            authorization_signals=authorization,
            integration_inputs=integration,
            pqx_state_path=pqx_state_path,
            pqx_runs_root=pqx_runs_root,
            execution_policy=scenario["execution_policy"],
            created_at=timestamp,
            pqx_execute_fn=patched["pqx_execute_fn"],
        )

        friction_type, severity, suggested_fix_type = _classify_friction(result)
        summary = result["build_summary"]
        recommendation = result["next_step_recommendation"]
        integration_validation = result["core_system_integration_validation"]

        outcome_understandable = bool(summary["failure_surface"]["root_cause"])
        next_action_obvious = bool(summary["failure_surface"]["next_action"]) and (
            recommendation["next_batch_id"] is not None or bool(recommendation["blockers"])
        )
        manual_required = not (outcome_understandable and next_action_obvious)

        friction_items.append(
            {
                "scenario_id": sid,
                "friction_type": friction_type,
                "severity": severity,
                "artifact_refs": sorted(
                    {
                        f"build_summary:{summary['summary_id']}",
                        f"next_step_recommendation:{recommendation['recommendation_id']}",
                        f"core_system_integration_validation:{integration_validation['validation_id']}",
                    }
                ),
                "stop_reason": summary["failure_surface"]["stop_reason"],
                "blockers": recommendation["blockers"],
                "outcome_understandable": outcome_understandable,
                "next_action_obvious": next_action_obvious,
                "manual_interpretation_required": manual_required,
                "root_cause_hypothesis": (
                    f"Scenario {sid} indicates {friction_type} because stop_reason={summary['failure_surface']['stop_reason']} "
                    f"and blockers={','.join(recommendation['blockers']) or 'none'}."
                ),
                "suggested_fix_type": suggested_fix_type,
                "trace_id": integration_validation["trace_id"],
            }
        )

        scenario_results.append(
            {
                "scenario_id": sid,
                "stop_reason": summary["failure_surface"]["stop_reason"],
                "next_batch_id": recommendation["next_batch_id"],
                "blockers": recommendation["blockers"],
                "required_reviews": recommendation["required_reviews"],
                "artifacts": {
                    "roadmap_multi_batch_run_result": result["roadmap_multi_batch_run_result"],
                    "core_system_integration_validation": integration_validation,
                    "next_step_recommendation": recommendation,
                    "build_summary": summary,
                },
            }
        )

    report = {
        "report_id": f"OFR-{_canonical_hash({'trace_id': trace_id, 'at': timestamp})[:12].upper()}",
        "schema_version": "1.0.0",
        "scenarios_exercised": [item["scenario_id"] for item in scenario_results],
        "friction_items": friction_items,
        "created_at": timestamp,
        "trace_id": trace_id,
        "source_refs": sorted(
            {
                f"build_summary:{item['artifacts']['build_summary']['summary_id']}" for item in scenario_results
            }
            | {
                f"next_step_recommendation:{item['artifacts']['next_step_recommendation']['recommendation_id']}"
                for item in scenario_results
            }
        ),
    }
    _validate_schema(report, "operator_friction_report")

    grouped: dict[str, dict[str, Any]] = {}
    for item in friction_items:
        key = item["friction_type"]
        bucket = grouped.setdefault(
            key,
            {"friction_type": key, "scenario_refs": set(), "suggested_fix_type": item["suggested_fix_type"]},
        )
        bucket["scenario_refs"].add(item["scenario_id"])

    severity_weight = {"low": 1, "medium": 2, "high": 3}
    ranked_groups = sorted(
        grouped.values(),
        key=lambda entry: (
            -sum(severity_weight[next(x["severity"] for x in friction_items if x["scenario_id"] == sid)] for sid in entry["scenario_refs"]),
            entry["friction_type"],
        ),
    )

    prioritized_items = []
    for idx, bucket in enumerate(ranked_groups, start=1):
        refs = sorted(bucket["scenario_refs"])
        related = [item for item in friction_items if item["scenario_id"] in refs]
        trust_gain = "high" if any(item["severity"] == "high" for item in related) else "medium"
        usability_gain = "high" if len(refs) >= 2 else "medium"
        minutes_saved = 6 + (4 * len(refs))
        prioritized_items.append(
            {
                "rank": idx,
                "title": f"Reduce {bucket['friction_type']}",
                "why_it_matters": (
                    f"{len(refs)} exercised scenarios showed repeat friction in {bucket['friction_type']}, "
                    "forcing extra operator interpretation before safe continuation."
                ),
                "affected_layer": _layer_for_friction(bucket["friction_type"]),
                "expected_trust_gain": trust_gain,
                "expected_usability_gain": usability_gain,
                "operator_time_saved_minutes": minutes_saved,
                "suggested_batch_grouping": f"BATCH-Y{idx}",
                "source_friction_refs": refs,
            }
        )

    backlog = {
        "handoff_id": f"OBH-{_canonical_hash({'report_id': report['report_id']})[:12].upper()}",
        "schema_version": "1.0.0",
        "prioritized_items": prioritized_items,
        "grouped_candidates": [
            {
                "friction_type": bucket["friction_type"],
                "scenario_refs": sorted(bucket["scenario_refs"]),
                "suggested_fix_type": bucket["suggested_fix_type"],
            }
            for bucket in ranked_groups
        ],
        "dependency_notes": [
            "Preserve BATCH-Z fail-closed authority invariants while reducing operator interpretation cost.",
            "Apply BATCH-U summary/recommendation UX hardening before broader automation changes.",
        ],
        "trust_gain": {
            "score": min(95, 55 + 5 * len(prioritized_items)),
            "justification": "Prioritized items are ranked from deterministic friction evidence and retain authority boundaries.",
        },
        "operator_time_saved": {
            "minutes_per_cycle": sum(item["operator_time_saved_minutes"] for item in prioritized_items),
            "justification": "Estimated from deterministic scenario friction counts and repeated artifact-hunting overhead.",
        },
        "created_at": timestamp,
        "trace_id": trace_id,
        "source_refs": [f"operator_friction_report:{report['report_id']}"],
    }
    _validate_schema(backlog, "operator_backlog_handoff")

    return {
        "trace_id": trace_id,
        "created_at": timestamp,
        "scenario_results": scenario_results,
        "operator_friction_report": report,
        "operator_backlog_handoff": backlog,
    }


__all__ = ["run_operator_shakeout"]
