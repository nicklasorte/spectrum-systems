#!/usr/bin/env python3
"""Run deterministic governed failure-injection chaos validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.governed_failure_injection import (  # noqa: E402
    GovernedFailureInjectionError,
    list_case_ids,
    run_governed_failure_injection,
    write_summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic fail-closed chaos validation across governed runtime seams."
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/governed_failure_injection",
        help="Directory to write governed failure injection artifacts.",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional list of case IDs to run. Defaults to all cases.",
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List available case IDs and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_cases:
        print(json.dumps(list_case_ids(), indent=2))
        return 0

    try:
        summary = run_governed_failure_injection(case_filter=args.cases)
    except GovernedFailureInjectionError as exc:
        print(f"ERROR: governed failure injection failed: {exc}", file=sys.stderr)
        return 2

    out_path = write_summary(Path(args.output_dir), summary)
    print(json.dumps({"output": str(out_path), "summary": summary}, indent=2, sort_keys=True))
    return 0 if int(summary.get("fail_count", 1)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
