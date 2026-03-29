#!/usr/bin/env python3
"""Thin CLI wrapper for QUEUE-12 queue policy backtesting."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    run_queue_policy_backtest,
    validate_policy_backtest_report,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic prompt queue policy backtesting")
    parser.add_argument("--replay-run-ref", action="append", dest="replay_run_refs", required=True)
    parser.add_argument("--baseline-policy-id", required=True)
    parser.add_argument("--baseline-policy-version", required=True)
    parser.add_argument("--candidate-policy-id", required=True)
    parser.add_argument("--candidate-policy-version", required=True)
    parser.add_argument("--timestamp", default="2026-03-29T00:00:00Z")
    parser.add_argument("--output-path", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    payload = {
        "replay_run_refs": args.replay_run_refs,
        "baseline_policy_ref": {
            "policy_id": args.baseline_policy_id,
            "policy_version": args.baseline_policy_version,
        },
        "policy_under_test_ref": {
            "policy_id": args.candidate_policy_id,
            "policy_version": args.candidate_policy_version,
        },
        "timestamp": args.timestamp,
    }

    try:
        report = run_queue_policy_backtest(payload)
        validate_policy_backtest_report(report)
        write_artifact(report, Path(args.output_path))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps({"output_path": args.output_path, "recommendation": report.get("recommendation")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
