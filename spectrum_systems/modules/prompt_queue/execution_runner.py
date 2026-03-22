"""Pure deterministic controlled execution runner for governed prompt queue work items."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import (
    ExecutionGatingArtifactValidationError,
    validate_execution_gating_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now


class ExecutionRunnerError(ValueError):
    """Raised when controlled execution runner fails closed."""


def revalidate_execution_entry(
    *,
    work_item: dict,
    gating_decision_artifact: dict,
) -> None:
    if work_item.get("status") != WorkItemStatus.RUNNABLE.value:
        raise ExecutionRunnerError("Execution entry requires work item status 'runnable'.")

    try:
        validate_work_item(work_item)
    except ArtifactValidationError as exc:
        raise ExecutionRunnerError(str(exc)) from exc

    gating_path = work_item.get("gating_decision_artifact_path")
    if not gating_path:
        raise ExecutionRunnerError("Missing gating_decision_artifact_path on work item.")

    try:
        validate_execution_gating_decision_artifact(gating_decision_artifact)
    except ExecutionGatingArtifactValidationError as exc:
        raise ExecutionRunnerError(str(exc)) from exc

    if gating_decision_artifact.get("work_item_id") != work_item.get("work_item_id"):
        raise ExecutionRunnerError("Gating artifact work_item_id does not match target work item.")

    if gating_decision_artifact.get("decision_status") != WorkItemStatus.RUNNABLE.value:
        raise ExecutionRunnerError("Gating decision must be runnable at execution entry.")


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

    return {
        "execution_result_artifact_id": f"execres-{execution_attempt_id}",
        "execution_attempt_id": execution_attempt_id,
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
        "error_summary": error_summary,
        "source_queue_state_path": source_queue_state_path,
        "generated_at": completed,
        "generator_version": "prompt-queue-execution-mvp-1",
    }
