#!/usr/bin/env python3
"""CLI: run historical replay validation backtest (CLX-ALL-01 Phase 4).

Usage:
    python scripts/run_historical_replay_validator.py \
        [--trace-id ID] [--additional-cases-json path] [--output-json path]

Exit codes:
    0 — all replay cases pass
    1 — one or more mismatches, missing classifications, or non-deterministic results
    2 — usage/runtime error
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Historical replay validation backtest")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--additional-cases-json", default="", help="Path to JSON with additional cases")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args(argv)

    trace_id = args.trace_id or str(uuid.uuid4())

    additional_cases = None
    if args.additional_cases_json:
        cases_path = Path(args.additional_cases_json)
        if not cases_path.is_file():
            print(json.dumps({"error": f"cases file not found: {args.additional_cases_json}"}))
            return 2
        try:
            additional_cases = json.loads(cases_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(json.dumps({"error": f"malformed additional-cases JSON: {exc}", "status": "error"}))
            return 2

    from spectrum_systems.modules.runtime.historical_replay_validator import (
        HistoricalReplayValidatorError,
        run_historical_replay_validation,
    )

    try:
        report = run_historical_replay_validation(
            trace_id=trace_id,
            run_id=args.run_id,
            additional_cases=additional_cases,
        )
    except HistoricalReplayValidatorError as e:
        print(json.dumps({"error": str(e), "status": "error"}))
        return 2

    output = json.dumps(report, indent=2)
    print(output)

    if args.output_json:
        Path(args.output_json).write_text(output, encoding="utf-8")

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
