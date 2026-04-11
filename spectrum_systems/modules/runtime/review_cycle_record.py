"""Runtime lifecycle support for review_cycle_record artifacts."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewCycleRecordError(ValueError):
    """Raised when review-cycle lifecycle operations violate fail-closed rules."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_cycle(record: dict[str, Any]) -> None:
    try:
        validate_artifact(record, "review_cycle_record")
    except Exception as exc:  # pragma: no cover - wrapper
        raise ReviewCycleRecordError(f"invalid review_cycle_record: {exc}") from exc


def _next_unique(existing: list[str], new_ref: str) -> list[str]:
    if new_ref in existing:
        return list(existing)
    return [*existing, new_ref]


def create_review_cycle(
    *,
    parent_batch_id: str,
    parent_umbrella_id: str,
    max_iterations: int,
    review_request_ref: str,
    lineage: list[str],
    created_at: str | None = None,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    if not parent_batch_id:
        raise ReviewCycleRecordError("parent_batch_id is required")
    if not parent_umbrella_id:
        raise ReviewCycleRecordError("parent_umbrella_id is required")
    if max_iterations < 1:
        raise ReviewCycleRecordError("max_iterations must be >= 1")
    if not review_request_ref:
        raise ReviewCycleRecordError("review_request_ref is required")
    if not lineage:
        raise ReviewCycleRecordError("lineage must include at least one ref")

    now = created_at or _utc_now_iso()
    resolved_cycle_id = cycle_id or deterministic_id(
        prefix="rcy",
        namespace="review_cycle_record",
        payload=[parent_batch_id, parent_umbrella_id, review_request_ref, max_iterations, lineage],
    )
    record = {
        "artifact_type": "review_cycle_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "cycle_id": resolved_cycle_id,
        "parent_batch_id": parent_batch_id,
        "parent_umbrella_id": parent_umbrella_id,
        "iteration_number": 1,
        "max_iterations": max_iterations,
        "termination_state": "open",
        "status": "active",
        "review_request_ref": review_request_ref,
        "review_result_refs": [],
        "fix_slice_refs": [],
        "replay_result_refs": [],
        "lineage": list(lineage),
        "created_at": now,
        "updated_at": now,
    }
    _validate_cycle(record)
    return record


def advance_review_cycle(record: dict[str, Any], *, updated_at: str | None = None) -> dict[str, Any]:
    if record.get("status") != "active":
        raise ReviewCycleRecordError("cannot advance terminated review cycle")
    next_iteration = int(record["iteration_number"]) + 1
    if next_iteration > int(record["max_iterations"]):
        raise ReviewCycleRecordError("cannot advance beyond max_iterations")

    advanced = deepcopy(record)
    advanced["iteration_number"] = next_iteration
    advanced["updated_at"] = updated_at or _utc_now_iso()
    _validate_cycle(advanced)
    return advanced


def attach_review_result(record: dict[str, Any], *, review_result_ref: str, updated_at: str | None = None) -> dict[str, Any]:
    if record.get("status") != "active":
        raise ReviewCycleRecordError("cannot attach review_result_ref to terminated review cycle")
    if not review_result_ref:
        raise ReviewCycleRecordError("review_result_ref is required")

    updated = deepcopy(record)
    updated["review_result_refs"] = _next_unique(list(record["review_result_refs"]), review_result_ref)
    updated["updated_at"] = updated_at or _utc_now_iso()
    _validate_cycle(updated)
    return updated


def attach_fix_slice(record: dict[str, Any], *, fix_slice_ref: str, updated_at: str | None = None) -> dict[str, Any]:
    if record.get("status") != "active":
        raise ReviewCycleRecordError("cannot attach fix_slice_ref to terminated review cycle")
    if not fix_slice_ref:
        raise ReviewCycleRecordError("fix_slice_ref is required")

    updated = deepcopy(record)
    updated["fix_slice_refs"] = _next_unique(list(record["fix_slice_refs"]), fix_slice_ref)
    updated["updated_at"] = updated_at or _utc_now_iso()
    _validate_cycle(updated)
    return updated


def attach_replay_result(record: dict[str, Any], *, replay_result_ref: str, updated_at: str | None = None) -> dict[str, Any]:
    if record.get("status") != "active":
        raise ReviewCycleRecordError("cannot attach replay_result_ref to terminated review cycle")
    if not replay_result_ref:
        raise ReviewCycleRecordError("replay_result_ref is required")

    updated = deepcopy(record)
    updated["replay_result_refs"] = _next_unique(list(record["replay_result_refs"]), replay_result_ref)
    updated["updated_at"] = updated_at or _utc_now_iso()
    _validate_cycle(updated)
    return updated


def terminate_review_cycle(
    record: dict[str, Any],
    *,
    termination_state: str,
    status: str,
    updated_at: str | None = None,
) -> dict[str, Any]:
    if record.get("status") != "active":
        raise ReviewCycleRecordError("review cycle already terminated")

    terminated = deepcopy(record)
    terminated["termination_state"] = termination_state
    terminated["status"] = status
    terminated["updated_at"] = updated_at or _utc_now_iso()
    _validate_cycle(terminated)
    return terminated
