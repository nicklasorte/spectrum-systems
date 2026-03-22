#!/usr/bin/env python3
"""Thin CLI for governed prompt queue loop continuation from reentry-generated repair prompts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    LoopContinuationArtifactIOError,
    LoopContinuationError,
    LoopContinuationQueueIntegrationError,
    apply_loop_continuation_to_queue,
    default_loop_continuation_path,
    run_loop_continuation,
    validate_queue_state,
    write_artifact,
    write_loop_continuation_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed prompt queue loop continuation for one work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    return parser.parse_args(argv)


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"Work item '{work_item_id}' not found.")


def _load_required_artifact(repo_root: Path, path: str, *, label: str) -> dict:
    if not path:
        raise ValueError(f"Work item missing {label}.")
    artifact_path = repo_root / path
    if not artifact_path.exists() or not artifact_path.is_file():
        raise ValueError(f"Missing {label}: {path}")
    return read_json_artifact(artifact_path)


def _load_optional_artifact(repo_root: Path, path: str | None) -> dict | None:
    if not path:
        return None
    artifact_path = repo_root / path
    if not artifact_path.exists() or not artifact_path.is_file():
        raise ValueError(f"Missing loop_control_decision_artifact_path: {path}")
    return read_json_artifact(artifact_path)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root)
    queue_state_path = Path(args.queue_state_path)
    queue_state = read_json_artifact(queue_state_path)
    validate_queue_state(queue_state)

    try:
        work_item = _find_work_item(queue_state, args.work_item_id)

        findings_reentry_path = work_item.get("findings_reentry_artifact_path")
        repair_prompt_path = work_item.get("repair_prompt_artifact_path")
        loop_control_path = work_item.get("loop_control_decision_artifact_path")

        findings_reentry_artifact = _load_required_artifact(
            repo_root,
            findings_reentry_path,
            label="findings_reentry_artifact_path",
        )
        repair_prompt_artifact = _load_required_artifact(
            repo_root,
            repair_prompt_path,
            label="repair_prompt_artifact_path",
        )
        loop_control_artifact = _load_optional_artifact(repo_root, loop_control_path)

        continuation_result = run_loop_continuation(
            queue_state=queue_state,
            work_item=work_item,
            findings_reentry_artifact=findings_reentry_artifact,
            findings_reentry_artifact_path=findings_reentry_path,
            repair_prompt_artifact=repair_prompt_artifact,
            repair_prompt_artifact_path=repair_prompt_path,
            loop_control_decision_artifact=loop_control_artifact,
            loop_control_decision_artifact_path=loop_control_path,
            source_queue_state_path=str(queue_state_path),
        )

        continuation_path = default_loop_continuation_path(work_item_id=args.work_item_id, root_dir=repo_root)
        continuation_rel_path = str(continuation_path.relative_to(repo_root))
        write_loop_continuation_artifact(
            artifact=continuation_result["loop_continuation_artifact"],
            output_path=continuation_path,
        )

        updated_queue, updated_item = apply_loop_continuation_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            loop_continuation_artifact=continuation_result["loop_continuation_artifact"],
            loop_continuation_artifact_path=continuation_rel_path,
            updated_queue_state=continuation_result["updated_queue_state"],
            spawned_child_work_item=continuation_result["spawned_child_work_item"],
        )

        write_artifact(updated_queue, queue_state_path)
    except (
        ValueError,
        LoopContinuationError,
        LoopContinuationArtifactIOError,
        LoopContinuationQueueIntegrationError,
    ) as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    payload = {
        "queue_state_path": str(queue_state_path),
        "work_item_id": updated_item["work_item_id"],
        "loop_continuation_artifact_path": continuation_rel_path,
        "continuation_status": continuation_result["loop_continuation_artifact"]["continuation_status"],
        "spawned_child_work_item_id": continuation_result["loop_continuation_artifact"]["spawned_child_work_item_id"],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
