"""Pure deterministic loop control policy for governed prompt queue repair cycles."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.loop_control_artifact_io import validate_loop_control_decision_artifact
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class LoopControlPolicyError(ValueError):
    """Raised when loop control cannot be evaluated safely."""


@dataclass(frozen=True)
class LoopControlPolicyConfig:
    max_generation_allowed: int = 2
    generator_version: str = "prompt_queue_loop_control_policy.v1"


_CANONICAL_DECISIONS = {
    "within_budget": {
        "enforcement_action": "allow_reentry",
        "reason_code": "within_budget_allow_reentry",
    },
    "limit_reached": {
        "enforcement_action": "require_review",
        "reason_code": "limit_reached_require_review",
    },
    "limit_exceeded": {
        "enforcement_action": "block_reentry",
        "reason_code": "limit_exceeded_block_reentry",
    },
}


def _parse_generation_count(work_item: dict) -> int:
    if "generation_count" not in work_item:
        raise LoopControlPolicyError("generation_count is required for loop control.")
    try:
        generation_count = int(work_item["generation_count"])
    except (TypeError, ValueError) as exc:
        raise LoopControlPolicyError("generation_count must be an integer.") from exc
    if generation_count < 0:
        raise LoopControlPolicyError("generation_count must be >= 0.")
    return generation_count


def _validate_lineage(work_item: dict, parent_work_item: dict | None, generation_count: int) -> None:
    parent_id = work_item.get("parent_work_item_id")

    if generation_count == 0:
        if parent_id is not None:
            raise LoopControlPolicyError("Root work items (generation_count=0) must not declare parent_work_item_id.")
        if parent_work_item is not None:
            raise LoopControlPolicyError("Root work items must not include lineage parent payload.")
        return

    if not parent_id:
        raise LoopControlPolicyError("Non-root work items must include parent_work_item_id.")
    if parent_work_item is None:
        raise LoopControlPolicyError("Non-root work items require lineage parent payload.")
    if parent_work_item.get("work_item_id") != parent_id:
        raise LoopControlPolicyError("Parent lineage mismatch: parent_work_item_id does not match lineage payload.")

    parent_generation = _parse_generation_count(parent_work_item)
    if generation_count != parent_generation + 1:
        raise LoopControlPolicyError("Non-monotonic generation_count detected between parent and child work item.")


def _derive_status(generation_count: int, max_generation_allowed: int) -> str:
    if generation_count < max_generation_allowed:
        return "within_budget"
    if generation_count == max_generation_allowed:
        return "limit_reached"
    return "limit_exceeded"


def evaluate_loop_control_policy(
    *,
    work_item: dict,
    parent_work_item: dict | None,
    source_queue_state_path: str | None,
    policy: LoopControlPolicyConfig = LoopControlPolicyConfig(),
    clock=utc_now,
) -> dict:
    if policy.max_generation_allowed < 0:
        raise LoopControlPolicyError("max_generation_allowed must be >= 0.")

    try:
        validate_work_item(work_item)
        if parent_work_item is not None:
            validate_work_item(parent_work_item)
    except ArtifactValidationError as exc:
        raise LoopControlPolicyError(f"Invalid work item schema input: {exc}") from exc

    generation_count = _parse_generation_count(work_item)
    _validate_lineage(work_item, parent_work_item, generation_count)

    status = _derive_status(generation_count, policy.max_generation_allowed)
    decision = _CANONICAL_DECISIONS[status]
    generated_at = iso_now(clock)

    artifact = {
        "loop_control_decision_artifact_id": f"loop-control-{work_item['work_item_id']}-{generated_at}",
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "generation_count": generation_count,
        "max_generation_allowed": policy.max_generation_allowed,
        "loop_control_status": status,
        "enforcement_action": decision["enforcement_action"],
        "reason_code": decision["reason_code"],
        "generated_at": generated_at,
        "generator_version": policy.generator_version,
        "source_queue_state_path": source_queue_state_path,
        "warnings": [],
    }
    validate_loop_control_decision_artifact(artifact)
    return artifact
