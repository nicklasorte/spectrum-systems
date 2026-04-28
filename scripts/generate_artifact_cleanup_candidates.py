#!/usr/bin/env python3
"""OC-19: Generate the advisory cleanup candidate report.

Reads a JSON list of candidate descriptors and writes the cleanup
candidate report to stdout (or to a file when --out is given). The
report is advisory only; it never deletes artifacts.

Exit codes:
  0  no candidate is unknown_blocked
  1  at least one candidate is unknown_blocked (operator must triage)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.cleanup_candidate_report import (  # noqa: E402
    build_cleanup_candidate_report,
)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the advisory cleanup candidate report (never deletes)."
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
        help="path to a JSON list of candidate descriptors",
    )
    parser.add_argument(
        "--report-id", type=str, default="cleanup-cli-1"
    )
    parser.add_argument(
        "--audit-timestamp", type=str, default="1970-01-01T00:00:00Z"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    raw = json.loads(args.candidates.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("--candidates must point to a JSON list", file=sys.stderr)
        return 2

    report = build_cleanup_candidate_report(
        report_id=args.report_id,
        audit_timestamp=args.audit_timestamp,
        candidates=raw,
    )

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)

    candidates: List[Any] = report.get("candidates", []) or []
    has_unknown_blocked = any(
        c.get("classification") == "unknown_blocked" for c in candidates
    )
    return 1 if has_unknown_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
