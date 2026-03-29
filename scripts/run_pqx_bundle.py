#!/usr/bin/env python3
"""Run a governed PQX executable bundle from docs/roadmaps/execution_bundles.md."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import (
    PQXBundleOrchestratorError,
    execute_bundle_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a PQX bundle deterministically.")
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--bundle-state-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sequence-run-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--bundle-plan-path", default="docs/roadmaps/execution_bundles.md")
    args = parser.parse_args()

    try:
        result = execute_bundle_run(
            bundle_id=args.bundle_id,
            bundle_state_path=Path(args.bundle_state_path),
            output_dir=Path(args.output_dir),
            run_id=args.run_id,
            sequence_run_id=args.sequence_run_id,
            trace_id=args.trace_id,
            bundle_plan_path=Path(args.bundle_plan_path),
        )
    except PQXBundleOrchestratorError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
