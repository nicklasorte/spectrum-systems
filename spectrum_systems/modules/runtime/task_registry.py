"""Governed AI task registry helpers."""

from __future__ import annotations

from typing import Any


def resolve_task_spec(*, registry: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in registry.get("tasks", []):
        if task.get("task_id") == task_id:
            return dict(task)
    raise ValueError(f"unknown task_id: {task_id}")
