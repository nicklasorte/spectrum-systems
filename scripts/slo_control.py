#!/usr/bin/env python3
"""Run BR SLO control evaluation across BE, BF, and BG outputs.

Usage
-----
    # Evaluate with BE inputs only:
    python scripts/slo_control.py --be-input run1/nrr.json --be-input run2/nrr.json

    # Evaluate with BE, BF, and BG:
    python scripts/slo_control.py \\
        --be-input run1/nrr.json \\
        --bf-input comparison/cri.json \\
        --bg-input evidence/wpe.json

    # Specify output directory:
    python scripts/slo_control.py \\
        --be-input run1/nrr.json \\
        --output-dir outputs/slo/

Outputs
-------
- Prints a concise operator summary to stdout.
- Writes slo_evaluation.json to the chosen output directory
  (default: current working directory).
- Archives the evaluation artifact to data/slo_evaluations/.

Exit codes
----------
0   healthy — all SLIs >=0.95 and burn_rate <=0.2
1   degraded — at least one SLI is in the degraded band (0.85–0.95)
2   violated — at least one SLI is <0.85 or burn_rate >0.2
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

from spectrum_systems.modules.runtime.slo_control import run_slo_control  # noqa: E402

_ARCHIVE_DIR = _REPO_ROOT / "data" / "slo_evaluations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persist(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _archive_evaluation(artifact: Dict[str, Any], archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / f"slo_evaluation_{stamp}.json"
    suffix = 1
    while target.exists():
        target = archive_dir / f"slo_evaluation_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return target


def _print_summary(result: Dict[str, Any]) -> None:
    artifact = result.get("slo_evaluation") or {}
    slo_status = result.get("slo_status", "unknown")
    allowed = result.get("allowed_to_proceed", False)

    print(f"slo_status:          {slo_status}")
    print(f"allowed_to_proceed:  {allowed}")

    slis = artifact.get("slis") or {}
    print(f"completeness_sli:    {slis.get('completeness', 'n/a')}")
    print(f"timeliness_sli:      {slis.get('timeliness', 'n/a')}")
    print(f"traceability_sli:    {slis.get('traceability', 'n/a')}")

    eb = artifact.get("error_budget") or {}
    print(f"error_budget:        remaining={eb.get('remaining', 'n/a')}  "
          f"burn_rate={eb.get('burn_rate', 'n/a')}")

    violations = artifact.get("violations") or []
    if violations:
        print("violations:")
        for v in violations:
            print(f"  [{v['severity'].upper()}] {v['sli']}: {v['description']}")
    else:
        print("violations:          []")

    load_errors = result.get("load_errors") or []
    if load_errors:
        print("load_errors:")
        for e in load_errors:
            print(f"  {e}", file=sys.stderr)

    schema_errors = result.get("schema_errors") or []
    if schema_errors:
        print("schema_errors:")
        for e in schema_errors:
            print(f"  {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="BR SLO control evaluation across BE, BF, and BG outputs (Prompt BR)."
    )
    parser.add_argument(
        "--be-input",
        dest="be_inputs",
        action="append",
        metavar="PATH",
        default=[],
        help="Path to a BE normalized_run_result.json artifact. Can be specified multiple times.",
    )
    parser.add_argument(
        "--bf-input",
        dest="bf_input",
        metavar="PATH",
        default=None,
        help="Path to the BF cross_run_intelligence_decision.json artifact (optional).",
    )
    parser.add_argument(
        "--bg-input",
        dest="bg_input",
        metavar="PATH",
        default=None,
        help="Path to the BG working_paper_evidence_pack.json artifact (optional).",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Directory to write output artifacts (default: current working directory).",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    # Run SLO evaluation
    try:
        result = run_slo_control(
            be_inputs=args.be_inputs or [],
            bf_input=args.bf_input or None,
            bg_input=args.bg_input or None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Unexpected failure during SLO evaluation: {exc}", file=sys.stderr)
        return 2

    _print_summary(result)

    artifact = result.get("slo_evaluation")

    # Write output
    if artifact:
        out_path = output_dir / "slo_evaluation.json"
        try:
            _persist(artifact, out_path)
            print(f"\nslo_evaluation written to:  {out_path}")
        except OSError as exc:
            print(f"WARNING: Could not write slo_evaluation.json: {exc}", file=sys.stderr)

        try:
            archive_path = _archive_evaluation(artifact, _ARCHIVE_DIR)
            print(f"slo_evaluation archived to: {archive_path}")
        except OSError as exc:
            print(f"WARNING: Could not archive slo_evaluation: {exc}", file=sys.stderr)

    # Exit codes
    slo_status = result.get("slo_status", "violated")
    if slo_status == "healthy":
        return 0
    if slo_status == "degraded":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
