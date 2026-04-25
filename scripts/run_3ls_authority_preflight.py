#!/usr/bin/env python3
"""Combined authority preflight for the 3LS governed runtime.

Runs two complementary authority checks:

1. run_authority_shape_preflight — scans dashboard_seed, dashboard_metrics, and
   MET-prefixed review docs for authority-shaped vocabulary used outside canonical
   owner systems.

2. The authority leak guard scope (spectrum_systems/modules/) is handled by
   run_authority_leak_guard.py (CI gate, not duplicated here).

This script is the single entry point to verify the 3LS artifact surface is
authority-vocabulary-clean before promotion.

Usage:
    python scripts/run_3ls_authority_preflight.py \\
      --suggest-only \\
      --output outputs/authority_shape_preflight/3ls_authority_preflight_result.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _run_shape_preflight(suggest_only: bool, registry: str) -> dict:
    """Invoke run_authority_shape_preflight and return its result payload."""
    result_path = REPO_ROOT / "outputs" / "authority_shape_preflight" / "authority_shape_preflight_result.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_authority_shape_preflight.py"),
        "--registry", registry,
        "--output", str(result_path.relative_to(REPO_ROOT)),
    ]
    if suggest_only:
        cmd.append("--suggest-only")

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result_path.is_file():
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return {
        "status": "error",
        "violation_count": -1,
        "scanned_file_count": 0,
        "scanned_files": [],
        "violations": [{"rule": "runner_error", "message": proc.stderr.strip() or "unknown error"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combined 3LS authority preflight (shape + dashboard scope)"
    )
    parser.add_argument(
        "--registry",
        default="contracts/governance/authority_registry.json",
        help="Authority registry for owner path exclusions",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/3ls_authority_preflight_result.json",
        help="Output artifact path",
    )
    parser.add_argument(
        "--suggest-only",
        action="store_true",
        help="Print violations but always exit 0 (non-blocking mode)",
    )
    args = parser.parse_args()

    shape_result = _run_shape_preflight(suggest_only=True, registry=args.registry)

    total_violations = shape_result.get("violation_count", 0)
    status = "pass" if total_violations == 0 else "fail"

    result: dict = {
        "status": status,
        "total_violation_count": total_violations,
        "checks": {
            "authority_shape_preflight": shape_result,
        },
    }

    out_path = REPO_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    shape_count = shape_result.get("violation_count", 0)
    shape_files = shape_result.get("scanned_file_count", 0)

    if total_violations == 0:
        print(f"3LS authority preflight PASSED — 0 violations across {shape_files} files")
    else:
        print(f"3LS authority preflight FAILED — {total_violations} violation(s)")
        for v in shape_result.get("violations", [])[:20]:
            tok = v.get("token", v.get("artifact_type", "?"))
            loc = f":{v['line']}" if "line" in v else ""
            print(f"  [authority_shape] [{v['rule']}] {v['path']}{loc}  token={tok}")

    print(f"result written to: {out_path}")
    return 0 if (args.suggest_only or total_violations == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
