#!/usr/bin/env python3
"""Canonical thin CLI for one deterministic fail-closed prompt-queue loop iteration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    QueueLoopError,
    read_json_artifact,
    run_queue_once,
    write_artifact,
)

EXIT_SUCCESS = 0
EXIT_FAILURE = 2
EXIT_BLOCKED = 3


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one fail-closed prompt queue execution-loop iteration.")
    parser.add_argument(
        "--manifest-path",
        "--manifest",
        dest="manifest_path",
        required=True,
        help="Path to prompt_queue_manifest JSON artifact.",
    )
    parser.add_argument(
        "--queue-state-path",
        "--queue-path",
        dest="queue_state_path",
        required=True,
        help="Path to prompt_queue_state JSON artifact.",
    )
    parser.add_argument(
        "--output-path",
        help="Optional output path for updated prompt_queue_state artifact. Defaults to --queue-state-path.",
    )
    return parser.parse_args(argv)


def _read_object_artifact(path: Path, label: str) -> dict:
    try:
        payload = read_json_artifact(path)
    except Exception as exc:  # pragma: no cover - exercised through CLI integration behavior
        raise QueueLoopError(f"unable to read {label} artifact '{path}': {exc}") from exc
    if not isinstance(payload, dict):
        raise QueueLoopError(f"{label} artifact '{path}' must be a JSON object")
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    manifest_path = Path(args.manifest_path)
    queue_state_path = Path(args.queue_state_path)
    output_path = Path(args.output_path) if args.output_path else queue_state_path

    try:
        manifest = _read_object_artifact(manifest_path, "manifest")
        queue_state = _read_object_artifact(queue_state_path, "queue_state")
        updated_queue_state = run_queue_once(queue_state=queue_state, manifest=manifest)
        write_artifact(updated_queue_state, output_path)
    except QueueLoopError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return EXIT_FAILURE

    print(
        json.dumps(
            {
                "manifest_path": str(manifest_path),
                "queue_state_path": str(queue_state_path),
                "output_path": str(output_path),
                "queue_status": updated_queue_state["queue_status"],
                "current_step_index": updated_queue_state["current_step_index"],
                "total_steps": updated_queue_state["total_steps"],
            },
            indent=2,
        )
    )

    if updated_queue_state["queue_status"] == "blocked":
        return EXIT_BLOCKED
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
