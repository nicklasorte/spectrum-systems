#!/usr/bin/env python3
"""Run BG working paper evidence pack synthesis.

Usage
-----
    # Synthesize from BE inputs only:
    python scripts/working_paper_synthesis.py --be-input run1/nrr.json --be-input run2/nrr.json

    # Synthesize from BE and BF:
    python scripts/working_paper_synthesis.py \\
        --be-input run1/nrr.json --be-input run2/nrr.json \\
        --bf-input comparison/crc.json

    # Specify output directory:
    python scripts/working_paper_synthesis.py \\
        --be-input run1/nrr.json \\
        --output-dir outputs/evidence/

Outputs
-------
- Prints a concise operator summary to stdout.
- Writes working_paper_evidence_pack.json and working_paper_synthesis_decision.json
  to the chosen output directory (default: current working directory).
- Archives decision artifact to data/working_paper_synthesis_decisions/.

Exit codes
----------
0   pass — synthesis complete; no error or warning findings
1   warning — synthesis complete but warning-level findings present
2   fail — missing or invalid inputs, schema failures, or error-level findings
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.working_paper_synthesis import (  # noqa: E402
    synthesize_working_paper_evidence,
)

_ARCHIVE_DIR = _REPO_ROOT / "data" / "working_paper_synthesis_decisions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persist(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _archive_decision(decision: Dict[str, Any], archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / f"working_paper_synthesis_decision_{stamp}.json"
    suffix = 1
    while target.exists():
        target = archive_dir / f"working_paper_synthesis_decision_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return target


def _print_summary(result: Dict[str, Any]) -> None:
    decision = result.get("working_paper_synthesis_decision") or {}
    pack = result.get("working_paper_evidence_pack")

    print(f"overall_status:  {decision.get('overall_status', 'unknown')}")
    print(f"failure_type:    {decision.get('failure_type', 'unknown')}")

    if pack:
        print(f"study_type:      {pack.get('study_type', 'unknown')}")
        print(f"source_artifacts:{len(pack.get('source_artifacts', []))}")
        secs = pack.get("section_evidence") or []
        populated = sum(1 for s in secs if s.get("synthesis_status") == "populated")
        partial = sum(1 for s in secs if s.get("synthesis_status") == "partial")
        empty = sum(1 for s in secs if s.get("synthesis_status") == "empty")
        print(f"sections:        {populated} populated / {partial} partial / {empty} empty")
        print(f"ranked_findings: {len(pack.get('ranked_findings', []))}")
        print(f"caveats:         {len(pack.get('caveats', []))}")
        print(f"followup_q:      {len(pack.get('followup_questions', []))}")
    else:
        print("evidence_pack:   not produced (hard failure)")

    findings = result.get("findings") or []
    if findings:
        print("findings:")
        for f in findings:
            print(f"  [{f['severity'].upper()}] {f['code']}: {f['message']}")
    else:
        print("findings:        []")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="BG: Synthesize working paper evidence pack from BE/BF artifacts."
    )
    parser.add_argument(
        "--be-input",
        metavar="PATH",
        action="append",
        dest="be_inputs",
        default=[],
        help="Path to a normalized_run_result (BE) JSON file. May be specified multiple times.",
    )
    parser.add_argument(
        "--bf-input",
        metavar="PATH",
        dest="bf_input",
        default=None,
        help="Path to a cross_run_comparison (BF) JSON file (optional).",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        dest="output_dir",
        default=None,
        help="Directory to write output JSON files (default: current working directory).",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()

    result = synthesize_working_paper_evidence(
        be_inputs=args.be_inputs if args.be_inputs else None,
        bf_input=args.bf_input,
    )

    _print_summary(result)

    decision = result.get("working_paper_synthesis_decision")
    pack = result.get("working_paper_evidence_pack")

    # Write outputs
    if pack is not None:
        _persist(pack, output_dir / "working_paper_evidence_pack.json")
        print(f"evidence_pack written:   {output_dir / 'working_paper_evidence_pack.json'}")

    if decision is not None:
        _persist(decision, output_dir / "working_paper_synthesis_decision.json")
        print(f"synthesis_decision written: {output_dir / 'working_paper_synthesis_decision.json'}")
        archive_path = _archive_decision(decision, _ARCHIVE_DIR)
        print(f"decision archived:       {archive_path}")

    # Exit code
    status = (decision or {}).get("overall_status", "fail")
    if status == "pass":
        return 0
    if status == "warning":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
