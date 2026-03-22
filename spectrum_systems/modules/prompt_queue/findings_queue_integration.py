"""Deterministic work-item update logic for attaching findings artifacts."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus
from spectrum_systems.modules.prompt_queue.queue_state_machine import transition_work_item


def attach_findings_to_work_item(work_item: dict, *, findings_artifact_path: str, clock) -> dict:
    updated = dict(work_item)
    updated["findings_artifact_path"] = findings_artifact_path
    if updated["status"] == WorkItemStatus.REVIEW_COMPLETE.value:
        updated = transition_work_item(updated, WorkItemStatus.FINDINGS_PARSED.value, clock=clock)
    return updated
