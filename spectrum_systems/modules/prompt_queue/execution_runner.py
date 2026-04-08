"""Pure deterministic controlled execution runner for governed prompt queue work items."""

from __future__ import annotations

import re

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_queue_state, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.runtime.permission_governance import (
    PermissionGovernanceError,
    require_checkpoint_decision,
)
from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_system_boundaries


class ExecutionRunnerError(ValueError):
    """Raised when controlled execution runner fails closed."""


_STEP_ID_PATTERN = re.compile(r"^step-[0-9]{3}$")
_SUPPORTED_EXECUTION_MODES = {"simulated"}


def _validate_step_shape(step: dict) -> dict:
    if not isinstance(step, dict):
        raise ExecutionRunnerError("Queue step must be an object.")

    step_id = step.get("step_id")
    if not isinstance(step_id, str) or not _STEP_ID_PATTERN.fullmatch(step_id):
        raise ExecutionRunnerError("Queue step is missing a valid step_id.")

    work_item_id = step.get("work_item_id")
    if not isinstance(work_item_id, str) or not work_item_id:
        raise ExecutionRunnerError("Queue step is missing work_item_id.")

    execution_mode = step.get("execution_mode", "simulated")
    if execution_mode not in _SUPPORTED_EXECUTION_MODES:
        raise ExecutionRunnerError(f"Unknown execution shape: unsupported execution_mode '{execution_mode}'.")

    return {
        "step_id": step_id,
        "work_item_id": work_item_id,
        "execution_mode": execution_mode,
    }


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for work_item in queue_state.get("work_items", []):
        if work_item.get("work_item_id") == work_item_id:
            return dict(work_item)
    raise ExecutionRunnerError(f"Work item '{work_item_id}' not found in queue state.")


def _normalize_input_refs(input_refs: dict | None) -> dict:
    refs = {} if input_refs is None else input_refs
    if not isinstance(refs, dict):
        raise ExecutionRunnerError("Malformed input_refs: expected object.")

    allowed = {
        "permission_request_record",
        "permission_decision_record",
        "human_checkpoint_request",
        "human_checkpoint_decision",
        "pqx_execution_authority_record",
        "source_queue_state_path",
    }
    extra = set(refs) - allowed
    if extra:
        unknown = ", ".join(sorted(extra))
        raise ExecutionRunnerError(f"Unknown execution shape: unsupported input_refs keys: {unknown}.")

    permission_decision_record = refs.get("permission_decision_record")
    if not isinstance(permission_decision_record, dict):
        raise ExecutionRunnerError("Malformed input_refs: permission_decision_record is required and must be an object.")

    permission_request_record = refs.get("permission_request_record")
    if not isinstance(permission_request_record, dict):
        raise ExecutionRunnerError("Malformed input_refs: permission_request_record is required and must be an object.")

    checkpoint_request = refs.get("human_checkpoint_request")
    if checkpoint_request is not None and not isinstance(checkpoint_request, dict):
        raise ExecutionRunnerError("Malformed input_refs: human_checkpoint_request must be an object when provided.")

    checkpoint_decision = refs.get("human_checkpoint_decision")
    if checkpoint_decision is not None and not isinstance(checkpoint_decision, dict):
        raise ExecutionRunnerError("Malformed input_refs: human_checkpoint_decision must be an object when provided.")

    pqx_proof = refs.get("pqx_execution_authority_record")
    if not isinstance(pqx_proof, dict):
        raise ExecutionRunnerError("Malformed input_refs: pqx_execution_authority_record is required and must be an object.")

    source_queue_state_path = refs.get("source_queue_state_path")
    if source_queue_state_path is not None and (not isinstance(source_queue_state_path, str) or not source_queue_state_path):
        raise ExecutionRunnerError("Malformed input_refs: source_queue_state_path must be a non-empty string when provided.")

    return {
        "permission_request_record": dict(permission_request_record),
        "permission_decision_record": dict(permission_decision_record),
        "human_checkpoint_request": None if checkpoint_request is None else dict(checkpoint_request),
        "human_checkpoint_decision": None if checkpoint_decision is None else dict(checkpoint_decision),
        "pqx_execution_authority_record": dict(pqx_proof),
        "source_queue_state_path": source_queue_state_path,
    }


def revalidate_execution_entry(
    *,
    work_item: dict,
    permission_decision_record: dict,
    human_checkpoint_decision: dict | None,
) -> None:
    if work_item.get("status") != WorkItemStatus.RUNNABLE.value:
        raise ExecutionRunnerError("Execution entry requires work item status 'runnable'.")

    try:
        validate_work_item(work_item)
    except ArtifactValidationError as exc:
        raise ExecutionRunnerError(str(exc)) from exc

    try:
        validate_artifact(permission_decision_record, "permission_decision_record")
    except Exception as exc:
        raise ExecutionRunnerError(str(exc)) from exc

    provenance = permission_decision_record.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("producer") != "permission_governance":
        raise ExecutionRunnerError("Permission decision artifact provenance must be produced by permission_governance.")

    trace = permission_decision_record.get("trace")
    trace_refs = [] if not isinstance(trace, dict) else trace.get("trace_refs", [])
    if not isinstance(trace_refs, list):
        raise ExecutionRunnerError("Permission decision trace_refs must be a list.")
    work_item_trace_ref = f"work_item_id:{work_item.get('work_item_id')}"
    if work_item_trace_ref not in trace_refs:
        raise ExecutionRunnerError("Permission decision trace provenance does not match target work item.")

    decision = permission_decision_record.get("decision")
    if decision != "allow":
        if decision == "require_human_approval":
            try:
                require_checkpoint_decision(
                    permission_decision_record=permission_decision_record,
                    human_checkpoint_decision=human_checkpoint_decision,
                )
            except PermissionGovernanceError as exc:
                raise ExecutionRunnerError(str(exc)) from exc
        else:
            raise ExecutionRunnerError("Permission decision must allow execution at execution entry.")


def run_queue_step_execution(
    *,
    step: dict,
    queue_state: dict,
    input_refs: dict | None = None,
    clock=utc_now,
) -> dict:
    """Run one queue step through a normalized execution adapter boundary.

    This adapter validates step and queue inputs fail-closed, calls existing runner seams
    (`revalidate_execution_entry` and `run_simulated_execution`), and emits a deterministic
    normalized execution result artifact shape.
    """

    step_view = _validate_step_shape(step)
    refs = _normalize_input_refs(input_refs)

    try:
        validate_queue_state(queue_state)
    except ArtifactValidationError as exc:
        raise ExecutionRunnerError(str(exc)) from exc

    work_item = _find_work_item(queue_state, step_view["work_item_id"])
    revalidate_execution_entry(
        work_item=work_item,
        permission_decision_record=refs["permission_decision_record"],
        human_checkpoint_decision=refs["human_checkpoint_decision"],
    )
    sel_result = enforce_system_boundaries(
        {
            "source_module": "spectrum_systems.modules.prompt_queue.execution_runner",
            "caller_identity": "run_queue_step_execution",
            "execution_request": {
                "execution_context": "pqx_governed",
                "pqx_entry": True,
                "direct_cli": False,
                "ad_hoc_runtime": False,
                "direct_slice_execution": False,
                "tpa_required": False,
                "recovery_involved": False,
                "certification_required": False,
            },
            "artifact_references": {
                "execution_artifact": f"permission_decision_record:{refs['permission_decision_record'].get('decision_id')}",
                "trace_refs": refs["permission_decision_record"]["trace"]["trace_refs"],
                "lineage": {
                    "lineage_id": f"queue:{queue_state['queue_id']}:step:{step_view['step_id']}",
                    "parent_refs": [
                        f"permission_request_record:{refs['permission_request_record'].get('request_id')}",
                        f"permission_decision_record:{refs['permission_decision_record'].get('decision_id')}",
                    ],
                },
                "pqx_execution_authority_record": refs["pqx_execution_authority_record"],
            },
            "trace_refs": refs["permission_decision_record"]["trace"]["trace_refs"],
            "lineage": {
                "lineage_id": f"queue:{queue_state['queue_id']}:step:{step_view['step_id']}",
                "parent_refs": [
                    f"permission_request_record:{refs['permission_request_record'].get('request_id')}",
                    f"permission_decision_record:{refs['permission_decision_record'].get('decision_id')}",
                ],
            },
            "governance_evidence": {
                "preflight_evidence": f"permission_request_record:{refs['permission_request_record'].get('request_id')}",
                "control_evidence": f"permission_decision_record:{refs['permission_decision_record'].get('decision_id')}",
            },
            "downstream_consumption": {"consumed_artifact_types": ["review_projection_bundle_artifact"]},
        }
    )
    if sel_result.get("enforcement_status") != "allow":
        raise ExecutionRunnerError("SEL blocked execution due to authority boundary violations.")
    runner_result = run_simulated_execution(
        work_item=work_item,
        source_queue_state_path=refs["source_queue_state_path"],
        clock=clock,
    )

    output_reference = runner_result.get("output_reference")
    produced_refs = [] if output_reference is None else [output_reference]
    normalized = dict(runner_result)
    normalized.update(
        {
            "step_id": step_view["step_id"],
            "queue_id": queue_state["queue_id"],
            "trace_linkage": queue_state.get("queue_id"),
            "execution_type": "queue_step",
            "produced_artifact_refs": produced_refs,
        }
    )
    return normalized


def run_simulated_execution(*, work_item: dict, source_queue_state_path: str | None, clock=utc_now) -> dict:
    start = iso_now(clock)

    has_lineage = all(
        [
            work_item.get("repair_prompt_artifact_path") or work_item.get("spawned_from_repair_prompt_artifact_path"),
            work_item.get("gating_decision_artifact_path"),
            work_item.get("spawned_from_findings_artifact_path"),
            work_item.get("spawned_from_review_artifact_path"),
        ]
    )

    if has_lineage:
        execution_status = "success"
        output_reference = f"artifacts/prompt_queue/simulated_outputs/{work_item['work_item_id']}.output.json"
        error_summary = None
    else:
        execution_status = "failure"
        output_reference = None
        error_summary = "Missing required lineage for controlled simulated execution."

    completed = iso_now(clock)
    execution_attempt_id = f"{work_item['work_item_id']}-attempt-1"

    produced_artifact_refs = [] if output_reference is None else [output_reference]

    return {
        "execution_result_artifact_id": f"execres-{execution_attempt_id}",
        "execution_attempt_id": execution_attempt_id,
        "step_id": None,
        "queue_id": None,
        "trace_linkage": work_item.get("work_item_id"),
        "execution_type": "queue_step",
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "repair_prompt_artifact_path": work_item.get("repair_prompt_artifact_path")
        or work_item.get("spawned_from_repair_prompt_artifact_path"),
        "gating_decision_artifact_path": work_item.get("gating_decision_artifact_path"),
        "spawned_from_findings_artifact_path": work_item.get("spawned_from_findings_artifact_path"),
        "spawned_from_review_artifact_path": work_item.get("spawned_from_review_artifact_path"),
        "execution_mode": "simulated",
        "execution_status": execution_status,
        "started_at": start,
        "completed_at": completed,
        "output_reference": output_reference,
        "produced_artifact_refs": produced_artifact_refs,
        "error_summary": error_summary,
        "source_queue_state_path": source_queue_state_path,
        "generated_at": completed,
        "generator_version": "prompt-queue-execution-mvp-1",
    }
