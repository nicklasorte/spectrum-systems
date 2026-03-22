#!/usr/bin/env python3
"""Thin CLI for governed prompt queue post-execution policy decision and queue update."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    PostExecutionPolicyConfig,
    PostExecutionQueueIntegrationError,
    apply_post_execution_decision_to_queue,
    default_post_execution_decision_path,
    evaluate_post_execution_policy,
    validate_queue_state,
    validate_work_item,
    write_artifact,
    write_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate governed post-execution policy for an executed work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--max-generation-allowed", type=int, default=2)
    return parser.parse_args(argv)


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"work item '{work_item_id}' not found")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    queue_state_path = Path(args.queue_state_path)
    queue_state = read_json_artifact(queue_state_path)

    try:
        work_item = _find_work_item(queue_state, args.work_item_id)
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    if work_item.get("status") not in {"executed_success", "executed_failure"}:
        print(
            json.dumps(
                {"error": "work item must be in executed_success or executed_failure", "work_item_id": args.work_item_id},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    execution_result_path = work_item.get("execution_result_artifact_path")
    gating_decision_path = work_item.get("gating_decision_artifact_path")

    if not execution_result_path:
        print(json.dumps({"error": "missing execution_result_artifact_path", "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    if not gating_decision_path:
        print(json.dumps({"error": "missing gating_decision_artifact_path", "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    execution_result_artifact = read_json_artifact(Path(execution_result_path))
    gating_decision_artifact = read_json_artifact(Path(gating_decision_path))

    decision = evaluate_post_execution_policy(
        work_item=work_item,
        execution_result_artifact=execution_result_artifact,
        execution_result_artifact_path=execution_result_path,
        gating_decision_artifact=gating_decision_artifact,
        gating_decision_artifact_path=gating_decision_path,
        source_queue_state_path=str(queue_state_path),
        policy=PostExecutionPolicyConfig(max_generation_allowed=args.max_generation_allowed),
    )

    decision_path = default_post_execution_decision_path(args.work_item_id, queue_state_path)
    write_post_execution_decision_artifact(decision, decision_path)

    try:
        updated_queue, updated_item = apply_post_execution_decision_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            post_execution_decision_artifact=decision,
            post_execution_decision_artifact_path=str(decision_path),
        )
    except PostExecutionQueueIntegrationError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    validate_work_item(updated_item)
    validate_queue_state(updated_queue)
    write_artifact(updated_queue, queue_state_path)
    updated_item_path = queue_state_path.parent / f"{updated_item['work_item_id']}.work_item.json"
    write_artifact(updated_item, updated_item_path)

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "work_item_path": str(updated_item_path),
                "post_execution_decision_artifact_path": str(decision_path),
                "work_item_id": args.work_item_id,
                "decision_status": decision["decision_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
