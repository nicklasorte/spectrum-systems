#!/usr/bin/env python3
"""OC-07: Generate a dashboard truth projection.

Reads two JSON inputs that each describe a proof view (one from repo
truth, one from the dashboard / public surface) and writes the
projection record to stdout (or to a file when --out is given).

The projection is read-only. It NEVER modifies the dashboard surface.

Exit codes:
  0  alignment_status == aligned
  1  alignment_status in (drifted, missing, corrupt)
  2  alignment_status == unknown
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.observability.dashboard_truth_projection import (  # noqa: E402
    build_dashboard_truth_projection,
)


def _load(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a dashboard truth projection record."
    )
    parser.add_argument("--repo-truth", type=Path, required=False)
    parser.add_argument("--dashboard-view", type=Path, required=False)
    parser.add_argument("--freshness-audit", type=Path, default=None)
    parser.add_argument(
        "--projection-id", type=str, default="dtp-cli-1"
    )
    parser.add_argument(
        "--audit-timestamp", type=str, default="1970-01-01T00:00:00Z"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    projection = build_dashboard_truth_projection(
        projection_id=args.projection_id,
        audit_timestamp=args.audit_timestamp,
        repo_truth=_load(args.repo_truth),
        dashboard_view=_load(args.dashboard_view),
        freshness_audit=_load(args.freshness_audit),
    )

    text = json.dumps(projection, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)

    align = projection.get("alignment_status", "unknown")
    if align == "aligned":
        return 0
    if align == "unknown":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
