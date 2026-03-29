#!/usr/bin/env python3
"""Thin CLI for deterministic sequential prompt-queue PQX execution with resume support."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pqx_sequence_runner import (  # noqa: E402
    PQXSequenceRunnerError,
    execute_sequence_run,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run narrow sequential PQX execution for 2–3 ordered slices")
    parser.add_argument("--state-path", required=True, help="Path to prompt_queue_sequence_run state artifact")
    parser.add_argument("--slices-path", required=True, help="Path to ordered slice request list JSON")
    parser.add_argument("--queue-run-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--resume", action="store_true", help="Resume from persisted state")
    parser.add_argument("--max-slices", type=int, default=None, help="Optional bounded number of slices to run this invocation")
    return parser.parse_args(argv)


def _load_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PQXSequenceRunnerError(f"failed to load {label}: {exc}") from exc


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    state_path = Path(args.state_path)
    slices_path = Path(args.slices_path)

    try:
        slice_requests = _load_json(slices_path, "slice request list")
        state = execute_sequence_run(
            slice_requests=slice_requests,
            state_path=state_path,
            queue_run_id=args.queue_run_id,
            run_id=args.run_id,
            trace_id=args.trace_id,
            resume=args.resume,
            max_slices=args.max_slices,
        )
    except PQXSequenceRunnerError as exc:
        print(json.dumps({"status": "failed", "error": str(exc), "state_path": str(state_path)}), file=sys.stderr)
        return 2

    output = {
        "status": state["status"],
        "queue_run_id": state["queue_run_id"],
        "run_id": state["run_id"],
        "completed": len(state["completed_slice_ids"]),
        "failed": len(state["failed_slice_ids"]),
        "next_slice_ref": state["next_slice_ref"],
        "resume_token": state["resume_token"],
        "state_path": str(state_path),
    }
    print(json.dumps(output))

    if state["status"] == "completed":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
