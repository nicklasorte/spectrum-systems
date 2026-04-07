"""Roadmap execution adapter: deterministic conversion of roadmap_two_step_artifact to governed TLC execution requests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from spectrum_systems.contracts import validate_artifact


class RoadmapExecutionAdapterError(ValueError):
    """Raised when a roadmap artifact cannot be safely converted to execution requests."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_roadmap_execution(roadmap_artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate and deterministically convert a two-step roadmap artifact into ordered execution requests."""
    if not isinstance(roadmap_artifact, dict):
        raise RoadmapExecutionAdapterError("roadmap_artifact must be an object")

    validate_artifact(roadmap_artifact, "roadmap_two_step_artifact")

    step_count = roadmap_artifact.get("step_count")
    if not isinstance(step_count, int):
        raise RoadmapExecutionAdapterError("roadmap_artifact.step_count must be an integer")
    if step_count > 2:
        raise RoadmapExecutionAdapterError("bounded_enforcement_violation:step_count_exceeds_2")

    steps = roadmap_artifact.get("steps")
    if not isinstance(steps, list) or len(steps) != step_count:
        raise RoadmapExecutionAdapterError("roadmap_artifact.steps must match step_count")

    roadmap_id = roadmap_artifact.get("roadmap_id")
    if not isinstance(roadmap_id, str) or not roadmap_id.strip():
        raise RoadmapExecutionAdapterError("roadmap_artifact.roadmap_id must be a non-empty string")

    ordered_steps: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise RoadmapExecutionAdapterError(f"steps[{index-1}] must be an object")

        step_id = step.get("step_id")
        required_inputs = step.get("required_inputs")
        expected_outputs = step.get("expected_outputs")
        description = step.get("description")

        if not isinstance(step_id, str) or not step_id.strip():
            raise RoadmapExecutionAdapterError(f"steps[{index-1}].step_id must be non-empty string")
        if not isinstance(description, str) or not description.strip():
            raise RoadmapExecutionAdapterError(f"steps[{index-1}].description must be non-empty string")
        if not isinstance(required_inputs, list) or not required_inputs:
            raise RoadmapExecutionAdapterError(f"steps[{index-1}].required_inputs must be non-empty list")
        if not isinstance(expected_outputs, list) or not expected_outputs:
            raise RoadmapExecutionAdapterError(f"steps[{index-1}].expected_outputs must be non-empty list")

        normalized_inputs = [str(item).strip() for item in required_inputs if isinstance(item, str) and item.strip()]
        normalized_outputs = [str(item).strip() for item in expected_outputs if isinstance(item, str) and item.strip()]
        if len(normalized_inputs) != len(required_inputs):
            raise RoadmapExecutionAdapterError(f"steps[{index-1}].required_inputs contains invalid refs")
        if len(normalized_outputs) != len(expected_outputs):
            raise RoadmapExecutionAdapterError(f"steps[{index-1}].expected_outputs contains invalid refs")

        execution_request = {
            "execution_request_id": f"{roadmap_id}:{step_id}:request",
            "roadmap_id": roadmap_id,
            "step_id": step_id,
            "order_index": index,
            "objective": description.strip(),
            "required_inputs": normalized_inputs,
            "expected_outputs": normalized_outputs,
        }
        ordered_steps.append(
            {
                "step_id": step_id,
                "required_inputs": normalized_inputs,
                "expected_outputs": normalized_outputs,
                "execution_request": execution_request,
            }
        )

    execution_seed = {
        "roadmap_id": roadmap_id,
        "steps": [
            {
                "step_id": row["step_id"],
                "required_inputs": row["required_inputs"],
                "expected_outputs": row["expected_outputs"],
            }
            for row in ordered_steps
        ],
    }
    execution_id = f"R2E-{_canonical_hash(execution_seed)[:16].upper()}"

    return {
        "execution_id": execution_id,
        "roadmap_id": roadmap_id,
        "ordered_steps": deepcopy(ordered_steps),
    }
