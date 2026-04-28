#!/usr/bin/env python3
"""OC-22: Generate an operator runbook entry from existing proof.

Reads supplied evidence files and writes a short evidence-bound
runbook entry. The entry refuses confident guidance when proof is
insufficient, stale, or conflicting.

Exit codes:
  0  status == pass
  1  status == block
  2  status == freeze
  3  status in (insufficient_evidence, blocked) — operator must triage
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

from spectrum_systems.modules.governance.operator_runbook import (  # noqa: E402
    build_operator_runbook_entry,
)


def _load(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an evidence-bound operator runbook entry."
    )
    parser.add_argument("--proof-intake", type=Path, default=None)
    parser.add_argument("--bottleneck", type=Path, default=None)
    parser.add_argument("--dashboard-projection", type=Path, default=None)
    parser.add_argument("--closure-packet", type=Path, default=None)
    parser.add_argument("--closure-bundle", type=Path, default=None)
    parser.add_argument(
        "--entry-id", type=str, default="runbook-cli-1"
    )
    parser.add_argument(
        "--audit-timestamp", type=str, default="1970-01-01T00:00:00Z"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    entry = build_operator_runbook_entry(
        entry_id=args.entry_id,
        audit_timestamp=args.audit_timestamp,
        proof_intake=_load(args.proof_intake),
        bottleneck_classification=_load(args.bottleneck),
        dashboard_projection=_load(args.dashboard_projection),
        closure_packet=_load(args.closure_packet),
        operational_closure_bundle=_load(args.closure_bundle),
    )

    text = json.dumps(entry, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)

    status = str(entry.get("status", "unknown"))
    if status == "pass":
        return 0
    if status == "block":
        return 1
    if status == "freeze":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
