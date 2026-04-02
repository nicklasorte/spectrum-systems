#!/usr/bin/env python3
"""Thin CLI wrapper for deterministic PQX sequential execution (CON-046)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pqx_sequential_loop import (
    PQXSequentialLoopError,
    run_pqx_sequential,
)


def _load_json(path: Path) -> dict | list:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, (dict, list)):
        raise PQXSequentialLoopError(f"JSON payload must be object or list: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run sequential PQX slices via control-loop native orchestration")
    parser.add_argument("--roadmap-file", type=Path, required=True, help="Path to ordered slice list JSON")
    parser.add_argument("--initial-context", type=Path, required=True, help="Path to initial context JSON")
    parser.add_argument("--output", type=Path, required=True, help="Path to write execution trace artifact JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roadmap_payload = _load_json(args.roadmap_file)
    initial_context_payload = _load_json(args.initial_context)

    slices = roadmap_payload.get("slices") if isinstance(roadmap_payload, dict) else roadmap_payload
    if not isinstance(slices, list):
        raise PQXSequentialLoopError("roadmap file must be a list or an object with a 'slices' list")
    if not isinstance(initial_context_payload, dict):
        raise PQXSequentialLoopError("initial context must be a JSON object")

    trace = run_pqx_sequential(slices=slices, initial_context=initial_context_payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(trace, indent=2))
    return 2 if trace.get("final_status") == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
