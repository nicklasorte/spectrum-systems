#!/usr/bin/env python3
"""Thin CLI for spawning governed repair child work items from repair prompt artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    RepairChildQueueIntegrationError,
    spawn_repair_child_in_queue,
    validate_queue_state,
    validate_work_item,
    write_artifact,
)
from spectrum_systems.modules.prompt_queue.repair_prompt_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spawn governed prompt queue repair child work item")
    parser.add_argument("--parent-work-item-id", required=True)
    parser.add_argument("--repair-prompt-artifact-path", required=True)
    parser.add_argument("--queue-state-path", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    queue_state_path = Path(args.queue_state_path)
    repair_prompt_artifact_path = Path(args.repair_prompt_artifact_path)

    queue_state = read_json_artifact(queue_state_path)
    repair_prompt_artifact = read_json_artifact(repair_prompt_artifact_path)

    try:
        updated_queue, updated_parent, child = spawn_repair_child_in_queue(
            queue_state=queue_state,
            parent_work_item_id=args.parent_work_item_id,
            repair_prompt_artifact=repair_prompt_artifact,
            repair_prompt_artifact_path=str(repair_prompt_artifact_path),
        )
    except RepairChildQueueIntegrationError as exc:
        print(json.dumps({"error": str(exc), "parent_work_item_id": args.parent_work_item_id}, indent=2), file=sys.stderr)
        return 2

    validate_work_item(updated_parent)
    validate_work_item(child)
    validate_queue_state(updated_queue)

    write_artifact(updated_queue, queue_state_path)
    parent_path = queue_state_path.parent / f"{updated_parent['work_item_id']}.work_item.json"
    child_path = queue_state_path.parent / f"{child['work_item_id']}.work_item.json"
    write_artifact(updated_parent, parent_path)
    write_artifact(child, child_path)

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "parent_work_item_path": str(parent_path),
                "child_work_item_path": str(child_path),
                "child_work_item_id": child["work_item_id"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
