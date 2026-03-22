"""Deterministic work-item update logic for attaching repair prompt artifacts."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus
from spectrum_systems.modules.prompt_queue.queue_state_machine import transition_work_item


def attach_repair_prompt_to_work_item(work_item: dict, *, repair_prompt_artifact_path: str, clock) -> dict:
    updated = dict(work_item)
    updated["repair_prompt_artifact_path"] = repair_prompt_artifact_path
    if updated["status"] == WorkItemStatus.FINDINGS_PARSED.value:
        updated = transition_work_item(updated, WorkItemStatus.REPAIR_PROMPT_GENERATED.value, clock=clock)
    return updated
