"""Pure child repair work-item construction from validated repair prompt artifacts."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, make_work_item, utc_now
from spectrum_systems.modules.prompt_queue.repair_prompt_artifact_io import (
    RepairPromptArtifactValidationError,
    validate_repair_prompt_artifact,
)


class RepairChildCreationError(ValueError):
    """Raised when governed repair child creation cannot proceed safely."""


def _derive_repair_generation(parent_work_item: dict) -> int:
    parent_generation = int(parent_work_item.get("repair_loop_generation") or 0)
    return parent_generation + 1


def _derive_generation_count(parent_work_item: dict) -> int:
    if "generation_count" not in parent_work_item:
        raise RepairChildCreationError("Parent work item missing required generation_count.")
    try:
        parent_generation = int(parent_work_item["generation_count"])
    except (TypeError, ValueError) as exc:
        raise RepairChildCreationError("Parent work item generation_count must be an integer.") from exc
    if parent_generation < 0:
        raise RepairChildCreationError("Parent work item generation_count must be >= 0.")
    return parent_generation + 1


def _derive_child_prompt_id(parent_work_item: dict, generation: int) -> str:
    return f"{parent_work_item['prompt_id']}:repair:{generation}"


def _derive_child_title(parent_work_item: dict, generation: int) -> str:
    return f"{parent_work_item['title']} [repair {generation}]"


def _validate_spawn_preconditions(parent_work_item: dict, repair_prompt_artifact: dict) -> None:
    try:
        validate_repair_prompt_artifact(repair_prompt_artifact)
    except RepairPromptArtifactValidationError as exc:
        raise RepairChildCreationError(f"Malformed repair prompt artifact: {exc}") from exc

    if repair_prompt_artifact.get("work_item_id") != parent_work_item.get("work_item_id"):
        raise RepairChildCreationError(
            "Repair prompt artifact work_item_id does not match parent work item."
        )

    if repair_prompt_artifact.get("review_decision") != "FAIL":
        raise RepairChildCreationError("Only FAIL-derived repair prompt artifacts can spawn child work items.")

    if repair_prompt_artifact.get("prompt_generation_status") != "generated":
        raise RepairChildCreationError(
            "Repair prompt artifact prompt_generation_status must be 'generated' to spawn a child."
        )

    if parent_work_item.get("status") != WorkItemStatus.REPAIR_PROMPT_GENERATED.value:
        raise RepairChildCreationError(
            "Parent work item must be in 'repair_prompt_generated' state before child creation."
        )


def build_repair_child_work_item(
    *,
    parent_work_item: dict,
    repair_prompt_artifact: dict,
    repair_prompt_artifact_path: str,
    clock=utc_now,
) -> dict:
    """Build a deterministic child work item with explicit parent→review→findings→repair lineage."""

    _validate_spawn_preconditions(parent_work_item, repair_prompt_artifact)

    generation_count = _derive_generation_count(parent_work_item)
    generation = _derive_repair_generation(parent_work_item)
    child_work_item = make_work_item(
        work_item_id=f"{parent_work_item['work_item_id']}.repair.{generation}",
        prompt_id=_derive_child_prompt_id(parent_work_item, generation),
        title=_derive_child_title(parent_work_item, generation),
        priority=parent_work_item["priority"],
        risk_level=parent_work_item["risk_level"],
        repo=parent_work_item["repo"],
        branch=parent_work_item["branch"],
        scope_paths=parent_work_item["scope_paths"],
        parent_work_item_id=parent_work_item["work_item_id"],
        clock=clock,
    )

    now = iso_now(clock)
    child_work_item.update(
        {
            "spawned_from_repair_prompt_artifact_path": repair_prompt_artifact_path,
            "spawned_from_findings_artifact_path": repair_prompt_artifact["source_findings_artifact_path"],
            "spawned_from_review_artifact_path": repair_prompt_artifact["source_review_artifact_path"],
            "generation_count": generation_count,
            "repair_loop_generation": generation,
            "child_work_item_ids": [],
            "updated_at": now,
        }
    )

    validate_work_item(child_work_item)
    return child_work_item
