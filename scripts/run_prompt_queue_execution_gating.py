#!/usr/bin/env python3
"""Thin CLI for governed prompt queue execution gating evaluation and queue update."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ExecutionGatingPolicyConfig,
    ExecutionGatingQueueIntegrationError,
    apply_execution_gating_decision_to_queue,
    default_execution_gating_decision_path,
    evaluate_execution_gating_policy,
    validate_queue_state,
    validate_work_item,
    write_artifact,
    write_execution_gating_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate governed execution gating for repair child work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--approval-present", action="store_true")
    parser.add_argument("--max-generation-allowed", type=int, default=2)
    parser.add_argument("--approval-required-risk-level", action="append", default=["high", "critical"])
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

    repair_prompt_path = work_item.get("spawned_from_repair_prompt_artifact_path")
    if not repair_prompt_path:
        print(
            json.dumps(
                {
                    "error": "work item missing spawned_from_repair_prompt_artifact_path",
                    "work_item_id": args.work_item_id,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    repair_prompt_artifact = read_json_artifact(Path(repair_prompt_path))

    policy = ExecutionGatingPolicyConfig(
        max_generation_allowed=args.max_generation_allowed,
        approval_required_risk_levels=tuple(args.approval_required_risk_level),
    )

    decision = evaluate_execution_gating_policy(
        work_item=work_item,
        repair_prompt_artifact=repair_prompt_artifact,
        repair_prompt_artifact_path=repair_prompt_path,
        approval_present=args.approval_present,
        source_queue_state_path=str(queue_state_path),
        policy=policy,
    )

    decision_path = default_execution_gating_decision_path(args.work_item_id, queue_state_path)
    write_execution_gating_decision_artifact(decision, decision_path)

    try:
        updated_queue, updated_item = apply_execution_gating_decision_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            gating_decision_artifact=decision,
            gating_decision_artifact_path=str(decision_path),
        )
    except ExecutionGatingQueueIntegrationError as exc:
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
                "gating_decision_artifact_path": str(decision_path),
                "work_item_id": args.work_item_id,
                "decision_status": decision["decision_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
