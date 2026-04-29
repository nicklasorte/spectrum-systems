"""LRT checkpoint record builder.

Extends HNX checkpoint semantics with long-running task slice fields.
The record is serializable, schema-validated, and trace-linked.
HNX retains canonical checkpoint/continuity authority; this module
produces the lrt_checkpoint_record artifact type only.
"""

from __future__ import annotations

from typing import Any

from spectrum_systems.contracts import validate_artifact

_ALLOWED_STATUSES = frozenset({"checkpointed", "resumed", "blocked"})


class LRTCheckpointError(ValueError):
    """Raised when checkpoint record construction fails validation."""


def build_lrt_checkpoint_record(
    *,
    checkpoint_id: str,
    trace_id: str,
    task_id: str,
    stage: str,
    files_changed: int,
    tests_added: int,
    commands_run: list[str],
    next_recommended_slice: str,
    resume_instructions: str,
    status: str,
) -> dict[str, Any]:
    """Build and validate an lrt_checkpoint_record artifact. Fail closed on invalid input."""
    if status not in _ALLOWED_STATUSES:
        raise LRTCheckpointError(f"status must be one of {sorted(_ALLOWED_STATUSES)}, got {status!r}")

    record: dict[str, Any] = {
        "artifact_type": "lrt_checkpoint_record",
        "schema_version": "1.0.0",
        "checkpoint_id": checkpoint_id,
        "trace_id": trace_id,
        "task_id": task_id,
        "stage": stage,
        "files_changed": files_changed,
        "tests_added": tests_added,
        "commands_run": list(commands_run),
        "next_recommended_slice": next_recommended_slice,
        "resume_instructions": resume_instructions,
        "status": status,
    }

    try:
        validate_artifact(record, "lrt_checkpoint_record")
    except Exception as exc:
        raise LRTCheckpointError(f"lrt_checkpoint_record schema validation failed: {exc}") from exc

    return record
