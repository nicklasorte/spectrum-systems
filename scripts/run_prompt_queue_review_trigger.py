#!/usr/bin/env python3
"""Thin CLI for deterministic prompt queue automatic review triggering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ReviewTriggerPolicyConfig,
    ReviewTriggerQueueIntegrationError,
    apply_review_trigger_to_queue,
    default_review_trigger_path,
    evaluate_review_trigger_policy,
    validate_queue_state,
    validate_work_item,
    write_artifact,
    write_review_trigger_artifact,
)
from spectrum_systems.modules.prompt_queue.review_trigger_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed prompt queue automatic review trigger for one work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
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

    post_execution_decision_path = work_item.get("post_execution_decision_artifact_path")
    execution_result_artifact_path = work_item.get("execution_result_artifact_path")
    loop_control_decision_artifact_path = work_item.get("loop_control_decision_artifact_path")

    if not post_execution_decision_path:
        print(
            json.dumps({"error": "missing post_execution_decision_artifact_path", "work_item_id": args.work_item_id}, indent=2),
            file=sys.stderr,
        )
        return 2
    if not execution_result_artifact_path:
        print(
            json.dumps({"error": "missing execution_result_artifact_path", "work_item_id": args.work_item_id}, indent=2),
            file=sys.stderr,
        )
        return 2

    try:
        post_execution_decision_artifact = read_json_artifact(Path(post_execution_decision_path))
    except FileNotFoundError:
        print(
            json.dumps(
                {"error": f"post_execution_decision artifact not found at {post_execution_decision_path}", "work_item_id": args.work_item_id},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    loop_control_decision_artifact = None
    if loop_control_decision_artifact_path:
        try:
            loop_control_decision_artifact = read_json_artifact(Path(loop_control_decision_artifact_path))
        except FileNotFoundError:
            print(
                json.dumps(
                    {"error": f"loop_control_decision artifact not found at {loop_control_decision_artifact_path}", "work_item_id": args.work_item_id},
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2

    review_trigger = evaluate_review_trigger_policy(
        work_item=work_item,
        post_execution_decision_artifact=post_execution_decision_artifact,
        post_execution_decision_artifact_path=post_execution_decision_path,
        loop_control_decision_artifact=loop_control_decision_artifact,
        loop_control_decision_artifact_path=loop_control_decision_artifact_path,
        execution_result_artifact_path=execution_result_artifact_path,
        source_queue_state_path=str(queue_state_path),
        config=ReviewTriggerPolicyConfig(),
    )

    review_trigger_path = default_review_trigger_path(args.work_item_id, queue_state_path)

    try:
        updated_queue, updated_item, spawned_child, finalized_trigger = apply_review_trigger_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            review_trigger_artifact=review_trigger,
            review_trigger_artifact_path=str(review_trigger_path),
        )
        write_review_trigger_artifact(finalized_trigger, review_trigger_path)
    except ReviewTriggerQueueIntegrationError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    validate_work_item(updated_item)
    if spawned_child is not None:
        validate_work_item(spawned_child)
    validate_queue_state(updated_queue)

    write_artifact(updated_queue, queue_state_path)
    updated_item_path = queue_state_path.parent / f"{updated_item['work_item_id']}.work_item.json"
    write_artifact(updated_item, updated_item_path)

    spawned_child_path: str | None = None
    if spawned_child is not None:
        spawned_child_path = str(queue_state_path.parent / f"{spawned_child['work_item_id']}.work_item.json")
        write_artifact(spawned_child, Path(spawned_child_path))

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "work_item_path": str(updated_item_path),
                "review_trigger_artifact_path": str(review_trigger_path),
                "spawned_review_work_item_path": spawned_child_path,
                "work_item_id": args.work_item_id,
                "trigger_status": finalized_trigger["trigger_status"],
                "spawned_review_work_item_id": finalized_trigger.get("spawned_review_work_item_id"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
