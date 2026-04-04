"""Deterministic governed BATCH-MVP-20 execution drill runner."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.system_cycle_operator import run_system_cycle


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ValueError(f"{schema_name} validation failed: {details}")


def _batch_id(index: int) -> str:
    return f"BATCH-{chr(ord('A') + index)}"


def _build_20_slice_roadmap() -> dict[str, Any]:
    batches = []
    for idx in range(20):
        batch_id = _batch_id(idx)
        depends_on = [] if idx == 0 else [_batch_id(idx - 1)]
        if idx >= 3 and idx % 5 == 0:
            depends_on.append(_batch_id(idx - 3))

        required_signals = ["roadmap_authority_resolved", "executor_ingestion_valid"]
        if idx >= 1:
            required_signals.append("state_binding_complete")

        batches.append(
            {
                "batch_id": batch_id,
                "title": f"Governed drill slice {idx + 1}",
                "step_ids": [f"MVP20-{idx + 1:02d}", f"MVP20-{idx + 1:02d}-VERIFY"],
                "depends_on": depends_on,
                "required_signals": required_signals,
                "hard_gate_after": idx in {6, 13},
                "execution_mode": "pqx_batch",
                "trust_goal": "deterministic_bounded_progression",
                "status": "not_started",
            }
        )

    return {
        "roadmap_id": "RDX-BATCH-MVP-20-2026-04-04",
        "schema_version": "1.0.0",
        "title": "BATCH-MVP-20 Governed Deterministic Roadmap Drill",
        "generated_at": "2026-04-04T00:00:00Z",
        "source_ref": "docs/roadmaps/system_roadmap.md#batch-mvp-20",
        "batches": batches,
        "current_batch_id": "BATCH-A",
        "next_hard_gate": "BATCH-G",
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


def _base_integration_inputs(trace_id: str, batch_id: str) -> dict[str, Any]:
    return {
        "program_artifact": {"program_id": "PRG-BATCH-MVP-20", "priority": "roadmap_progression"},
        "review_control_signal": {"signal_id": f"rcs-{batch_id.lower()}", "gate_assessment": "PASS"},
        "eval_result": {"run_id": f"eval-{batch_id.lower()}", "result_status": "pass"},
        "context_bundle": {"context_id": f"ctx-{batch_id.lower()}", "risks": []},
        "tpa_gate": {
            "context_bundle_ref": f"context_bundle_v2:ctx-{batch_id.lower()}",
            "speculative_expansion_detected": False,
            "gate_replaces_control": False,
        },
        "roadmap_loop_validation": {"validation_id": f"RLV-{batch_id}", "determinism_status": "deterministic"},
        "control_decision": {"decision": "allow", "review_eval_ingested": True},
        "certification_pack": {"certification_status": "complete"},
        "validation_scope": {"batch_id": batch_id, "run_id": f"run-{batch_id.lower()}", "mode": "governed_integration"},
        "trace_id": trace_id,
        "source_refs": {
            "program_artifact": "program_artifact:PRG-BATCH-MVP-20",
            "review_control_signal": f"review_control_signal:rcs-{batch_id.lower()}",
            "eval_result": f"eval_result:eval-{batch_id.lower()}",
            "context_bundle_v2": f"context_bundle_v2:ctx-{batch_id.lower()}",
            "tpa_gate": f"tpa_gate:gate-{batch_id.lower()}",
            "roadmap_execution_loop_validation": f"roadmap_execution_loop_validation:RLV-{batch_id}",
            "roadmap_multi_batch_run_result": "roadmap_multi_batch_run_result:RMB-BATCH-MVP-20",
            "control_decision": f"control_execution_result:ctrl-{batch_id.lower()}",
            "certification_pack": f"control_loop_certification_pack:cert-{batch_id.lower()}",
        },
    }


def _pqx_success(**_: object) -> dict[str, Any]:
    return {
        "status": "completed",
        "blocked_reason": None,
        "batch_result": {"status": "completed"},
        "execution_history": [
            {
                "execution_ref": "exec:mvp20:ok:1",
                "slice_execution_record_ref": "runs/pqx/mvp20.slice.json",
                "certification_ref": "runs/pqx/mvp20.cert.json",
                "audit_bundle_ref": "runs/pqx/mvp20.audit.json",
            }
        ],
    }


def _pqx_blocked(**_: object) -> dict[str, Any]:
    return {
        "status": "blocked",
        "blocked_reason": "simulated blocker for governed stop validation",
        "batch_result": {"status": "blocked"},
        "execution_history": [],
    }


def _run_drill_sequence(*, created_at: str, pqx_state_path: Path, pqx_runs_root: Path) -> dict[str, Any]:
    roadmap = _build_20_slice_roadmap()
    trace_id = f"trace-batch-mvp-20-{_canonical_hash({'created_at': created_at})[:8]}"

    run_records: list[dict[str, Any]] = []
    aggregated_decisions: list[dict[str, Any]] = []
    build_summary_refs: list[str] = []
    recommendation_refs: list[str] = []
    continuation_refs: list[str] = []
    required_review_hits = 0

    for step in range(1, 21):
        next_batch = next((batch for batch in roadmap["batches"] if batch["status"] == "not_started"), None)
        if next_batch is None:
            break
        batch_id = str(next_batch["batch_id"])
        all_batches = [
            str(batch["batch_id"])
            for batch in roadmap["batches"]
            if isinstance(batch, dict) and isinstance(batch.get("batch_id"), str)
        ]
        remaining_batches = [
            str(batch["batch_id"])
            for batch in roadmap["batches"]
            if isinstance(batch, dict) and batch.get("status") == "not_started" and isinstance(batch.get("batch_id"), str)
        ]

        selection_signals = {
            "signals": ["roadmap_authority_resolved", "executor_ingestion_valid", "state_binding_complete"],
            "hard_gates": {"BATCH-G": "pass", "BATCH-N": "pass"},
            "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
            "risk_level": "medium",
            "program_phase": "build",
            "allowed_targets": all_batches,
            "priority_ordering": remaining_batches,
            "eval_health": "healthy",
        }
        integration = _base_integration_inputs(trace_id, batch_id)
        pqx_execute_fn = _pqx_success

        if batch_id == "BATCH-F":
            integration["control_decision"]["review_eval_ingested"] = False
            required_review_hits += 1
        if batch_id == "BATCH-J":
            integration["roadmap_multi_batch_result_overrides"] = {"program_constraints_applied": True}
        if batch_id == "BATCH-K":
            pqx_execute_fn = _pqx_blocked

        cycle = run_system_cycle(
            roadmap_artifact=copy.deepcopy(roadmap),
            selection_signals=selection_signals,
            authorization_signals=_base_authorization_signals(trace_id),
            integration_inputs=integration,
            pqx_state_path=pqx_state_path,
            pqx_runs_root=pqx_runs_root,
            execution_policy={"max_batches_per_run": 1, "stop_on_hard_gate": False},
            created_at=created_at,
            pqx_execute_fn=pqx_execute_fn,
        )
        roadmap = cycle["updated_roadmap"]
        run_result = cycle["roadmap_multi_batch_run_result"]
        build_summary = cycle["build_summary"]
        recommendation = cycle["next_step_recommendation"]

        build_summary_refs.append(f"build_summary:{build_summary['summary_id']}")
        recommendation_refs.append(f"next_step_recommendation:{recommendation['recommendation_id']}")

        run_continuations = run_result.get("batch_continuation_records", [])
        continuation_refs.extend([f"batch_continuation_record:{item['continuation_id']}" for item in run_continuations])

        for item in run_result.get("continuation_decision_sequence", []):
            aggregated_decisions.append(
                {
                    "step": len(aggregated_decisions) + 1,
                    "decision": str(item["decision"]),
                    "reason_code": str(item["reason_code"]),
                }
            )

        run_records.append(
            {
                "batch_id": batch_id,
                "run_id": run_result["run_id"],
                "stop_reason": run_result["stop_reason"],
                "attempted_batch_ids": list(run_result.get("attempted_batch_ids", [])),
                "completed_batch_ids": list(run_result.get("completed_batch_ids", [])),
                "required_reviews": list(recommendation.get("required_reviews", [])),
            }
        )

        if run_result["stop_reason"] != "max_batches_reached":
            break

    attempted = [batch for record in run_records for batch in record["attempted_batch_ids"]]
    completed = [batch for record in run_records for batch in record["completed_batch_ids"]]
    blocked = [record for record in run_records if record["stop_reason"] not in {"max_batches_reached", "no_eligible_batch"}]
    escalated = [record for record in run_records if record["stop_reason"] == "authorization_block"]

    return {
        "roadmap": roadmap,
        "roadmap_id": "RDX-BATCH-MVP-20-2026-04-04",
        "trace_id": trace_id,
        "runs": run_records,
        "attempted_sequence": attempted,
        "completed_sequence": completed,
        "continuation_decision_sequence": aggregated_decisions,
        "stop_reason": run_records[-1]["stop_reason"] if run_records else "no_eligible_batch",
        "blocked_count": len(blocked),
        "escalated_count": len(escalated),
        "required_review_hits": required_review_hits,
        "build_summary_refs": sorted(set(build_summary_refs)),
        "recommendation_refs": sorted(set(recommendation_refs)),
        "continuation_refs": sorted(set(continuation_refs)),
    }


def run_mvp_20_slice_execution_drill(
    *,
    pqx_state_path: Path,
    pqx_runs_root: Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or _utc_now()

    run_a = _run_drill_sequence(created_at=timestamp, pqx_state_path=pqx_state_path, pqx_runs_root=pqx_runs_root)
    run_b = _run_drill_sequence(created_at=timestamp, pqx_state_path=pqx_state_path, pqx_runs_root=pqx_runs_root)

    parity_match = (
        run_a["attempted_sequence"] == run_b["attempted_sequence"]
        and run_a["completed_sequence"] == run_b["completed_sequence"]
        and run_a["continuation_decision_sequence"] == run_b["continuation_decision_sequence"]
        and run_a["stop_reason"] == run_b["stop_reason"]
    )

    program_alignment_ok = all(
        not any(reason.startswith("program_") for reason in [record["stop_reason"]])
        for record in run_a["runs"]
    )

    trace_integrity_ok = bool(run_a["build_summary_refs"] and run_a["recommendation_refs"] and run_a["continuation_refs"])
    blocked_before_first_slice = len(run_a["attempted_sequence"]) == 0
    governed_stop_reason = run_a["stop_reason"] if run_a["stop_reason"].startswith("program_") else "none"
    drill_mode = "positive_path"

    report_seed = {
        "roadmap_id": run_a["roadmap_id"],
        "attempted": run_a["attempted_sequence"],
        "stop": run_a["stop_reason"],
        "trace_id": run_a["trace_id"],
    }

    report = {
        "report_id": f"MVP20-{_canonical_hash(report_seed)[:12].upper()}",
        "roadmap_id": run_a["roadmap_id"],
        "total_slices_planned": 20,
        "total_slices_attempted": len(run_a["attempted_sequence"]),
        "total_slices_completed": len(run_a["completed_sequence"]),
        "total_slices_blocked": run_a["blocked_count"],
        "total_slices_escalated": run_a["escalated_count"],
        "continuation_decision_sequence": run_a["continuation_decision_sequence"],
        "stop_or_completion_reason": run_a["stop_reason"],
        "determinism_status": "deterministic" if parity_match else "mismatch_detected",
        "replay_status": "parity_verified" if parity_match else "parity_mismatch",
        "trace_integrity_status": "complete" if trace_integrity_ok else "incomplete",
        "program_alignment_status": "aligned" if program_alignment_ok else "violated",
        "operator_clarity_assessment": {
            "build_summary_readable": True,
            "next_step_recommendation_readable": True,
            "batch_continuation_record_readable": True,
            "final_report_readable": True,
            "notes": [
                f"drill_mode={drill_mode}",
                f"blocked_before_first_slice={str(blocked_before_first_slice).lower()}",
                f"governed_stop_reason={governed_stop_reason}",
                "Build summary and recommendation artifacts identify stop location and next action.",
                "Continuation records are linked for each attempted slice decision point.",
            ],
        },
        "blocking_issues": (
            ([] if run_a["stop_reason"] == "max_batches_reached" else [run_a["stop_reason"]])
            + [f"attempted_slices={len(run_a['attempted_sequence'])}"]
            + [f"attempt_explanation={'blocked_before_first_slice' if blocked_before_first_slice else 'drill_progressed_before_stop'}"]
        ),
        "created_at": timestamp,
        "trace_id": run_a["trace_id"],
        "evidence_refs": {
            "run_a": f"roadmap_multi_batch_run_result:{run_a['runs'][-1]['run_id']}",
            "run_b": f"roadmap_multi_batch_run_result:{run_b['runs'][-1]['run_id']}",
            "build_summaries": run_a["build_summary_refs"],
            "next_step_recommendations": run_a["recommendation_refs"],
            "batch_continuation_records": run_a["continuation_refs"],
            "drill_input": f"roadmap_artifact:{run_a['roadmap_id']}",
        },
    }

    _validate_schema(report, "mvp_20_slice_execution_report")

    return {
        "drill_input": _build_20_slice_roadmap(),
        "run_a": run_a,
        "run_b": run_b,
        "mvp_20_slice_execution_report": report,
    }


__all__ = ["run_mvp_20_slice_execution_drill"]
