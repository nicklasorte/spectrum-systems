#!/usr/bin/env python3
"""Thin CLI for one deterministic fail-closed prompt-queue loop iteration."""

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
    run_queue_once,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one fail-closed prompt queue execution-loop iteration.")
    parser.add_argument("--manifest-path", required=True, help="Path to prompt_queue_manifest JSON artifact.")
    parser.add_argument("--queue-state-path", required=True, help="Path to prompt_queue_state JSON artifact.")
    return parser.parse_args(argv)


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised through CLI integration behavior
        raise QueueLoopError(f"unable to read JSON artifact '{path}': {exc}") from exc
    if not isinstance(payload, dict):
        raise QueueLoopError(f"artifact '{path}' must be a JSON object")
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    manifest_path = Path(args.manifest_path)
    queue_state_path = Path(args.queue_state_path)

    try:
        manifest = _read_json(manifest_path)
        queue_state = _read_json(queue_state_path)
        updated_queue_state = run_queue_once(queue_state=queue_state, manifest=manifest)
        write_artifact(updated_queue_state, queue_state_path)
    except QueueLoopError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "queue_status": updated_queue_state["queue_status"],
                "current_step_index": updated_queue_state["current_step_index"],
                "total_steps": updated_queue_state["total_steps"],
            },
            indent=2,
        )
    )

    if updated_queue_state["queue_status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
