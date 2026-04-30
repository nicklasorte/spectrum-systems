#!/usr/bin/env python3
"""CLI: run minimality sweep to identify redundancy candidates (CLX-ALL-01 Phase 6).

Advisory only. No files are deleted or modified.

Usage:
    python scripts/run_minimality_sweep.py [--output-json path]

Exit codes:
    0 — sweep complete (advisory report produced; review candidates manually)
    1 — runtime error
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
    parser = argparse.ArgumentParser(description="Minimality sweep — advisory redundancy scanner")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args(argv)

    trace_id = args.trace_id or str(uuid.uuid4())

    from spectrum_systems.modules.runtime.minimality_sweep import (
        MinimalitySweepError,
        run_minimality_sweep,
    )

    try:
        report = run_minimality_sweep(trace_id=trace_id, run_id=args.run_id)
    except MinimalitySweepError as e:
        print(json.dumps({"error": str(e)}))
        return 1

    output = json.dumps(report, indent=2)
    print(output)

    if args.output_json:
        Path(args.output_json).write_text(output, encoding="utf-8")

    candidate_count = len(report.get("candidates") or [])
    print(f"\n[sweep] {candidate_count} candidate(s) identified (advisory, no action taken)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
