#!/usr/bin/env python3
"""Thin CLI for deterministic prompt queue observability snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    generate_queue_snapshot,
    validate_queue_invariants,
    validate_observability_snapshot,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate read-only prompt queue observability snapshot")
    parser.add_argument("--queue-path", required=True, help="Path to prompt queue state JSON")
    parser.add_argument(
        "--output-path",
        required=True,
        help="Path where prompt_queue_observability_snapshot JSON will be written",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    queue_path = Path(args.queue_path)
    output_path = Path(args.output_path)

    queue_state = json.loads(queue_path.read_text(encoding="utf-8"))
    snapshot = generate_queue_snapshot(queue_state)
    violations = validate_queue_invariants(queue_state)
    if violations != snapshot["invariant_violations"]:
        raise ValueError("Invariant mismatch between snapshot generation and direct invariant validation")

    validate_observability_snapshot(snapshot)
    written = write_artifact(snapshot, output_path)
    print(json.dumps({"snapshot_path": str(written), "invariant_violations": violations}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
