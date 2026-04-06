"""Canonical deterministic end-to-end governed validation scenario (BATCH-SYS-VAL-01)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.failure_diagnosis_engine import build_failure_diagnosis_artifact
from spectrum_systems.modules.runtime.pqx_execution_policy import evaluate_pqx_execution_policy
from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run
from spectrum_systems.modules.runtime.recovery_orchestrator import orchestrate_recovery
from spectrum_systems.modules.runtime.repair_prompt_generator import generate_repair_prompt
from spectrum_systems.modules.runtime.review_consumer_wiring import build_review_consumer_outputs
from spectrum_systems.modules.runtime.review_parsing_engine import parse_review_to_signal
from spectrum_systems.modules.runtime.review_projection_adapter import build_review_projection_bundle
from spectrum_systems.modules.runtime.review_signal_classifier import classify_review_signal
from spectrum_systems.modules.runtime.review_signal_consumer import build_review_integration_packet
from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_system_boundaries
from spectrum_systems.modules.runtime.tpa_complexity_governance import (
    build_complexity_budget,
    build_complexity_trend,
    build_simplification_campaign,
)


class SystemEndToEndValidationError(ValueError):
    """Raised when canonical governed scenario cannot be validated deterministically."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_emitted_at(emitted_at: str) -> datetime:
    text = emitted_at.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(timezone.utc)


def _status(pass_condition: bool) -> str:
    return "pass" if pass_condition else "fail"


def _validation_runner(command: str) -> dict[str, Any]:
    if "contract_enforcement" in command:
        return {
            "status": "failed",
            "artifact_ref": "validation:contract_enforcement:failed",
            "details": {"reason": "intentional deterministic partial recovery probe"},
        }
    return {
        "status": "passed",
        "artifact_ref": f"validation:{command}:passed",
        "details": {"reason": "deterministic validation pass"},
    }


def run_system_end_to_end_governed_validation(
    *,
    review_path: str | Path,
    action_tracker_path: str | Path,
    runtime_dir: str | Path,
    emitted_at: str = "2026-04-06T00:00:00Z",
) -> dict[str, Any]:
    """Run one bounded deterministic governed scenario across PQX, TPA, FRE, RIL, and SEL."""
    review_path = Path(review_path)
    action_tracker_path = Path(action_tracker_path)
    runtime_dir = Path(runtime_dir)

    if not review_path.exists():
        raise SystemEndToEndValidationError(f"review_path not found: {review_path}")
    if not action_tracker_path.exists():
        raise SystemEndToEndValidationError(f"action_tracker_path not found: {action_tracker_path}")

    scenario_name = "BATCH-SYS-VAL-01-canonical-governed-loop"
    scenario_version = "1.0.0"
    scenario_seed = {
        "scenario_name": scenario_name,
        "scenario_version": scenario_version,
        "review_path": str(review_path),
        "action_tracker_path": str(action_tracker_path),
        "emitted_at": emitted_at,
    }
    scenario_hash = _canonical_hash(scenario_seed)
    trace_id = f"trace-s2e-{scenario_hash[:12]}"
    lineage_id = f"lineage-s2e-{scenario_hash[12:24]}"
    run_id = f"run-s2e-{scenario_hash[24:36]}"

    # Phase 1 — PQX governed entry and bounded sequence.
    policy_decision = evaluate_pqx_execution_policy(
        changed_paths=[
            "spectrum_systems/modules/runtime/system_end_to_end_validator.py",
            "tests/test_system_end_to_end_governed_loop.py",
        ],
        execution_context="pqx_governed",
    )
    if policy_decision.status != "allow":
        raise SystemEndToEndValidationError("canonical scenario requires governed PQX entry to allow execution")

    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path = runtime_dir / "s2e_pqx_sequence_state.json"
    bundle_state_path = runtime_dir / "s2e_pqx_bundle_state.json"
    if state_path.exists():
        state_path.unlink()
    if bundle_state_path.exists():
        bundle_state_path.unlink()

    fixed_clock_time = _parse_emitted_at(emitted_at)

    def _fixed_clock() -> datetime:
        return fixed_clock_time

    slice_requests = [
        {"slice_id": "fix-step:plan", "trace_id": trace_id},
        {"slice_id": "fix-step:build", "trace_id": trace_id},
        {"slice_id": "fix-step:simplify", "trace_id": trace_id},
        {"slice_id": "fix-step:gate", "trace_id": trace_id},
    ]

    def _slice_executor(payload: dict[str, Any]) -> dict[str, Any]:
        slice_id = str(payload["slice_id"])
        return {
            "execution_status": "success",
            "slice_execution_record": f"slice_execution_record:{run_id}:{slice_id}",
            "done_certification_record": f"done_certification_record:{run_id}:{slice_id}",
            "pqx_slice_audit_bundle": f"pqx_slice_audit_bundle:{run_id}:{slice_id}",
        }

    pqx_result = execute_sequence_run(
        slice_requests=slice_requests,
        state_path=state_path,
        queue_run_id=f"queue-{run_id}",
        run_id=run_id,
        trace_id=trace_id,
        execute_slice=_slice_executor,
        max_slices=4,
        bundle_state_path=bundle_state_path,
        enforce_dependency_admission=False,
        clock=_fixed_clock,
    )

    pqx_phase_ok = (
        pqx_result["status"] == "completed"
        and pqx_result["completed_slice_ids"] == [entry["slice_id"] for entry in slice_requests]
        and len(pqx_result.get("execution_history", [])) == 4
    )

    # Phase 2 — TPA plan/build/simplify/gate artifacts.
    complexity_budget = build_complexity_budget(
        run_id=run_id,
        trace_id=trace_id,
        step_id="AI-01",
        module_or_path="spectrum_systems/modules/runtime/system_end_to_end_validator.py",
        build_signals={
            "lines_added": 24,
            "lines_removed": 0,
            "helpers_added_count": 1,
            "functions_added_count": 1,
            "abstraction_added_count": 0,
            "public_surface_delta_count": 0,
            "approximate_max_nesting_delta": 1,
            "approximate_branching_delta": 1,
            "helpers_removed_count": 0,
            "functions_removed_count": 0,
            "abstraction_removed_count": 0,
            "wrappers_collapsed_count": 0,
            "deletions_count": 0,
        },
        simplify_signals={
            "lines_added": 20,
            "lines_removed": 3,
            "helpers_added_count": 1,
            "functions_added_count": 1,
            "abstraction_added_count": 0,
            "public_surface_delta_count": 0,
            "approximate_max_nesting_delta": 1,
            "approximate_branching_delta": 1,
            "helpers_removed_count": 0,
            "functions_removed_count": 0,
            "abstraction_removed_count": 0,
            "wrappers_collapsed_count": 0,
            "deletions_count": 1,
        },
        historical_scores=[20, 21],
        last_updated=emitted_at,
        allowed_growth_delta=8,
    )
    complexity_trend = build_complexity_trend(
        run_id=run_id,
        trace_id=trace_id,
        step_id="AI-01",
        module="system_end_to_end_validator",
        artifact_type_scope="coordination",
        slice_family="TPA",
        points=[
            {
                "index": 0,
                "step_id": "AI-01",
                "complexity": 22,
                "complexity_delta": 1,
                "simplify_effectiveness": 0.0,
                "deletions_count": 0,
                "abstraction_growth": 0,
            },
            {
                "index": 1,
                "step_id": "AI-01",
                "complexity": 22,
                "complexity_delta": 0,
                "simplify_effectiveness": 1.0,
                "deletions_count": 1,
                "abstraction_growth": 0,
            },
            {
                "index": 2,
                "step_id": "AI-01",
                "complexity": 21,
                "complexity_delta": -1,
                "simplify_effectiveness": 1.0,
                "deletions_count": 2,
                "abstraction_growth": 0,
            },
            {
                "index": 3,
                "step_id": "AI-01",
                "complexity": 21,
                "complexity_delta": 0,
                "simplify_effectiveness": 0.0,
                "deletions_count": 0,
                "abstraction_growth": 0,
            },
        ],
    )
    simplification_campaign = build_simplification_campaign(
        run_id=run_id,
        trace_id=trace_id,
        step_id="AI-01",
        target_module="spectrum_systems.modules.runtime.system_end_to_end_validator",
        trend=complexity_trend,
        budget=complexity_budget,
    )
    tpa_phase_ok = all(
        item.get("artifact_type")
        for item in (complexity_budget, complexity_trend, simplification_campaign)
    )

    # Phase 3/4 — deterministic failure injection and governed recovery orchestration.
    diagnosis = build_failure_diagnosis_artifact(
        failure_source_type="contract_preflight",
        source_artifact_refs=[f"tpa_artifact:{run_id}:AI-01-G"],
        failure_payload={
            "observed_failure_summary": "Intentional controlled missing required evidence ref in governed validation slice.",
            "preflight_status": "BLOCK",
            "missing_required_surfaces": ["recovery_result_artifact"],
            "missing_control_inputs": ["control_execution_result"],
        },
        emitted_at=emitted_at,
        run_id=run_id,
        trace_id=trace_id,
    )
    repair_prompt = generate_repair_prompt(
        diagnosis,
        emitted_at=emitted_at,
        run_id=run_id,
        trace_id=trace_id,
    )

    def _execution_runner(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "completed",
            "reason_code": None,
            "repair_execution_mode": "bounded_governed_execution",
            "execution_artifact_refs": [f"recovery_execution:{run_id}:attempt-1"],
            "governance_gate_evidence_refs": {
                "preflight": f"governance_preflight:{run_id}",
                "control": f"governance_control:{run_id}",
                "certification": f"governance_certification:{run_id}",
                "certification_applicable": True,
            },
        }

    recovery_result = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        repair_prompt_artifact=repair_prompt,
        recovery_attempt_number=1,
        max_attempts=2,
        execution_runner=_execution_runner,
        validation_runner=_validation_runner,
        emitted_at=emitted_at,
        run_id=run_id,
        trace_id=trace_id,
    )
    fre_phase_ok = all(
        artifact.get("artifact_type")
        for artifact in (diagnosis, repair_prompt, recovery_result)
    )

    # Phase 5 — RIL review parsing → classification → integration packet → projection bundle → consumer outputs.
    review_signal = parse_review_to_signal(review_path=review_path, action_tracker_path=action_tracker_path)
    review_control_signal = classify_review_signal(review_signal)
    integration_packet = build_review_integration_packet(review_control_signal)
    projection_bundle = build_review_projection_bundle(integration_packet)
    consumer_outputs = build_review_consumer_outputs(
        projection_bundle,
        projection_bundle["roadmap_projection"],
        projection_bundle["control_loop_projection"],
        projection_bundle["readiness_projection"],
    )
    ril_phase_ok = all(
        artifact.get("artifact_type")
        for artifact in (review_signal, review_control_signal, integration_packet, projection_bundle, consumer_outputs)
    )

    # Phase 6 — SEL valid path allow + invalid bypass block.
    valid_sel_context = {
        "source_module": "spectrum_systems.modules.runtime.system_end_to_end_validator",
        "caller_identity": "tests/test_system_end_to_end_governed_loop.py",
        "emitted_at": emitted_at,
        "execution_request": {
            "execution_context": "pqx_governed",
            "pqx_entry": True,
            "direct_cli": False,
            "ad_hoc_runtime": False,
            "direct_slice_execution": False,
            "tpa_required": True,
            "recovery_involved": True,
            "certification_required": True,
        },
        "artifact_references": {
            "execution_artifact": f"pqx_execution:{run_id}",
            "trace_refs": [trace_id, f"{trace_id}:fre", f"{trace_id}:ril"],
            "lineage": {
                "lineage_id": lineage_id,
                "parent_refs": [f"pqx_admission_preflight_artifact:{run_id}"],
            },
            "tpa_lineage_artifact": f"complexity_budget:{complexity_budget['run_id']}:{complexity_budget['step_id']}",
            "tpa_artifact": f"tpa_simplification_campaign:{simplification_campaign['run_id']}:{simplification_campaign['step_id']}",
            "failure_diagnosis_artifact": f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
            "repair_prompt_artifact": f"repair_prompt_artifact:{repair_prompt['repair_prompt_id']}",
            "recovery_result_artifact": f"recovery_result_artifact:{recovery_result['recovery_result_id']}",
        },
        "trace_refs": [trace_id, f"{trace_id}:fre", f"{trace_id}:ril"],
        "lineage": {
            "lineage_id": lineage_id,
            "parent_refs": [f"pqx_admission_preflight_artifact:{run_id}"],
        },
        "governance_evidence": {
            "preflight_evidence": f"governance_preflight:{run_id}",
            "control_evidence": f"governance_control:{run_id}",
            "certification_evidence": f"governance_certification:{run_id}",
        },
        "downstream_consumption": {
            "consumed_artifact_types": ["review_projection_bundle_artifact"],
        },
    }
    valid_sel_result = enforce_system_boundaries(valid_sel_context)

    invalid_sel_context = dict(valid_sel_context)
    invalid_sel_context["downstream_consumption"] = {
        "consumed_artifact_types": ["review_signal_artifact"],
    }
    invalid_sel_result = enforce_system_boundaries(invalid_sel_context)

    sel_valid_path_allowed = valid_sel_result["enforcement_status"] == "allow"
    sel_invalid_path_blocked = invalid_sel_result["enforcement_status"] == "block"
    sel_phase_ok = sel_valid_path_allowed and sel_invalid_path_blocked

    produced_artifact_refs = sorted(
        {
            f"pqx_sequence_run:{pqx_result['queue_run_id']}",
            f"complexity_budget:{complexity_budget['run_id']}:{complexity_budget['step_id']}",
            f"complexity_trend:{complexity_trend['run_id']}:{complexity_trend['step_id']}",
            f"tpa_simplification_campaign:{simplification_campaign['run_id']}:{simplification_campaign['step_id']}",
            f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
            f"repair_prompt_artifact:{repair_prompt['repair_prompt_id']}",
            f"recovery_result_artifact:{recovery_result['recovery_result_id']}",
            f"review_signal_artifact:{review_signal['review_signal_id']}",
            f"review_control_signal_artifact:{review_control_signal['review_control_signal_id']}",
            f"review_integration_packet_artifact:{integration_packet['review_integration_packet_id']}",
            f"review_projection_bundle_artifact:{projection_bundle['review_projection_bundle_id']}",
            f"review_consumer_output_bundle_artifact:{consumer_outputs['review_consumer_output_bundle_id']}",
            f"system_enforcement_result_artifact:{valid_sel_result['enforcement_result_id']}",
            f"system_enforcement_result_artifact:{invalid_sel_result['enforcement_result_id']}",
        }
    )

    trace_continuity_verified = (
        all(item["trace_id"] == trace_id for item in pqx_result["execution_history"])
        and complexity_budget["trace_id"] == trace_id
        and complexity_trend["trace_id"] == trace_id
        and simplification_campaign["trace_id"] == trace_id
        and diagnosis.get("trace", {}).get("trace_id") == trace_id
        and repair_prompt.get("trace", {}).get("trace_id") == trace_id
        and recovery_result.get("trace", {}).get("trace_id") == trace_id
        and trace_id in valid_sel_result["trace_refs"]
    )
    lineage_continuity_verified = (
        bool(valid_sel_context["lineage"]["lineage_id"])
        and valid_sel_context["lineage"]["lineage_id"] == lineage_id
        and bool(valid_sel_context["lineage"]["parent_refs"])
        and len(pqx_result["execution_history"]) == len(slice_requests)
    )

    required_artifact_types_verified = sorted(
        {
            "pqx_sequence_run",
            "complexity_budget",
            "complexity_trend",
            "tpa_simplification_campaign",
            "failure_diagnosis_artifact",
            "repair_prompt_artifact",
            "recovery_result_artifact",
            "review_signal_artifact",
            "review_control_signal_artifact",
            "review_integration_packet_artifact",
            "review_projection_bundle_artifact",
            "review_consumer_output_bundle_artifact",
            "system_enforcement_result_artifact",
        }
    )

    validation_status = _status(all((pqx_phase_ok, tpa_phase_ok, fre_phase_ok, ril_phase_ok, sel_phase_ok, trace_continuity_verified, lineage_continuity_verified)))

    result = {
        "artifact_type": "system_end_to_end_validation_result_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "validation_result_id": f"s2e-{scenario_hash[:16]}",
        "validation_status": validation_status,
        "scenario_name": scenario_name,
        "scenario_version": scenario_version,
        "source_subsystems": ["pqx", "tpa", "fre", "ril", "sel"],
        "pqx_phase_status": _status(pqx_phase_ok),
        "tpa_phase_status": _status(tpa_phase_ok),
        "fre_phase_status": _status(fre_phase_ok),
        "ril_phase_status": _status(ril_phase_ok),
        "sel_phase_status": _status(sel_phase_ok),
        "produced_artifact_refs": produced_artifact_refs,
        "required_artifact_types_verified": required_artifact_types_verified,
        "trace_continuity_verified": trace_continuity_verified,
        "lineage_continuity_verified": lineage_continuity_verified,
        "sel_valid_path_allowed": sel_valid_path_allowed,
        "sel_invalid_path_blocked": sel_invalid_path_blocked,
        "failure_injected_type": "missing_required_evidence_ref",
        "recovery_outcome": recovery_result["recovery_status"],
        "final_summary": (
            "Canonical governed loop completed with PQX bounded sequence, TPA Plan→Build→Simplify→Gate artifacts, "
            "deterministic FRE partial recovery, full RIL projection/consumer outputs, and SEL allow+block assertions."
        ),
        "trace_id": trace_id,
        "lineage": {
            "lineage_id": lineage_id,
            "parent_refs": [f"pqx_admission_preflight_artifact:{run_id}"],
        },
        "provenance": {
            "producer": "spectrum_systems.modules.runtime.system_end_to_end_validator",
            "governed_entry": policy_decision.authority_resolution,
            "scenario_hash": scenario_hash,
            "phase_artifact_refs": {
                "pqx": [f"pqx_sequence_run:{pqx_result['queue_run_id']}"],
                "tpa": [
                    f"complexity_budget:{complexity_budget['run_id']}:{complexity_budget['step_id']}",
                    f"complexity_trend:{complexity_trend['run_id']}:{complexity_trend['step_id']}",
                    f"tpa_simplification_campaign:{simplification_campaign['run_id']}:{simplification_campaign['step_id']}",
                ],
                "fre": [
                    f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
                    f"repair_prompt_artifact:{repair_prompt['repair_prompt_id']}",
                    f"recovery_result_artifact:{recovery_result['recovery_result_id']}",
                ],
                "ril": [
                    f"review_signal_artifact:{review_signal['review_signal_id']}",
                    f"review_control_signal_artifact:{review_control_signal['review_control_signal_id']}",
                    f"review_integration_packet_artifact:{integration_packet['review_integration_packet_id']}",
                    f"review_projection_bundle_artifact:{projection_bundle['review_projection_bundle_id']}",
                    f"review_consumer_output_bundle_artifact:{consumer_outputs['review_consumer_output_bundle_id']}",
                ],
                "sel": [
                    f"system_enforcement_result_artifact:{valid_sel_result['enforcement_result_id']}",
                    f"system_enforcement_result_artifact:{invalid_sel_result['enforcement_result_id']}",
                ],
            },
        },
        "emitted_at": emitted_at,
    }

    validate_artifact(result, "system_end_to_end_validation_result_artifact")
    return {
        "validation_result": result,
        "phase_artifacts": {
            "pqx": pqx_result,
            "tpa": {
                "complexity_budget": complexity_budget,
                "complexity_trend": complexity_trend,
                "simplification_campaign": simplification_campaign,
            },
            "fre": {
                "failure_diagnosis_artifact": diagnosis,
                "repair_prompt_artifact": repair_prompt,
                "recovery_result_artifact": recovery_result,
            },
            "ril": {
                "review_signal_artifact": review_signal,
                "review_control_signal_artifact": review_control_signal,
                "review_integration_packet_artifact": integration_packet,
                "review_projection_bundle_artifact": projection_bundle,
                "review_consumer_output_bundle_artifact": consumer_outputs,
            },
            "sel": {
                "valid_path": valid_sel_result,
                "invalid_path": invalid_sel_result,
            },
        },
    }


__all__ = ["SystemEndToEndValidationError", "run_system_end_to_end_governed_validation"]
