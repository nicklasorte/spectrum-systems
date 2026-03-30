#!/usr/bin/env python3
"""CLI for deterministic autonomous-cycle status and backlog observability artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.orchestration.cycle_observability import (  # noqa: E402
    CycleObservabilityError,
    build_cycle_backlog_snapshot,
    build_cycle_status,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cycle status/backlog observability artifacts")
    parser.add_argument("--manifest", action="append", required=True, help="Path to cycle_manifest.json (repeatable)")
    parser.add_argument("--status-output", help="Optional output path for single-cycle cycle_status_artifact JSON")
    parser.add_argument("--backlog-output", help="Optional output path for cycle_backlog_snapshot JSON")
    parser.add_argument("--generated-at", help="Optional deterministic timestamp for backlog snapshot")
    return parser.parse_args()


def _write(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    manifest_paths = sorted(args.manifest)

    try:
        statuses = [build_cycle_status(path) for path in manifest_paths]
        backlog = build_cycle_backlog_snapshot(manifest_paths, generated_at=args.generated_at)
    except CycleObservabilityError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 2

    if args.status_output:
        if len(statuses) != 1:
            print(json.dumps({"status": "blocked", "error": "--status-output requires exactly one --manifest"}, indent=2))
            return 2
        _write(args.status_output, statuses[0])

    if args.backlog_output:
        _write(args.backlog_output, backlog)

    print(
        json.dumps(
            {
                "status": "ok",
                "manifest_count": len(manifest_paths),
                "queue_counts": {k: len(v) for k, v in backlog["queues"].items()},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
