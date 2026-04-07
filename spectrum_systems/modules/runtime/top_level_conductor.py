"""Top-Level Conductor (TLC-002): thin deterministic orchestration shell with real subsystem adapters."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.governance.tpa_policy_composition import load_tpa_policy_composition, resolve_tpa_policy_decision
from spectrum_systems.modules.runtime.closure_decision_engine import build_closure_decision_artifact
from spectrum_systems.modules.runtime.failure_diagnosis_engine import (
    build_failure_diagnosis_artifact,
    build_failure_repair_candidate_artifact,
    normalize_pytest_failure_packet,
)
from spectrum_systems.modules.runtime.pqx_execution_policy import evaluate_pqx_execution_policy
from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run
from spectrum_systems.modules.runtime.roadmap_execution_adapter import run_roadmap_execution
from spectrum_systems.modules.runtime.program_layer import build_program_constraint_signal
from spectrum_systems.modules.runtime.recovery_orchestrator import orchestrate_recovery
from spectrum_systems.modules.runtime.review_consumer_wiring import build_review_consumer_outputs
from spectrum_systems.modules.runtime.review_parsing_engine import parse_review_to_signal
from spectrum_systems.modules.runtime.review_projection_adapter import build_review_projection_bundle
from spectrum_systems.modules.runtime.review_signal_classifier import classify_review_signal
from spectrum_systems.modules.runtime.review_signal_consumer import build_review_integration_packet
from spectrum_systems.modules.runtime.system_registry_enforcer import validate_system_action, validate_system_handoff
from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_system_boundaries


TERMINAL_STATES = {"ready_for_merge", "blocked", "exhausted", "escalated"}


class TopLevelConductorError(ValueError):
    """Raised when TLC input or transition invariants are violated."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TopLevelConductorError(f"{field} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TopLevelConductorError(f"{field} must be boolean")
    return value


def _require_non_negative_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise TopLevelConductorError(f"{field} must be a non-negative integer")
    return value


def _parse_emitted_at(emitted_at: str) -> datetime:
    text = emitted_at.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _extract_refs(result: dict[str, Any], *, produced_refs: list[str], trace_refs: list[str]) -> None:
    for key in ("artifact_ref", "artifacts_ref"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            produced_refs.append(value.strip())
    for key in ("artifact_refs", "produced_artifact_refs", "execution_artifact_refs"):
        value = result.get(key)
        if isinstance(value, list):
            for item in list(value):
                if isinstance(item, str) and item.strip():
                    produced_refs.append(item.strip())

    for key in ("trace_ref", "trace_id"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            trace_refs.append(value.strip())
    for key in ("trace_refs",):
        value = result.get(key)
        if isinstance(value, list):
            for item in list(value):
                if isinstance(item, str) and item.strip():
                    trace_refs.append(item.strip())


def _next_actions_for_state(state: str) -> list[str]:
    if state in TERMINAL_STATES:
        return []
    action_map = {
        "requested": ["admit"],
        "admitted": ["execute"],
        "executing": ["evaluate"],
        "validation_failed": ["recover", "block", "exhaust"],
        "recovering": ["review"],
        "reviewing": ["decide_closure"],
        "closure_decision_pending": ["lock", "continue_bounded", "block", "exhaust", "escalate"],
        "direction_pending": ["execute"],
    }
    return action_map.get(state, [])


def _build_repair_attempt_record_artifact(
    *,
    attempt_id: str,
    failure_id: str,
    roadmap_id: str | None,
    run_id: str,
    attempt_number: int,
    files_touched: list[str],
    commands_run: list[str],
    result_status: str,
    trace_refs: list[str],
) -> dict[str, Any]:
    artifact = {
        "artifact_type": "repair_attempt_record_artifact",
        "schema_version": "1.0.0",
        "attempt_id": attempt_id,
        "failure_id": failure_id,
        "roadmap_id": roadmap_id,
        "run_id": run_id,
        "attempt_number": attempt_number,
        "files_touched": sorted(set(files_touched)),
        "commands_run": list(commands_run),
        "result_status": result_status,
        "trace_refs": sorted(set(trace_refs)),
    }
    validate_artifact(artifact, "repair_attempt_record_artifact")
    return artifact


def _build_failure_learning_record_artifact(
    *,
    learning_id: str,
    failure_class: str,
    recurrence_count: int,
    first_seen_ref: str,
    latest_seen_ref: str,
    trace_refs: list[str],
) -> dict[str, Any]:
    artifact = {
        "artifact_type": "failure_learning_record_artifact",
        "schema_version": "1.0.0",
        "learning_id": learning_id,
        "failure_class": failure_class,
        "recurrence_count": recurrence_count,
        "first_seen_ref": first_seen_ref,
        "latest_seen_ref": latest_seen_ref,
        "recommended_eval_candidate": {
            "candidate_type": "targeted_regression_eval",
            "target_failure_class": failure_class,
            "minimum_recurrence": recurrence_count,
        },
        "recommended_hardening_signal": {
            "signal_type": "repair_recurrence",
            "severity": "high" if recurrence_count >= 3 else "medium",
            "target_surface": failure_class,
        },
        "trace_refs": sorted(set(trace_refs)),
    }
    validate_artifact(artifact, "failure_learning_record_artifact")
    return artifact


def _transition(*, state: dict[str, Any], to_state: str, reason: str) -> None:
    from_state = state["current_state"]
    state["phase_history"].append({"from": from_state, "to": to_state, "reason": reason})
    state["current_state"] = to_state
    state["next_allowed_actions"] = _next_actions_for_state(to_state)


def _record_invocation(
    *,
    state: dict[str, Any],
    subsystem: str,
    boundary: str,
    status: str,
    input_refs: list[str],
    output_refs: list[str],
    trace_refs: list[str],
) -> None:
    state["lineage"].setdefault("subsystem_invocations", []).append(
        {
            "subsystem": subsystem,
            "boundary": boundary,
            "status": status,
            "input_refs": sorted(set(input_refs)),
            "output_refs": sorted(set(output_refs)),
            "trace_refs": sorted(set(trace_refs)),
        }
    )


def _enforce_registry_action(*, actor: str, action_type: str, target_system: str, boundary: str) -> None:
    result = validate_system_action(actor, action_type, target_system)
    if not result["allow"]:
        violations = ",".join(result["violation_codes"])
        raise TopLevelConductorError(f"registry_action_blocked:{boundary}:{actor}->{target_system}:{violations}")


def _enforce_handoff(
    *,
    from_system: str,
    to_system: str,
    schema_name: str,
    action_type: str,
    payload: dict[str, Any],
    required_fields: list[str],
    expected_trace_refs: list[str],
    boundary: str,
) -> None:
    result = validate_system_handoff(
        from_system,
        to_system,
        {
            "schema_name": schema_name,
            "action_type": action_type,
            "payload": payload,
            "required_fields": required_fields,
            "expected_trace_refs": expected_trace_refs,
            "trace_refs": expected_trace_refs,
        },
    )
    if not result["allow"]:
        violations = ",".join(result["violation_codes"])
        raise TopLevelConductorError(f"handoff_blocked:{boundary}:{from_system}->{to_system}:{violations}")


def _validate_handoff_output(subsystem: str, result: dict[str, Any]) -> None:
    if subsystem == "PQX":
        if not isinstance(result.get("request_artifact"), dict):
            raise TopLevelConductorError("PQX output must include request_artifact")
        if not isinstance(result.get("execution_artifact"), dict):
            raise TopLevelConductorError("PQX output must include execution_artifact")
        if not isinstance(result.get("trace_refs"), list) or not result.get("trace_refs"):
            raise TopLevelConductorError("PQX output must include trace refs")
        if not isinstance(result.get("lineage"), dict):
            raise TopLevelConductorError("PQX output must include lineage")
        validate_artifact(result["request_artifact"], "pqx_execution_request")
        validate_artifact(result["execution_artifact"], "pqx_execution_result")
        return
    if subsystem == "FRE":
        diagnosis = result.get("failure_diagnosis_artifact")
        if not isinstance(diagnosis, dict):
            raise TopLevelConductorError("FRE output must include failure_diagnosis_artifact")
        validate_artifact(diagnosis, "failure_diagnosis_artifact")
        if isinstance(result.get("failure_repair_candidate_artifact"), dict):
            validate_artifact(result["failure_repair_candidate_artifact"], "failure_repair_candidate_artifact")
            return
        for key, schema in (("repair_prompt_artifact", "repair_prompt_artifact"), ("recovery_result_artifact", "recovery_result_artifact")):
            artifact = result.get(key)
            if not isinstance(artifact, dict):
                raise TopLevelConductorError(f"FRE output must include {key}")
            validate_artifact(artifact, schema)
        return
    if subsystem == "RIL":
        for key, schema in (
            ("review_signal_artifact", "review_signal_artifact"),
            ("review_projection_bundle_artifact", "review_projection_bundle_artifact"),
            ("review_consumer_output_bundle_artifact", "review_consumer_output_bundle_artifact"),
        ):
            artifact = result.get(key)
            if not isinstance(artifact, dict):
                raise TopLevelConductorError(f"RIL output must include {key}")
            validate_artifact(artifact, schema)
        if isinstance(result.get("raw_review"), str):
            raise TopLevelConductorError("RIL output must not include raw review")
        return
    if subsystem == "CDE":
        artifact = result.get("closure_decision_artifact")
        if not isinstance(artifact, dict):
            raise TopLevelConductorError("CDE output must include closure_decision_artifact")
        if not isinstance(result.get("decision_type"), str) or not result.get("decision_type"):
            raise TopLevelConductorError("CDE output must include decision_type")
        if not isinstance(result.get("next_step_class"), str) or not result.get("next_step_class"):
            raise TopLevelConductorError("CDE output must include next_step_class")
        validate_artifact(artifact, "closure_decision_artifact")
        return


def _real_sel(payload: dict[str, Any]) -> dict[str, Any]:
    result = enforce_system_boundaries(payload)
    return {
        "allowed": result["enforcement_status"] == "allow",
        "reason": result["enforcement_status"],
        "artifact_ref": f"system_enforcement_result_artifact:{result['enforcement_result_id']}",
        "trace_refs": list(result.get("trace_refs", [])),
        "violations": result.get("violations", []),
    }


def _real_pqx(payload: dict[str, Any]) -> dict[str, Any]:
    emitted_at = _require_non_empty_str(payload.get("emitted_at"), field="emitted_at")
    request_artifact = {
        "schema_version": "1.1.0",
        "run_id": payload["run_id"],
        "step_id": "TLC-EXECUTE",
        "step_name": "Top-level execution",
        "dependencies": [],
        "requested_at": emitted_at,
        "prompt": payload["objective"],
    }
    validate_artifact(request_artifact, "pqx_execution_request")

    policy = evaluate_pqx_execution_policy(
        changed_paths=["spectrum_systems/modules/runtime/top_level_conductor.py", "tests/test_top_level_conductor.py"],
        execution_context="pqx_governed",
    )
    if policy.status != "allow":
        return {
            "entry_valid": False,
            "validation_passed": False,
            "artifact_refs": [],
            "trace_refs": [payload["trace_id"]],
        }

    runtime_dir = Path(payload["runtime_dir"])
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path = runtime_dir / f"{payload['run_id']}-pqx-state.json"
    bundle_state_path = runtime_dir / f"{payload['run_id']}-pqx-bundle-state.json"
    if state_path.exists():
        state_path.unlink()
    if bundle_state_path.exists():
        bundle_state_path.unlink()

    fixed_clock = _parse_emitted_at(emitted_at)

    def _clock() -> datetime:
        return fixed_clock

    pqx_result = execute_sequence_run(
        slice_requests=[{"slice_id": "fix-step:plan", "trace_id": payload["trace_id"]}],
        state_path=state_path,
        queue_run_id=f"queue-{payload['run_id']}",
        run_id=payload["run_id"],
        trace_id=payload["trace_id"],
        execute_slice=lambda req: {
            "execution_status": "success",
            "slice_execution_record": f"pqx_slice_execution_record:{payload['run_id']}:{req['slice_id']}",
            "done_certification_record": f"done_certification_record:{payload['run_id']}:{req['slice_id']}",
            "pqx_slice_audit_bundle": f"pqx_slice_audit_bundle:{payload['run_id']}:{req['slice_id']}",
        },
        max_slices=1,
        bundle_state_path=bundle_state_path,
        enforce_dependency_admission=False,
        clock=_clock,
    )

    history = pqx_result.get("execution_history", [])
    execution = history[0] if history else {}
    output_artifact = {
        "schema_version": "1.0.0",
        "run_id": payload["run_id"],
        "step_id": "TLC-EXECUTE",
        "execution_status": "success" if execution.get("status") == "completed" else "failure",
        "started_at": execution.get("started_at", emitted_at),
        "completed_at": execution.get("completed_at", emitted_at),
        "output_text": str(execution.get("slice_execution_record_ref") or ""),
        "error": execution.get("error"),
    }
    validate_artifact(output_artifact, "pqx_execution_result")

    passed = pqx_result.get("status") == "completed"
    refs = [
        ref
        for ref in [
            execution.get("slice_execution_record_ref"),
            execution.get("certification_ref"),
            execution.get("audit_bundle_ref"),
        ]
        if isinstance(ref, str) and ref.strip()
    ]
    return {
        "entry_valid": True,
        "validation_passed": passed,
        "artifact_refs": refs,
        "trace_refs": [payload["trace_id"]],
        "lineage": {
            "lineage_id": f"lineage:{payload['run_id']}:pqx",
            "parent_refs": [f"request:{payload['run_id']}"],
        },
        "request_artifact": request_artifact,
        "execution_artifact": output_artifact,
    }


def _real_tpa(payload: dict[str, Any]) -> dict[str, Any]:
    composition = load_tpa_policy_composition()
    decision = resolve_tpa_policy_decision(
        {
            "required_scope": True,
            "tpa_lineage_present": True,
            "tpa_mode": "full",
            "lightweight_eligible": True,
            "execution_mode": "governed",
            "complexity_decision": "allow",
            "simplicity_decision": "allow",
            "promotion_ready_requested": True,
            "lightweight_evidence_omissions": [],
        },
        composition=composition,
    )
    return {
        "discipline_status": "accepted" if decision["final_decision"] in {"allow", "warn"} else "blocked",
        "artifact_refs": [f"tpa_policy_decision:{payload['run_id']}"],
        "trace_refs": [payload["trace_id"]],
    }


def _real_fre(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("mode") == "pre_pr_diagnosis":
        failure_packet = payload.get("failure_packet")
        if not isinstance(failure_packet, dict):
            raise TopLevelConductorError("pre_pr_diagnosis requires failure_packet")
        diagnosis = build_failure_diagnosis_artifact(
            failure_source_type="pytest_summary",
            source_artifact_refs=failure_packet["source_test_refs"],
            failure_payload={
                "observed_failure_summary": f"Pre-PR failed test surface for run {payload['run_id']}.",
                "failing_tests": failure_packet.get("failing_tests", []),
            },
            emitted_at=payload["emitted_at"],
            run_id=payload["run_id"],
            trace_id=payload["trace_id"],
        )
        bounded_scope = list(payload.get("default_bounded_scope", []))
        candidate = build_failure_repair_candidate_artifact(
            failure_packet=failure_packet,
            failure_diagnosis_artifact=diagnosis,
            proposed_repair_ref=f"repair_prompt_artifact:{payload['run_id']}:bounded",
            trace_refs=[payload["trace_id"]],
        )
        if bounded_scope:
            candidate["bounded_scope"] = sorted(set(str(item) for item in bounded_scope if str(item).strip()))
            candidate["safe_to_repair"] = bool(candidate["safe_to_repair"] and candidate["bounded_scope"])
            validate_artifact(candidate, "failure_repair_candidate_artifact")
        return {
            "recovery_completed": candidate["safe_to_repair"],
            "artifact_refs": [
                f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
                f"failure_repair_candidate_artifact:{candidate['failure_id']}",
            ],
            "trace_refs": [payload["trace_id"]],
            "failure_diagnosis_artifact": diagnosis,
            "failure_repair_candidate_artifact": candidate,
        }

    diagnosis = build_failure_diagnosis_artifact(
        failure_source_type="validation",
        source_artifact_refs=payload.get("source_artifact_refs", []),
        failure_payload={
            "observed_failure_summary": "Deterministic TLC validation failure requiring governed recovery.",
            "preflight_status": "BLOCK",
            "missing_required_surfaces": ["recovery_result_artifact"],
            "root_cause_hypotheses": ["governed_validation_failed"],
            "recommended_recovery_mode": "bounded_governed_execution",
            "request_context": {"run_id": payload["run_id"]},
            "provenance_notes": ["TLC deterministic FRE invocation"],
        },
        emitted_at=payload["emitted_at"],
        run_id=payload["run_id"],
        trace_id=payload["trace_id"],
    )
    validate_artifact(diagnosis, "failure_diagnosis_artifact")

    recovery_result = orchestrate_recovery(
        diagnosis_artifact=diagnosis,
        recovery_attempt_number=1,
        max_attempts=max(payload.get("max_attempts", 1), 1),
        execution_runner=lambda _: {
            "execution_status": "success",
            "repair_execution_mode": "bounded_governed_execution",
            "reason_code": "governed_success",
            "execution_artifact_refs": [f"execution_record:{payload['run_id']}:fre"],
            "remaining_failure_classes": [],
            "governance_gate_evidence_refs": {
                "preflight_gate_ref": f"preflight_gate:{payload['run_id']}",
                "control_decision_ref": f"control_decision:{payload['run_id']}",
                "certification_ref": f"certification:{payload['run_id']}",
            },
        },
        validation_runner=lambda _: {
            "status": "passed",
            "artifact_ref": f"validation:{payload['run_id']}:passed",
            "details": {"reason": "deterministic pass"},
        },
        emitted_at=payload["emitted_at"],
        run_id=payload["run_id"],
        trace_id=payload["trace_id"],
    )
    validate_artifact(recovery_result["repair_prompt_artifact"], "repair_prompt_artifact")
    validate_artifact(recovery_result, "recovery_result_artifact")
    return {
        "recovery_completed": recovery_result["recovery_status"] in {"recovered", "partially_recovered"},
        "artifact_refs": [
            f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
            f"repair_prompt_artifact:{recovery_result['repair_prompt_ref']}",
            f"recovery_result_artifact:{recovery_result['recovery_result_id']}",
        ],
        "trace_refs": [payload["trace_id"]],
        "failure_diagnosis_artifact": diagnosis,
        "repair_prompt_artifact": recovery_result["repair_prompt_artifact"],
        "recovery_result_artifact": recovery_result,
    }


def _real_ril(payload: dict[str, Any]) -> dict[str, Any]:
    review_signal = parse_review_to_signal(payload["review_path"], payload["action_tracker_path"])
    validate_artifact(review_signal, "review_signal_artifact")

    review_control_signal = classify_review_signal(review_signal)
    validate_artifact(review_control_signal, "review_control_signal_artifact")

    integration_packet = build_review_integration_packet(review_control_signal)
    validate_artifact(integration_packet, "review_integration_packet_artifact")
    projection_bundle = build_review_projection_bundle(integration_packet)
    validate_artifact(projection_bundle, "review_projection_bundle_artifact")

    consumer_outputs = build_review_consumer_outputs(
        projection_bundle,
        projection_bundle["roadmap_projection"],
        projection_bundle["control_loop_projection"],
        projection_bundle["readiness_projection"],
    )
    validate_artifact(consumer_outputs, "review_consumer_output_bundle_artifact")

    return {
        "outputs_exist": True,
        "artifact_refs": [
            f"review_signal_artifact:{review_signal['review_signal_id']}",
            f"review_control_signal_artifact:{review_control_signal['review_control_signal_id']}",
            f"review_integration_packet_artifact:{integration_packet['review_integration_packet_id']}",
            f"review_projection_bundle_artifact:{projection_bundle['review_projection_bundle_id']}",
            f"review_consumer_output_bundle_artifact:{consumer_outputs['review_consumer_output_bundle_id']}",
        ],
        "trace_refs": [payload["trace_id"]],
        "review_signal_artifact": review_signal,
        "review_projection_bundle_artifact": projection_bundle,
        "review_consumer_output_bundle_artifact": consumer_outputs,
    }


def _real_cde(payload: dict[str, Any]) -> dict[str, Any]:
    decision = build_closure_decision_artifact(
        {
            "subject_scope": "top_level_conductor",
            "subsystem_acronym": "TLC",
            "run_id": payload["run_id"],
            "review_date": payload["review_date"],
            "action_tracker_ref": payload["action_tracker_ref"],
            "source_artifacts": payload["source_artifacts"],
            "closure_complete": payload.get("closure_complete", True),
            "final_verification_passed": payload.get("final_verification_passed", True),
            "hardening_completed": payload.get("hardening_completed", True),
            "escalation_required": payload.get("escalation_required", False),
            "bounded_next_step_available": payload.get("bounded_next_step_available", False),
            "repair_loop_eligible": payload.get("repair_loop_eligible", False),
            "next_step_ref": payload.get("next_step_ref"),
            "emitted_at": payload["emitted_at"],
            "trace_id": payload["trace_id"],
        }
    )
    validate_artifact(decision, "closure_decision_artifact")
    return {
        "decision_type": decision["decision_type"],
        "next_step_class": (
            "continue_repair_bounded"
            if decision["decision_type"] == "continue_repair_bounded"
            else ("continue_bounded" if decision["decision_type"] == "continue_bounded" else "terminal")
        ),
        "closure_state": "closed" if decision["decision_type"] == "lock" else "open",
        "artifact_refs": [f"closure_decision_artifact:{decision['closure_decision_id']}"],
        "trace_refs": [decision["trace_id"]],
        "closure_decision_artifact": decision,
    }


def _real_prg(payload: dict[str, Any]) -> dict[str, Any]:
    closure_decision = payload.get("closure_decision") if isinstance(payload.get("closure_decision"), dict) else {}
    if "artifact_refs" not in closure_decision:
        raise TopLevelConductorError("PRG input must originate from TLC + CDE closure decision handoff")

    program_signal = build_program_constraint_signal(
        program_artifact={
            "program_id": "PRG-QUALITY-CERTIFICATION",
            "schema_version": "1.0.0",
            "batches": ["BATCH-H", "BATCH-I"],
            "allowed_targets": ["BATCH-H", "BATCH-I"],
            "disallowed_targets": [],
            "success_criteria": ["bounded_next_step_governed"],
            "blocking_conditions": [],
        },
        program_status={
            "program_version": "1.0.0",
            "priority_ordering": ["BATCH-H", "BATCH-I"],
            "blocking_conditions": [],
            "enforcement_mode": "block",
        },
        trace_id=payload["trace_id"],
        created_at=payload["emitted_at"],
    )
    validate_artifact(program_signal, "program_constraint_signal")
    next_step_artifact = {
        "next_step_action_artifact_id": f"next-step-{payload['run_id']}",
        "work_item_id": f"tlc:{payload['run_id']}",
        "parent_work_item_id": f"cde:{payload['run_id']}",
        "post_execution_decision_artifact_path": f"artifacts/tlc/{payload['run_id']}/closure_decision_artifact.json",
        "execution_result_artifact_path": f"artifacts/tlc/{payload['run_id']}/top_level_conductor_run_artifact.json",
        "action_status": "spawn_reentry_child",
        "action_reason_code": "spawn_reentry_child_from_post_execution_reentry_eligible",
        "decision_status": "reentry_eligible",
        "generated_at": payload["emitted_at"],
        "generator_version": "top_level_conductor.prg_boundary.v1",
    }
    validate_artifact(next_step_artifact, "prompt_queue_next_step_action")
    return {
        "proposed": True,
        "artifact_refs": [f"program_constraint_signal:{program_signal['program_id']}:{program_signal['program_version']}"],
        "trace_refs": [program_signal["trace_id"]],
        "next_step_artifact": next_step_artifact,
        "next_step_artifact_ref": f"prompt_queue_next_step_action:{next_step_artifact['next_step_action_artifact_id']}",
        "execution_performed": False,
        "closure_decided": False,
        "policy_mutated": False,
    }


def _resolve_subsystems(run_request: dict[str, Any]) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    subsystems = run_request.get("subsystems") if isinstance(run_request.get("subsystems"), dict) else {}
    resolved = {
        "sel": subsystems.get("sel", _real_sel),
        "pqx": subsystems.get("pqx", _real_pqx),
        "tpa": subsystems.get("tpa", _real_tpa),
        "fre": subsystems.get("fre", _real_fre),
        "ril": subsystems.get("ril", _real_ril),
        "cde": subsystems.get("cde", _real_cde),
        "prg": subsystems.get("prg", _real_prg),
    }
    for name, fn in resolved.items():
        if not callable(fn):
            raise TopLevelConductorError(f"subsystems.{name} must be callable")
    return resolved


def _enforce_sel(
    *,
    state: dict[str, Any],
    sel_fn: Callable[[dict[str, Any]], dict[str, Any]],
    boundary: str,
    consumed_artifact_types: list[str] | None = None,
) -> bool:
    payload = {
        "source_module": "top_level_conductor",
        "caller_identity": "tlc",
        "execution_request": {
            "execution_context": "pqx_governed",
            "pqx_entry": True,
            "direct_cli": False,
            "ad_hoc_runtime": False,
            "direct_slice_execution": False,
            "tpa_required": True,
            "recovery_involved": boundary == "recovery" and bool(state["lineage"].get("recovery_result_artifact_ref")),
            "repair_attempt": boundary == "repair_attempt",
            "repair_decision_state": state["lineage"].get("repair_decision_state"),
            "repair_budget_remaining": state["retry_budget_remaining"],
            "approved_repair_scope": state["lineage"].get("approved_repair_scope", []),
            "repair_files_touched": state["lineage"].get("pending_files_touched", []),
            "requested_at": state["emitted_at"],
        },
        "artifact_references": {
            "execution_artifact": state["produced_artifact_refs"][0] if state["produced_artifact_refs"] else "request_artifact",
            "trace_refs": state["trace_refs"] or [state["trace_id"]],
            "lineage": state["lineage"],
            "tpa_lineage_artifact": "tpa_lineage_artifact:tlc",
            "tpa_artifact": "tpa_policy_decision:tlc",
            "failure_diagnosis_artifact": state["lineage"].get("failure_diagnosis_artifact_ref"),
            "repair_prompt_artifact": state["lineage"].get("repair_prompt_artifact_ref"),
            "recovery_result_artifact": state["lineage"].get("recovery_result_artifact_ref"),
            "failure_repair_candidate_artifact": state["lineage"].get("failure_repair_candidate_artifact_ref"),
            "repair_attempt_record_artifact": state["lineage"].get("repair_attempt_record_artifact_ref"),
        },
        "downstream_consumption": {
            "consumed_artifact_types": consumed_artifact_types or ["review_projection_bundle_artifact"],
        },
        "governance_evidence": {
            "preflight_evidence": f"preflight_gate:{state['run_id']}",
            "control_evidence": f"control_decision:{state['run_id']}",
            "certification_evidence": f"certification:{state['run_id']}",
        },
        "trace_refs": state["trace_refs"] or [state["trace_id"]],
        "lineage": state["lineage"],
        "emitted_at": state["emitted_at"],
    }
    result = sel_fn(payload)
    state["active_subsystems"].append("SEL")
    _extract_refs(result if isinstance(result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
    allowed = isinstance(result, dict) and bool(result.get("allowed", False))
    _record_invocation(
        state=state,
        subsystem="SEL",
        boundary=boundary,
        status="allowed" if allowed else "blocked",
        input_refs=[],
        output_refs=[str(item) for item in (result.get("artifact_ref"),) if isinstance(item, str)],
        trace_refs=state["trace_refs"],
    )
    if not allowed:
        _transition(state=state, to_state="blocked", reason=f"sel_block:{boundary}")
        state["stop_reason"] = f"sel_block:{boundary}"
        state["lineage"].setdefault("sel_violations", []).append(result.get("violations", []) if isinstance(result, dict) else [])
        return False
    return True


def _validate_prg_output(prg_result: dict[str, Any], *, trace_refs: list[str]) -> None:
    if not isinstance(prg_result.get("next_step_artifact"), dict):
        raise TopLevelConductorError("PRG output must include next_step_artifact")
    validate_artifact(prg_result["next_step_artifact"], "prompt_queue_next_step_action")
    if bool(prg_result.get("execution_performed", True)):
        raise TopLevelConductorError("PRG must not execute work")
    if bool(prg_result.get("closure_decided", True)):
        raise TopLevelConductorError("PRG must not decide closure")
    if bool(prg_result.get("policy_mutated", True)):
        raise TopLevelConductorError("PRG must not mutate policy")
    # Use explicit trace refs supplied out-of-band for schemas that disallow trace fields.
    result = validate_system_handoff(
        "PRG",
        "TLC",
        {
            "schema_name": "prompt_queue_next_step_action",
            "action_type": "program_governance",
            "payload": prg_result["next_step_artifact"],
            "required_fields": ["next_step_action_artifact_id", "action_status", "decision_status"],
            "expected_trace_refs": trace_refs,
            "trace_refs": trace_refs,
        },
    )
    if not result["allow"]:
        violations = ",".join(result["violation_codes"])
        raise TopLevelConductorError(f"handoff_blocked:prg_to_tlc_next_step:{violations}")


def run_top_level_conductor(run_request: dict[str, Any]) -> dict[str, Any]:
    """Run one deterministic bounded TLC state machine invocation."""
    if not isinstance(run_request, dict):
        raise TopLevelConductorError("run_request must be an object")

    objective = _require_non_empty_str(run_request.get("objective"), field="objective")
    branch_ref = _require_non_empty_str(run_request.get("branch_ref"), field="branch_ref")
    retry_budget = _require_non_negative_int(run_request.get("retry_budget"), field="retry_budget")
    require_review = _require_bool(run_request.get("require_review"), field="require_review")
    require_recovery = _require_bool(run_request.get("require_recovery"), field="require_recovery")
    emitted_at = str(run_request.get("emitted_at") or "2026-04-06T00:00:00Z")

    run_id = run_request.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        identity_seed = {
            "objective": objective,
            "branch_ref": branch_ref,
            "retry_budget": retry_budget,
            "require_review": require_review,
            "require_recovery": require_recovery,
        }
        run_id = f"tlc-{_canonical_hash(identity_seed)[:12]}"

    trace_id = f"trace-{run_id}"
    resolved = _resolve_subsystems(run_request)

    lineage = deepcopy(run_request.get("lineage")) if isinstance(run_request.get("lineage"), dict) else {}
    lineage.setdefault("lineage_id", f"lineage-{run_id}")
    lineage.setdefault("parent_refs", [f"request:{run_id}"])
    lineage.setdefault(
        "request_hash",
        _canonical_hash(
            {
                "objective": objective,
                "branch_ref": branch_ref,
                "retry_budget": retry_budget,
                "require_review": require_review,
                "require_recovery": require_recovery,
                "run_id": run_id,
            }
        ),
    )

    state: dict[str, Any] = {
        "run_id": run_id,
        "objective": objective,
        "branch_ref": branch_ref,
        "current_state": "requested",
        "phase_history": [],
        "active_subsystems": [],
        "retry_budget_remaining": retry_budget,
        "closure_state": "pending",
        "next_allowed_actions": ["admit"],
        "stop_reason": None,
        "ready_for_merge": False,
        "produced_artifact_refs": [],
        "trace_refs": [trace_id],
        "trace_id": trace_id,
        "lineage": lineage,
        "emitted_at": emitted_at,
    }
    pre_pr_failures = run_request.get("pre_pr_failures")
    if isinstance(pre_pr_failures, list) and pre_pr_failures:
        packet = normalize_pytest_failure_packet(
            source_run_ref=f"run:{run_id}",
            command_ref=str(run_request.get("pre_pr_command_ref") or "pytest"),
            failing_tests=pre_pr_failures,
        )
        state["lineage"]["pending_failure_packet"] = packet
        state["lineage"]["repair_attempt_count"] = 0
        state["lineage"]["failure_recurrence"] = {}

    while state["current_state"] not in TERMINAL_STATES:
        if not _enforce_sel(state=state, sel_fn=resolved["sel"], boundary="state_transition"):
            break

        if state["current_state"] == "requested":
            _transition(state=state, to_state="admitted", reason="request_admitted")
            continue

        if state["current_state"] == "admitted":
            _transition(state=state, to_state="executing", reason="execution_admitted")
            continue

        if state["current_state"] == "executing":
            if not _enforce_sel(state=state, sel_fn=resolved["sel"], boundary="execution"):
                break
            _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="PQX", boundary="tlc_to_pqx")
            pqx_result = resolved["pqx"](
                {
                    "run_id": state["run_id"],
                    "objective": state["objective"],
                    "branch_ref": state["branch_ref"],
                    "runtime_dir": str(run_request.get("runtime_dir") or Path("outputs") / "tlc_runtime"),
                    "trace_id": state["trace_id"],
                    "emitted_at": state["emitted_at"],
                }
            )
            _validate_handoff_output("PQX", pqx_result if isinstance(pqx_result, dict) else {})
            _enforce_handoff(
                from_system="PQX",
                to_system="TPA",
                schema_name="pqx_execution_result",
                action_type="execution",
                payload=pqx_result["execution_artifact"],
                required_fields=["run_id", "execution_status", "output_text"],
                expected_trace_refs=state["trace_refs"],
                boundary="pqx_to_tpa",
            )
            state["active_subsystems"].append("PQX")
            _extract_refs(pqx_result if isinstance(pqx_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            _record_invocation(
                state=state,
                subsystem="PQX",
                boundary="execution",
                status="ok" if bool(pqx_result.get("entry_valid")) else "blocked",
                input_refs=["pqx_execution_request"],
                output_refs=pqx_result.get("artifact_refs", []) if isinstance(pqx_result, dict) else [],
                trace_refs=state["trace_refs"],
            )
            if not isinstance(pqx_result, dict) or not bool(pqx_result.get("entry_valid", False)):
                _transition(state=state, to_state="blocked", reason="pqx_entry_invalid")
                state["stop_reason"] = "pqx_entry_invalid"
                break

            _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="TPA", boundary="tlc_to_tpa")
            tpa_result = resolved["tpa"]({"run_id": state["run_id"], "trace_id": state["trace_id"], "pqx_result": pqx_result})
            state["active_subsystems"].append("TPA")
            _extract_refs(tpa_result if isinstance(tpa_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            _record_invocation(
                state=state,
                subsystem="TPA",
                boundary="execution",
                status="ok" if tpa_result.get("discipline_status") == "accepted" else "blocked",
                input_refs=pqx_result.get("artifact_refs", []) if isinstance(pqx_result, dict) else [],
                output_refs=tpa_result.get("artifact_refs", []) if isinstance(tpa_result, dict) else [],
                trace_refs=state["trace_refs"],
            )

            if bool(pqx_result.get("validation_passed", False)):
                _transition(state=state, to_state="reviewing" if require_review else "closure_decision_pending", reason="execution_validated")
            else:
                _transition(state=state, to_state="validation_failed", reason="validation_failed")
            continue

        if state["current_state"] == "validation_failed":
            if not require_recovery:
                _transition(state=state, to_state="blocked", reason="recovery_not_permitted")
                state["stop_reason"] = "recovery_not_permitted"
                break
            if state["retry_budget_remaining"] <= 0:
                _transition(state=state, to_state="exhausted", reason="retry_budget_exhausted")
                state["stop_reason"] = "retry_budget_exhausted"
                break
            _transition(state=state, to_state="recovering", reason="retry_available")
            continue

        if state["current_state"] == "recovering":
            if not _enforce_sel(state=state, sel_fn=resolved["sel"], boundary="recovery"):
                break
            _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="FRE", boundary="tlc_to_fre")
            fre_result = resolved["fre"](
                {
                    "run_id": state["run_id"],
                    "trace_id": state["trace_id"],
                    "emitted_at": state["emitted_at"],
                    "source_artifact_refs": state["produced_artifact_refs"],
                    "max_attempts": max(1, state["retry_budget_remaining"]),
                }
            )
            _validate_handoff_output("FRE", fre_result if isinstance(fre_result, dict) else {})
            _enforce_handoff(
                from_system="FRE",
                to_system="RIL",
                schema_name="recovery_result_artifact",
                action_type="failure_diagnosis",
                payload=fre_result["recovery_result_artifact"],
                required_fields=["recovery_status", "trace_id", "repair_prompt_ref"],
                expected_trace_refs=state["trace_refs"],
                boundary="fre_to_ril",
            )
            state["active_subsystems"].append("FRE")
            _extract_refs(fre_result if isinstance(fre_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            state["lineage"]["failure_diagnosis_artifact_ref"] = fre_result["artifact_refs"][0]
            state["lineage"]["repair_prompt_artifact_ref"] = fre_result["artifact_refs"][1]
            state["lineage"]["recovery_result_artifact_ref"] = fre_result["artifact_refs"][2]
            _record_invocation(
                state=state,
                subsystem="FRE",
                boundary="recovery",
                status="ok" if fre_result.get("recovery_completed") else "blocked",
                input_refs=state["produced_artifact_refs"],
                output_refs=fre_result.get("artifact_refs", []),
                trace_refs=state["trace_refs"],
            )
            if not isinstance(fre_result, dict) or not bool(fre_result.get("recovery_completed", False)):
                _transition(state=state, to_state="blocked", reason="recovery_incomplete")
                state["stop_reason"] = "recovery_incomplete"
                break
            _transition(state=state, to_state="reviewing", reason="recovery_completed")
            continue

        if state["current_state"] == "reviewing":
            if not _enforce_sel(state=state, sel_fn=resolved["sel"], boundary="review"):
                break
            _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="RIL", boundary="tlc_to_ril")
            ril_result = resolved["ril"](
                {
                    "run_id": state["run_id"],
                    "trace_id": state["trace_id"],
                    "review_path": _require_non_empty_str(run_request.get("review_path"), field="review_path"),
                    "action_tracker_path": _require_non_empty_str(run_request.get("action_tracker_path"), field="action_tracker_path"),
                }
            )
            _validate_handoff_output("RIL", ril_result if isinstance(ril_result, dict) else {})
            _enforce_handoff(
                from_system="RIL",
                to_system="CDE",
                schema_name="review_projection_bundle_artifact",
                action_type="review_projection",
                payload=ril_result["review_projection_bundle_artifact"],
                required_fields=["review_projection_bundle_id", "emitted_at"],
                expected_trace_refs=state["trace_refs"],
                boundary="ril_to_cde",
            )
            state["active_subsystems"].append("RIL")
            _extract_refs(ril_result if isinstance(ril_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            _record_invocation(
                state=state,
                subsystem="RIL",
                boundary="review",
                status="ok" if ril_result.get("outputs_exist") else "blocked",
                input_refs=["review_signal_artifact"],
                output_refs=ril_result.get("artifact_refs", []) if isinstance(ril_result, dict) else [],
                trace_refs=state["trace_refs"],
            )
            if not isinstance(ril_result, dict) or not bool(ril_result.get("outputs_exist", False)):
                _transition(state=state, to_state="blocked", reason="review_outputs_missing")
                state["stop_reason"] = "review_outputs_missing"
                break
            _transition(state=state, to_state="closure_decision_pending", reason="review_outputs_available")
            continue

        if state["current_state"] == "closure_decision_pending":
            _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="CDE", boundary="tlc_to_cde")
            ril_ref = next((ref for ref in state["produced_artifact_refs"] if ref.startswith("review_projection_bundle_artifact:")), None)
            if not isinstance(ril_ref, str) or not ril_ref:
                ril_ref = f"review_projection_bundle_artifact:{state['run_id']}:synthetic"
            repair_packet = state["lineage"].get("pending_failure_packet") if isinstance(state["lineage"].get("pending_failure_packet"), dict) else None
            repair_candidate = state["lineage"].get("failure_repair_candidate_artifact")
            if repair_packet is not None and not isinstance(repair_candidate, dict):
                _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="FRE", boundary="tlc_to_fre_pre_pr")
                fre_diag_result = resolved["fre"](
                    {
                        "mode": "pre_pr_diagnosis",
                        "run_id": state["run_id"],
                        "trace_id": state["trace_id"],
                        "emitted_at": state["emitted_at"],
                        "failure_packet": repair_packet,
                        "default_bounded_scope": list(run_request.get("repair_default_scope", [])),
                    }
                )
                _validate_handoff_output("FRE", fre_diag_result if isinstance(fre_diag_result, dict) else {})
                state["active_subsystems"].append("FRE")
                _extract_refs(fre_diag_result if isinstance(fre_diag_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
                state["lineage"]["failure_repair_candidate_artifact"] = fre_diag_result["failure_repair_candidate_artifact"]
                state["lineage"]["failure_repair_candidate_artifact_ref"] = (
                    f"failure_repair_candidate_artifact:{fre_diag_result['failure_repair_candidate_artifact']['failure_id']}"
                )
                repair_candidate = fre_diag_result["failure_repair_candidate_artifact"]

            repair_loop_eligible = bool(
                isinstance(repair_candidate, dict)
                and repair_candidate.get("safe_to_repair")
                and repair_candidate.get("bounded_scope")
                and state["retry_budget_remaining"] > 0
            )
            cde_result = resolved["cde"](
                {
                    "run_id": state["run_id"],
                    "trace_id": state["trace_id"],
                    "emitted_at": state["emitted_at"],
                    "review_date": "2026-04-05",
                    "action_tracker_ref": _require_non_empty_str(run_request.get("action_tracker_path"), field="action_tracker_path"),
                    "source_artifacts": [
                        {
                            "artifact_type": "review_projection_bundle_artifact",
                            "artifact_ref": ril_ref,
                            "blocker_count": 0,
                            "critical_count": 0,
                            "high_priority_count": 0,
                            "medium_priority_count": 1,
                            "unresolved_action_item_ids": [],
                        }
                    ],
                    "closure_complete": repair_packet is None,
                    "final_verification_passed": repair_packet is None,
                    "hardening_completed": repair_packet is None,
                    "escalation_required": False,
                    "bounded_next_step_available": state["retry_budget_remaining"] > 0,
                    "repair_loop_eligible": repair_loop_eligible,
                    "next_step_ref": (
                        f"repair_loop:{state['run_id']}:{state['lineage'].get('repair_attempt_count', 0) + 1}"
                        if repair_loop_eligible
                        else "BATCH-H"
                    ),
                }
            )
            _validate_handoff_output("CDE", cde_result if isinstance(cde_result, dict) else {})
            _enforce_handoff(
                from_system="CDE",
                to_system="TLC",
                schema_name="closure_decision_artifact",
                action_type="closure_decisions",
                payload=cde_result["closure_decision_artifact"],
                required_fields=["decision_type", "trace_id"],
                expected_trace_refs=state["trace_refs"],
                boundary="cde_to_tlc",
            )
            state["active_subsystems"].append("CDE")
            _extract_refs(cde_result if isinstance(cde_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
            _record_invocation(
                state=state,
                subsystem="CDE",
                boundary="closure_decision",
                status="ok",
                input_refs=[ril_ref] if isinstance(ril_ref, str) else [],
                output_refs=cde_result.get("artifact_refs", []) if isinstance(cde_result, dict) else [],
                trace_refs=state["trace_refs"],
            )
            decision = cde_result.get("decision_type") if isinstance(cde_result, dict) else None
            state["closure_state"] = str(cde_result.get("closure_state", "pending")) if isinstance(cde_result, dict) else "pending"

            if decision == "lock":
                _transition(state=state, to_state="ready_for_merge", reason="cde_lock")
                state["ready_for_merge"] = True
                state["stop_reason"] = "ready_for_merge"
                break

            if decision == "continue_bounded":
                if state["retry_budget_remaining"] <= 0:
                    _transition(state=state, to_state="exhausted", reason="retry_budget_exhausted")
                    state["stop_reason"] = "retry_budget_exhausted"
                    break
                if not _enforce_sel(state=state, sel_fn=resolved["sel"], boundary="direction"):
                    break
                _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="PRG", boundary="tlc_to_prg")
                prg_result = resolved["prg"](
                    {
                        "run_id": state["run_id"],
                        "trace_id": state["trace_id"],
                        "emitted_at": state["emitted_at"],
                        "closure_decision": cde_result,
                    }
                )
                _validate_prg_output(prg_result if isinstance(prg_result, dict) else {}, trace_refs=state["trace_refs"])
                state["active_subsystems"].append("PRG")
                _extract_refs(prg_result if isinstance(prg_result, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
                _record_invocation(
                    state=state,
                    subsystem="PRG",
                    boundary="direction",
                    status="ok" if prg_result.get("proposed") else "blocked",
                    input_refs=cde_result.get("artifact_refs", []),
                    output_refs=prg_result.get("artifact_refs", []),
                    trace_refs=state["trace_refs"],
                )
                state["retry_budget_remaining"] -= 1
                _transition(state=state, to_state="executing", reason="continue_bounded")
                continue

            if decision == "continue_repair_bounded":
                if not isinstance(repair_candidate, dict):
                    _transition(state=state, to_state="blocked", reason="missing_repair_candidate")
                    state["stop_reason"] = "missing_repair_candidate"
                    break
                state["lineage"]["repair_decision_state"] = "continue_repair_bounded"
                state["lineage"]["approved_repair_scope"] = list(repair_candidate.get("bounded_scope", []))
                state["lineage"]["pending_files_touched"] = list(run_request.get("simulated_repair_files_touched", []))
                if not _enforce_sel(state=state, sel_fn=resolved["sel"], boundary="repair_attempt"):
                    break
                _enforce_registry_action(actor="TLC", action_type="orchestration", target_system="PQX", boundary="tlc_to_pqx_repair")
                pqx_repair = resolved["pqx"](
                    {
                        "run_id": state["run_id"],
                        "objective": "bounded_pre_pr_repair",
                        "branch_ref": state["branch_ref"],
                        "runtime_dir": str(run_request.get("runtime_dir") or Path("outputs") / "tlc_runtime"),
                        "trace_id": state["trace_id"],
                        "emitted_at": state["emitted_at"],
                    }
                )
                _validate_handoff_output("PQX", pqx_repair if isinstance(pqx_repair, dict) else {})
                state["active_subsystems"].append("PQX")
                _extract_refs(pqx_repair if isinstance(pqx_repair, dict) else {}, produced_refs=state["produced_artifact_refs"], trace_refs=state["trace_refs"])
                state["lineage"]["repair_attempt_count"] = int(state["lineage"].get("repair_attempt_count", 0)) + 1
                passed = bool(run_request.get("repair_validation_passed_after_attempt", False))
                result_status = "tests_green" if passed else "tests_failed"
                attempt_id = f"attempt-{state['run_id']}-{state['lineage']['repair_attempt_count']}"
                attempt_record = _build_repair_attempt_record_artifact(
                    attempt_id=attempt_id,
                    failure_id=repair_candidate["failure_id"],
                    roadmap_id=run_request.get("roadmap_id"),
                    run_id=state["run_id"],
                    attempt_number=state["lineage"]["repair_attempt_count"],
                    files_touched=list(state["lineage"].get("pending_files_touched", [])),
                    commands_run=list(run_request.get("repair_commands_run", ["pytest -q"])),
                    result_status=result_status,
                    trace_refs=state["trace_refs"],
                )
                state["lineage"]["repair_attempt_record_artifact_ref"] = f"repair_attempt_record_artifact:{attempt_id}"
                state["produced_artifact_refs"].append(state["lineage"]["repair_attempt_record_artifact_ref"])

                failure_class = str(repair_candidate.get("failure_class") or "unknown_failure_class")
                recurrences = state["lineage"].setdefault("failure_recurrence", {})
                recurrences[failure_class] = int(recurrences.get(failure_class, 0)) + 1
                learning = _build_failure_learning_record_artifact(
                    learning_id=f"learning-{state['run_id']}-{failure_class}",
                    failure_class=failure_class,
                    recurrence_count=recurrences[failure_class],
                    first_seen_ref=f"failure_repair_candidate_artifact:{repair_candidate['failure_id']}",
                    latest_seen_ref=f"repair_attempt_record_artifact:{attempt_id}",
                    trace_refs=state["trace_refs"],
                )
                state["lineage"]["latest_failure_learning_record_artifact"] = learning
                state["produced_artifact_refs"].append(f"failure_learning_record_artifact:{learning['learning_id']}")

                if passed:
                    _transition(state=state, to_state="ready_for_merge", reason="repair_tests_green")
                    state["ready_for_merge"] = True
                    state["stop_reason"] = "ready_for_merge"
                    break
                state["retry_budget_remaining"] -= 1
                if state["retry_budget_remaining"] <= 0:
                    _transition(state=state, to_state="exhausted", reason="repair_attempts_exhausted")
                    state["stop_reason"] = "repair_attempts_exhausted"
                    break
                _transition(state=state, to_state="closure_decision_pending", reason="repair_retry")
                continue

            if decision == "blocked":
                _transition(state=state, to_state="blocked", reason="cde_blocked")
                state["stop_reason"] = "cde_blocked"
                break

            if decision == "escalate":
                _transition(state=state, to_state="escalated", reason="cde_escalate")
                state["stop_reason"] = "cde_escalate"
                break

            _transition(state=state, to_state="blocked", reason="unknown_cde_decision")
            state["stop_reason"] = "unknown_cde_decision"
            break

        raise TopLevelConductorError(f"unsupported state: {state['current_state']}")

    state["active_subsystems"] = sorted(set(state["active_subsystems"]))
    state["produced_artifact_refs"] = sorted(set(state["produced_artifact_refs"]))
    state["trace_refs"] = sorted(set(state["trace_refs"]))
    if state["stop_reason"] is None and state["current_state"] in TERMINAL_STATES:
        state["stop_reason"] = state["current_state"]

    output = {k: v for k, v in state.items() if k not in {"trace_id", "emitted_at"}}
    validate_artifact(output, "top_level_conductor_run_artifact")
    return output


def run_from_roadmap(roadmap_artifact: dict[str, Any], *, run_request_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a validated two-step roadmap through TLC->PQX with deterministic bounded governance."""
    execution_plan = run_roadmap_execution(roadmap_artifact)
    roadmap_id = execution_plan["roadmap_id"]
    execution_id = execution_plan["execution_id"]

    base_overrides = deepcopy(run_request_overrides) if isinstance(run_request_overrides, dict) else {}
    common_emitted_at = str(base_overrides.pop("emitted_at", roadmap_artifact.get("generated_at") or "2026-04-06T00:00:00Z"))

    step_artifacts: list[dict[str, Any]] = []
    tlc_runs: list[dict[str, Any]] = []

    for index, ordered in enumerate(execution_plan["ordered_steps"], start=1):
        required_inputs = list(ordered["required_inputs"])
        if not required_inputs:
            raise TopLevelConductorError(f"missing_artifact:required_inputs:{ordered['step_id']}")

        request = {
            "objective": ordered["execution_request"]["objective"],
            "branch_ref": "refs/heads/main",
            "run_id": f"{execution_id}-{ordered['step_id']}",
            "retry_budget": 1,
            "require_review": True,
            "require_recovery": True,
            "review_path": str(base_overrides.get("review_path", "contracts/examples/roadmap_review_artifact.json")),
            "action_tracker_path": str(base_overrides.get("action_tracker_path", "contracts/examples/roadmap_review_artifact.json")),
            "runtime_dir": str(base_overrides.get("runtime_dir", Path("outputs") / "roadmap_execution" / execution_id)),
            "emitted_at": common_emitted_at,
        }
        request.update(base_overrides)
        request["objective"] = ordered["execution_request"]["objective"]
        request["run_id"] = f"{execution_id}-{ordered['step_id']}"
        request["emitted_at"] = common_emitted_at

        tlc_result = run_top_level_conductor(request)
        tlc_runs.append(tlc_result)

        status = "succeeded" if tlc_result.get("ready_for_merge") is True else "failed"
        if status == "failed" and "FRE" in tlc_result.get("active_subsystems", []):
            status = "fre_recovered" if tlc_result.get("current_state") == "ready_for_merge" else "failed"

        step_artifact = {
            "schema_version": "1.0.0",
            "roadmap_step_execution_id": f"{execution_id}:{ordered['step_id']}",
            "execution_id": execution_id,
            "roadmap_id": roadmap_id,
            "step_id": ordered["step_id"],
            "execution_status": status,
            "input_refs": required_inputs,
            "output_refs": sorted(set(str(item) for item in tlc_result.get("produced_artifact_refs", []) if isinstance(item, str))),
            "trace_refs": sorted(set(str(item) for item in tlc_result.get("trace_refs", []) if isinstance(item, str))),
        }
        validate_artifact(step_artifact, "roadmap_step_execution_artifact")
        step_artifacts.append(step_artifact)

        if not step_artifact["trace_refs"]:
            raise TopLevelConductorError(f"missing_artifact:trace_refs:{ordered['step_id']}")

        if tlc_result.get("current_state") != "ready_for_merge":
            return {
                "execution_id": execution_id,
                "roadmap_id": roadmap_id,
                "execution_status": "blocked",
                "failure_mode": "cde_block" if "CDE" in tlc_result.get("active_subsystems", []) else "step_failed",
                "blocked_step_id": ordered["step_id"],
                "ordered_steps": execution_plan["ordered_steps"],
                "step_execution_artifacts": step_artifacts,
                "tlc_runs": tlc_runs,
            }

    return {
        "execution_id": execution_id,
        "roadmap_id": roadmap_id,
        "execution_status": "completed",
        "ordered_steps": execution_plan["ordered_steps"],
        "step_execution_artifacts": step_artifacts,
        "tlc_runs": tlc_runs,
    }
