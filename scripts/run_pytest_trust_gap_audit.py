#!/usr/bin/env python3
"""Run deterministic pytest trust-gap backtest over recent local preflight artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pytest_trust_gap_audit import run_pytest_trust_gap_audit, scan_preflight_artifacts  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic pytest trust-gap backtest.")
    parser.add_argument("--scan-root", action="append", default=[], help="Scan root (repeatable). Defaults to outputs/artifacts/data.")
    parser.add_argument("--max-artifacts", type=int, default=50, help="Maximum artifacts to evaluate.")
    parser.add_argument("--output-dir", default="outputs/pytest_trust_gap_audit", help="Backtest output directory.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scan_root_raw = args.scan_root or ["outputs", "artifacts", "data"]
    roots = [Path(root) if Path(root).is_absolute() else (REPO_ROOT / root) for root in scan_root_raw]
    scanned = scan_preflight_artifacts(roots, max_artifacts=args.max_artifacts)
    scope = {
        "roots": [str(path) for path in roots],
        "artifact_globs": ["**/contract_preflight_result_artifact.json"],
        "max_artifacts": args.max_artifacts,
        "repo_root": str(REPO_ROOT),
    }
    result = run_pytest_trust_gap_audit(scanned_artifacts=scanned, audit_scope=scope)

    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else (REPO_ROOT / args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "pytest_trust_gap_backtest_result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result_path": str(result_path), "evaluated_runs": result["evaluated_runs"], "suspect_runs": result["suspect_runs"], "final_decision": result["final_decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
