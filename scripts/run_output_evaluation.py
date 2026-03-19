#!/usr/bin/env python3
"""Run BE output normalization + evaluation for a validated execution bundle.

Usage
-----
    python scripts/run_output_evaluation.py --manifest path/to/run_bundle_manifest.json
    python scripts/run_output_evaluation.py --bundle-root path/to/bundle_dir

Outputs
-------
- Prints a concise operator summary to stdout.
- Writes normalized_run_result.json and run_output_evaluation_decision.json
  to outputs/ under the bundle root when possible.
- Archives decision artifact to data/run_output_evaluation_decisions/.

Exit codes
----------
0   pass — normalization complete; run is ready or limited_use with no errors
1   warning — normalization complete but findings present at warning level
2   fail — missing files, malformed JSON, schema failures, or error-level findings
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.run_output_evaluation import (  # noqa: E402
    evaluate_run_outputs,
)

_ARCHIVE_DIR = _REPO_ROOT / "data" / "run_output_evaluation_decisions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persist(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _archive_decision(decision: Dict[str, Any], archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / f"run_output_evaluation_decision_{stamp}.json"
    suffix = 1
    while target.exists():
        target = archive_dir / f"run_output_evaluation_decision_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return target


def _print_summary(result: Dict[str, Any]) -> None:
    decision = result.get("run_output_evaluation_decision") or {}
    nrr = result.get("normalized_run_result")

    print(f"overall_status:  {decision.get('overall_status', 'unknown')}")
    print(f"failure_type:    {decision.get('failure_type', 'unknown')}")

    if nrr:
        print(f"study_type:      {nrr.get('study_type', 'unknown')}")
        completeness = nrr.get("metrics", {}).get("completeness", {})
        print(f"completeness:    {completeness.get('status', 'unknown')}")
        readiness = nrr.get("evaluation_signals", {}).get("readiness", "unknown")
        print(f"readiness:       {readiness}")
    else:
        print("normalized_run_result: not produced (hard failure)")

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="BE run output normalization and evaluation (Prompt BE)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--manifest",
        dest="manifest",
        help="Path to the run_bundle_manifest.json file.",
    )
    group.add_argument(
        "--bundle-root",
        dest="bundle_root",
        help="Path to the bundle root directory (locates run_bundle_manifest.json automatically).",
    )
    args = parser.parse_args(argv)

    manifest_path: Optional[Path] = None
    bundle_root: Optional[Path] = None

    if args.bundle_root:
        bundle_root = Path(args.bundle_root).resolve()
        candidate = bundle_root / "run_bundle_manifest.json"
        if not candidate.exists():
            print(
                f"ERROR: No run_bundle_manifest.json found in: {bundle_root}",
                file=sys.stderr,
            )
            return 2
        manifest_path = candidate
    else:
        manifest_path = Path(args.manifest).resolve()
        bundle_root = manifest_path.parent

    # Run evaluation
    try:
        result = evaluate_run_outputs(
            manifest_path=manifest_path,
            bundle_root=bundle_root,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Unexpected failure during evaluation: {exc}", file=sys.stderr)
        return 2

    _print_summary(result)

    decision = result.get("run_output_evaluation_decision") or {}
    nrr = result.get("normalized_run_result")

    # Write outputs
    outputs_dir = bundle_root / "outputs" if bundle_root else Path("outputs")
    if nrr:
        nrr_path = outputs_dir / "normalized_run_result.json"
        try:
            _persist(nrr, nrr_path)
            print(f"\nnormalized_run_result written to: {nrr_path}")
        except OSError as exc:
            print(f"WARNING: Could not write normalized_run_result.json: {exc}", file=sys.stderr)

    if decision:
        roe_path = outputs_dir / "run_output_evaluation_decision.json"
        try:
            _persist(decision, roe_path)
            print(f"decision written to:              {roe_path}")
        except OSError as exc:
            print(f"WARNING: Could not write decision JSON: {exc}", file=sys.stderr)

        try:
            archive_path = _archive_decision(decision, _ARCHIVE_DIR)
            print(f"decision archived to:             {archive_path}")
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
