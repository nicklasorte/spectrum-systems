#!/usr/bin/env python3
"""Thin CLI for prompt queue loop control evaluation and deterministic queue update."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    LoopControlPolicyConfig,
    LoopControlPolicyError,
    LoopControlQueueIntegrationError,
    apply_loop_control_decision_to_queue,
    evaluate_loop_control_policy,
    validate_queue_state,
    validate_work_item,
    write_artifact,
    write_loop_control_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.loop_control_artifact_io import (  # noqa: E402
    default_loop_control_decision_path,
    read_json_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate governed prompt queue loop control")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--max-generation-allowed", type=int, default=2)
    return parser.parse_args(argv)


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"work item '{work_item_id}' not found")


def _resolve_parent(queue_state: dict, work_item: dict) -> dict | None:
    parent_id = work_item.get("parent_work_item_id")
    if parent_id is None:
        return None
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == parent_id:
            return item
    raise ValueError(f"parent work item '{parent_id}' not found")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    queue_state_path = Path(args.queue_state_path)
    queue_state = read_json_artifact(queue_state_path)

    try:
        work_item = _find_work_item(queue_state, args.work_item_id)
        parent = _resolve_parent(queue_state, work_item)
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    policy = LoopControlPolicyConfig(max_generation_allowed=args.max_generation_allowed)
    try:
        decision = evaluate_loop_control_policy(
            work_item=work_item,
            parent_work_item=parent,
            source_queue_state_path=str(queue_state_path),
            policy=policy,
        )
    except LoopControlPolicyError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    decision_path = default_loop_control_decision_path(args.work_item_id)
    write_loop_control_decision_artifact(decision, decision_path)

    try:
        updated_queue, updated_item = apply_loop_control_decision_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            loop_control_decision_artifact=decision,
            loop_control_decision_artifact_path=str(decision_path),
        )
    except LoopControlQueueIntegrationError as exc:
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
                "loop_control_decision_artifact_path": str(decision_path),
                "work_item_id": args.work_item_id,
                "loop_control_status": decision["loop_control_status"],
                "enforcement_action": decision["enforcement_action"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
