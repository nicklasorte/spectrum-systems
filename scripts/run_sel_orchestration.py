#!/usr/bin/env python3
"""Run SEL orchestration runner using real CDE bundle artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.sel_orchestration_runner import (
    SELOrchestrationRunnerError,
    run_sel_orchestration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SEL orchestration over a governed CDE artifact bundle.")
    parser.add_argument("--cde-bundle-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--observed-outcome", default=None)
    parser.add_argument("--observed-outcome-ref", default=None)
    args = parser.parse_args()

    try:
        result = run_sel_orchestration(
            cde_bundle_dir=Path(args.cde_bundle_dir),
            output_dir=Path(args.output_dir),
            observed_outcome=args.observed_outcome,
            observed_outcome_ref=args.observed_outcome_ref,
        )
    except SELOrchestrationRunnerError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    if result["artifact_chain_validation"]["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
