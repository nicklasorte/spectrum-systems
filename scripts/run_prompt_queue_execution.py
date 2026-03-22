#!/usr/bin/env python3
"""Thin CLI for governed prompt queue controlled execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    ExecutionQueueIntegrationError,
    ExecutionRunnerError,
    default_execution_result_path,
    finalize_execution,
    revalidate_execution_entry,
    run_simulated_execution,
    transition_to_executing,
    validate_execution_result_artifact,
    validate_queue_state,
    validate_work_item,
    write_artifact,
    write_execution_result_artifact,
)
from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one deterministic controlled execution for a runnable work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument(
        "--simulate-finalization-failure",
        action="store_true",
        help="Testing-only flag to stop after execution result write and before queue finalization.",
    )
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
        revalidate_execution_entry(work_item=work_item, gating_decision_artifact=gating_artifact)
        queue_executing, executing_item = transition_to_executing(queue_state=queue_state, work_item_id=args.work_item_id)
    except (ExecutionRunnerError, ExecutionQueueIntegrationError) as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    write_artifact(queue_executing, queue_state_path)

    execution_result = run_simulated_execution(
        work_item=executing_item,
        source_queue_state_path=str(queue_state_path),
    )

    result_path = default_execution_result_path(args.work_item_id, queue_state_path)

    try:
        validate_execution_result_artifact(execution_result)
        write_execution_result_artifact(execution_result, result_path)
    except Exception as exc:  # fail closed and finalize as execution failure
        failed_result = dict(execution_result)
        failed_result["execution_status"] = "failure"
        failed_result["output_reference"] = None
        failed_result["error_summary"] = f"Execution result artifact validation/write failed: {exc}"
        try:
            validate_execution_result_artifact(failed_result)
            write_execution_result_artifact(failed_result, result_path)
            queue_failed, failed_item = finalize_execution(
                queue_state=queue_executing,
                work_item_id=args.work_item_id,
                execution_result_artifact_path=str(result_path),
                execution_status="failure",
            )
            validate_work_item(failed_item)
            validate_queue_state(queue_failed)
            write_artifact(queue_failed, queue_state_path)
        except Exception as nested:
            print(json.dumps({"error": f"fatal fail-closed path failed: {nested}", "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    if args.simulate_finalization_failure:
        print(json.dumps({"error": "simulated finalization failure", "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    try:
        queue_final, final_item = finalize_execution(
            queue_state=queue_executing,
            work_item_id=args.work_item_id,
            execution_result_artifact_path=str(result_path),
            execution_status=execution_result["execution_status"],
        )
    except ExecutionQueueIntegrationError as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "work_item_id": args.work_item_id,
                    "execution_result_artifact_path": str(result_path),
                    "reconciliation_required": True,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    validate_work_item(final_item)
    validate_queue_state(queue_final)
    write_artifact(queue_final, queue_state_path)
    work_item_path = queue_state_path.parent / f"{final_item['work_item_id']}.work_item.json"
    write_artifact(final_item, work_item_path)

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "work_item_path": str(work_item_path),
                "execution_result_artifact_path": str(result_path),
                "work_item_id": args.work_item_id,
                "execution_status": execution_result["execution_status"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
