#!/usr/bin/env python3
"""Thin CLI for governed prompt queue controlled execution.

This utility remains specialized for work-item execution adapter runs.
For legacy queue-loop invocation compatibility, it can delegate queue-loop
execution to the canonical `scripts/run_prompt_queue.py` entrypoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_prompt_queue import main as run_prompt_queue_main  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    default_execution_result_path,
    read_execution_result_artifact,
    run_queue_step_execution_adapter,
    write_execution_result_artifact,
)
from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one deterministic controlled execution for a runnable work item")
    parser.add_argument("--work-item-id")
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--manifest-path", help="When set, delegate queue-loop execution to canonical run_prompt_queue CLI")
    parser.add_argument("--output-path", help="Optional output path for delegated canonical queue-loop execution")
    return parser.parse_args(argv)


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"work item '{work_item_id}' not found")


def _run_specialized_execution(args: argparse.Namespace) -> int:
    if not args.work_item_id:
        print(json.dumps({"error": "--work-item-id is required unless --manifest-path is provided"}, indent=2), file=sys.stderr)
        return 2

    queue_state_path = Path(args.queue_state_path)
    queue_state = read_json_artifact(queue_state_path)

    try:
        work_item = _find_work_item(queue_state, args.work_item_id)
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    gating_path = work_item.get("gating_decision_artifact_path")
    if not gating_path:
        print(json.dumps({"error": "missing gating_decision_artifact_path", "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    gating_artifact_path = Path(gating_path)
    if not gating_artifact_path.exists():
        print(
            json.dumps({"error": f"gating decision artifact not found: {gating_artifact_path}", "work_item_id": args.work_item_id}, indent=2),
            file=sys.stderr,
        )
        return 2

    gating_artifact = read_json_artifact(gating_artifact_path)

    try:
        execution_result = run_queue_step_execution_adapter(
            queue_state=queue_state,
            step={
                "step_id": f"step-{queue_state.get('current_step_index', 0) + 1:03d}",
                "work_item_id": args.work_item_id,
                "execution_mode": "simulated",
            },
            input_refs={
                "gating_decision_artifact": gating_artifact,
                "source_queue_state_path": str(queue_state_path),
            },
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    result_path = default_execution_result_path(args.work_item_id, queue_state_path)

    try:
        write_execution_result_artifact(execution_result, result_path)
        read_execution_result_artifact(result_path)
    except Exception as exc:
        print(
            json.dumps(
                {"error": f"Execution result artifact validation/write failed: {exc}", "work_item_id": args.work_item_id},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            {
                "queue_id": queue_state.get("queue_id"),
                "execution_result_artifact_path": str(result_path),
                "work_item_id": args.work_item_id,
                "execution_status": execution_result["execution_status"],
            },
            indent=2,
        )
    )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.manifest_path:
        delegated_argv = [
            "--manifest-path",
            args.manifest_path,
            "--queue-state-path",
            args.queue_state_path,
        ]
        if args.output_path:
            delegated_argv.extend(["--output-path", args.output_path])
        return run_prompt_queue_main(delegated_argv)

    return _run_specialized_execution(args)


if __name__ == "__main__":
    raise SystemExit(main())
