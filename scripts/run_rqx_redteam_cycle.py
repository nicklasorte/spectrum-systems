#!/usr/bin/env python3
"""Execute RQX red-team cycle orchestration using governed artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.rqx_redteam_orchestrator import RQXRedTeamError, run_redteam_cycle


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded RQX red-team cycle orchestration.")
    parser.add_argument("--review-request", required=True)
    parser.add_argument("--round-config", required=True)
    parser.add_argument("--exploit-bundle", required=True)
    parser.add_argument("--finding", action="append", default=[])
    parser.add_argument("--closure-request", action="append", default=[])
    args = parser.parse_args()

    try:
        result = run_redteam_cycle(
            review_request=_load(Path(args.review_request)),
            round_config=_load(Path(args.round_config)),
            findings=[_load(Path(path)) for path in args.finding],
            exploit_bundle=_load(Path(args.exploit_bundle)),
            closure_requests=[_load(Path(path)) for path in args.closure_request],
        )
    except (RQXRedTeamError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    unresolved = [item for item in result["closure_results"] if item["status"] != "pass"]
    return 0 if not unresolved and not result["operator_handoffs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
