#!/usr/bin/env python3
"""Thin CLI for deterministic prompt queue retry policy and queue mutation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    RetryPolicyConfig,
    RetryPolicyError,
    RetryQueueIntegrationError,
    apply_retry_decision_to_queue,
    default_retry_decision_path,
    evaluate_retry_policy,
    validate_queue_state,
    validate_work_item,
    write_artifact,
    write_retry_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.retry_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate prompt queue retry policy and apply deterministic retry action")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--failure-reason-code", required=True)
    return parser.parse_args(argv)


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"work item '{work_item_id}' not found")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    queue_state_path = Path(args.queue_state_path)

    try:
        queue_state = read_json_artifact(queue_state_path)
    except Exception as exc:
        print(json.dumps({"error": f"failed to load queue state: {exc}"}, indent=2), file=sys.stderr)
        return 2

    try:
        work_item = _find_work_item(queue_state, args.work_item_id)
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    try:
        decision = evaluate_retry_policy(
            work_item=work_item,
            failure_reason_code=args.failure_reason_code,
            source_queue_state_path=str(queue_state_path),
            config=RetryPolicyConfig(),
        )
    except RetryPolicyError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    decision_path = default_retry_decision_path(work_item_id=args.work_item_id, root_dir=REPO_ROOT)

    try:
        write_retry_decision_artifact(artifact=decision, output_path=decision_path)
    except Exception as exc:
        print(json.dumps({"error": f"artifact write failed: {exc}", "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    try:
        updated_queue, updated_item = apply_retry_decision_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            retry_decision_artifact=decision,
            retry_decision_artifact_path=str(decision_path),
        )
    except RetryQueueIntegrationError as exc:
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
                "retry_decision_artifact_path": str(decision_path),
                "work_item_id": args.work_item_id,
                "retry_status": decision["retry_status"],
                "retry_action": decision["retry_action"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
