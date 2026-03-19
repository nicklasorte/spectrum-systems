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

    # Evaluate with lineage registry and explicit parent artifact IDs:
    python scripts/slo_control.py \\
        --be-input run1/nrr.json \\
        --lineage-dir lineage/artifacts/ \\
        --parent-id DEC-001 \\
        --parent-id SYN-001 \\
        --output-dir outputs/slo/

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


def _load_lineage_registry(lineage_dir: str) -> Dict[str, Any]:
    """Load all *.json files from *lineage_dir* into a lineage registry.

    Each JSON file is expected to be an artifact metadata dict containing at
    least an ``artifact_id`` field.  The registry maps artifact_id → artifact
    metadata.

    Raises
    ------
    SystemExit
        When *lineage_dir* does not exist, contains no JSON files, or any file
        cannot be parsed.  Explicit failure is intentional: a missing or
        broken lineage registry must never silently pretend lineage is healthy.
    """
    dpath = Path(lineage_dir)
    if not dpath.is_dir():
        print(
            f"ERROR: --lineage-dir '{lineage_dir}' is not a directory or does not exist.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    json_files = sorted(dpath.glob("*.json"))
    if not json_files:
        print(
            f"ERROR: --lineage-dir '{lineage_dir}' contains no *.json files. "
            "Lineage registry cannot be empty.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    registry: Dict[str, Any] = {}
    for fpath in json_files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"ERROR: Failed to load lineage artifact from '{fpath}': {exc}",
                file=sys.stderr,
            )
            raise SystemExit(2)

        artifact_id = data.get("artifact_id")
        if not artifact_id:
            print(
                f"ERROR: Lineage artifact in '{fpath}' is missing 'artifact_id'. "
                "All lineage artifacts must carry a deterministic ID.",
                file=sys.stderr,
            )
            raise SystemExit(2)

        registry[str(artifact_id)] = data

    return registry


def _print_summary(result: Dict[str, Any]) -> None:
    artifact = result.get("slo_evaluation") or {}
    slo_status = result.get("slo_status", "unknown")
    allowed = result.get("allowed_to_proceed", False)

    print(f"slo_status:                  {slo_status}")
    print(f"allowed_to_proceed:          {allowed}")

    slis = artifact.get("slis") or {}
    print(f"completeness_sli:            {slis.get('completeness', 'n/a')}")
    print(f"timeliness_sli:              {slis.get('timeliness', 'n/a')}")
    print(f"traceability_sli:            {slis.get('traceability', 'n/a')}")
    print(f"traceability_integrity_sli:  {slis.get('traceability_integrity', 'n/a')}")

    eb = artifact.get("error_budget") or {}
    print(f"error_budget:                remaining={eb.get('remaining', 'n/a')}  "
          f"burn_rate={eb.get('burn_rate', 'n/a')}")

    lineage_valid = artifact.get("lineage_valid")
    if lineage_valid is None:
        print("lineage_valid:               [absent — lineage not assessed]")
    else:
        print(f"lineage_valid:               {lineage_valid}")

    lvm = artifact.get("lineage_validation_mode")
    if lvm is None:
        print("lineage_validation_mode:     [absent]")
    else:
        print(f"lineage_validation_mode:     {lvm}")

    ldef = artifact.get("lineage_defaulted")
    if ldef is None:
        print("lineage_defaulted:           [absent]")
    else:
        print(f"lineage_defaulted:           {ldef}")

    parent_ids = artifact.get("parent_artifact_ids")
    if parent_ids is None:
        print("parent_artifact_ids:         [absent]")
    else:
        print(f"parent_artifact_ids:         {parent_ids}")

    lineage_errors = result.get("lineage_errors") or []
    if lineage_errors:
        print(f"lineage_errors ({len(lineage_errors)}):", file=sys.stderr)
        for e in lineage_errors:
            print(f"  {e}", file=sys.stderr)
    else:
        print("lineage_errors:              []")

    violations = artifact.get("violations") or []
    if violations:
        print("violations:")
        for v in violations:
            print(f"  [{v['severity'].upper()}] {v['sli']}: {v['description']}")
    else:
        print("violations:                  []")

    load_errors = result.get("load_errors") or []
    if load_errors:
        print("load_errors:", file=sys.stderr)
        for e in load_errors:
            print(f"  {e}", file=sys.stderr)

    schema_errors = result.get("schema_errors") or []
    if schema_errors:
        print(f"Schema validation errors ({len(schema_errors)}):", file=sys.stderr)
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
        "--lineage-dir",
        dest="lineage_dir",
        metavar="PATH",
        default=None,
        help=(
            "Directory containing lineage-relevant JSON artifacts to load into the "
            "lineage registry.  When provided, all *.json files in the directory are "
            "loaded and used to evaluate traceability_integrity.  If any file cannot "
            "be parsed the command exits with code 2."
        ),
    )
    parser.add_argument(
        "--parent-id",
        dest="parent_ids",
        action="append",
        metavar="VALUE",
        default=[],
        help=(
            "Explicit parent artifact ID for this SLO output (e.g. a decision or "
            "synthesis artifact ID).  Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default=None,
        help="Directory to write output artifacts (default: current working directory).",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()

    # Load lineage registry when --lineage-dir is provided.
    # Failure is explicit and fatal — never silently pretend lineage is healthy.
    lineage_registry: Optional[Dict[str, Any]] = None
    if args.lineage_dir:
        lineage_registry = _load_lineage_registry(args.lineage_dir)

    parent_artifact_ids: Optional[List[str]] = args.parent_ids if args.parent_ids else None

    # Run SLO evaluation
    try:
        result = run_slo_control(
            be_inputs=args.be_inputs or [],
            bf_input=args.bf_input or None,
            bg_input=args.bg_input or None,
            lineage_registry=lineage_registry,
            parent_artifact_ids=parent_artifact_ids,
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
