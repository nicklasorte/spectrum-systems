#!/usr/bin/env python3
"""Run BF cross-run comparison and anomaly detection.

Usage
-----
    # Compare specific NRR files:
    python scripts/cross_run_intelligence.py --input run1/nrr.json --input run2/nrr.json

    # Auto-discover NRR files in a directory:
    python scripts/cross_run_intelligence.py --dir path/to/nrr_dir

    # Specify output directory:
    python scripts/cross_run_intelligence.py --input run1/nrr.json --input run2/nrr.json \\
        --output-dir outputs/comparison/

Outputs
-------
- Prints a concise operator summary to stdout.
- Writes cross_run_comparison.json and cross_run_intelligence_decision.json
  to the chosen output directory (default: current working directory).
- Archives decision artifact to data/cross_run_intelligence_decisions/.

Exit codes
----------
0   pass — comparison complete; no error or warning findings
1   warning — comparison complete but warning-level findings present
2   fail — missing or invalid inputs, schema failures, or error-level findings
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.cross_run_intelligence import (  # noqa: E402
    compare_normalized_runs,
)

_ARCHIVE_DIR = _REPO_ROOT / "data" / "cross_run_intelligence_decisions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persist(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _archive_decision(decision: Dict[str, Any], archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / f"cross_run_intelligence_decision_{stamp}.json"
    suffix = 1
    while target.exists():
        target = archive_dir / f"cross_run_intelligence_decision_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return target


def _discover_nrr_files(directory: Path) -> List[Path]:
    """Recursively discover normalized_run_result.json files under *directory*."""
    return sorted(directory.rglob("normalized_run_result.json"))


def _print_summary(result: Dict[str, Any]) -> None:
    decision = result.get("cross_run_intelligence_decision") or {}
    crc = result.get("cross_run_comparison")

    print(f"overall_status:  {decision.get('overall_status', 'unknown')}")
    print(f"failure_type:    {decision.get('failure_type', 'unknown')}")

    if crc:
        print(f"study_type:      {crc.get('study_type', 'unknown')}")
        print(f"compared_runs:   {len(crc.get('compared_runs', []))}")
        print(f"metric_comps:    {len(crc.get('metric_comparisons', []))}")
        print(f"rankings:        {len(crc.get('scenario_rankings', []))}")
        print(f"anomaly_flags:   {len(crc.get('anomaly_flags', []))}")
    else:
        print("cross_run_comparison: not produced (hard failure)")

    findings = result.get("findings") or []
    if findings:
        print("findings:")
        for f in findings:
            print(f"  [{f['severity'].upper()}] {f['code']}: {f['message']}")
    else:
        print("findings:        []")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="BF cross-run comparison and anomaly detection (Prompt BF)."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input",
        dest="inputs",
        action="append",
        metavar="PATH",
        help="Path to a normalized_run_result.json file. Can be specified multiple times.",
    )
    input_group.add_argument(
        "--dir",
        dest="directory",
        metavar="DIR",
        help="Directory to recursively search for normalized_run_result.json files.",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Directory to write output artifacts (default: current working directory).",
    )
    args = parser.parse_args(argv)

    # Resolve input paths
    input_paths: List[str] = []
    if args.directory:
        directory = Path(args.directory).resolve()
        if not directory.is_dir():
            print(f"ERROR: Directory not found: {directory}", file=sys.stderr)
            return 2
        discovered = _discover_nrr_files(directory)
        if not discovered:
            print(
                f"ERROR: No normalized_run_result.json files found in: {directory}",
                file=sys.stderr,
            )
            return 2
        input_paths = [str(p) for p in discovered]
        print(f"Discovered {len(input_paths)} NRR file(s) in: {directory}")
    else:
        input_paths = list(args.inputs or [])

    # Resolve output directory
    output_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    # Run comparison
    try:
        result = compare_normalized_runs(input_paths=input_paths)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Unexpected failure during comparison: {exc}", file=sys.stderr)
        return 2

    _print_summary(result)

    crc = result.get("cross_run_comparison")
    decision = result.get("cross_run_intelligence_decision") or {}

    # Write outputs
    if crc:
        crc_path = output_dir / "cross_run_comparison.json"
        try:
            _persist(crc, crc_path)
            print(f"\ncross_run_comparison written to:   {crc_path}")
        except OSError as exc:
            print(
                f"WARNING: Could not write cross_run_comparison.json: {exc}",
                file=sys.stderr,
            )

    if decision:
        cri_path = output_dir / "cross_run_intelligence_decision.json"
        try:
            _persist(decision, cri_path)
            print(f"decision written to:               {cri_path}")
        except OSError as exc:
            print(
                f"WARNING: Could not write cross_run_intelligence_decision.json: {exc}",
                file=sys.stderr,
            )

        try:
            archive_path = _archive_decision(decision, _ARCHIVE_DIR)
            print(f"decision archived to:              {archive_path}")
        except OSError as exc:
            print(f"WARNING: Could not archive decision: {exc}", file=sys.stderr)

    overall_status = decision.get("overall_status", "fail")
    if overall_status == "pass":
        return 0
    if overall_status == "warning":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
