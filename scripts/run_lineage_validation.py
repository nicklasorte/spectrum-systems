#!/usr/bin/env python3
"""
Lineage Validation CLI — scripts/run_lineage_validation.py

Reads a directory of artifact JSON files, builds the full lineage graph,
validates all artifacts, and writes a structured report.

Usage
-----
    python scripts/run_lineage_validation.py --dir <artifacts_directory>
    python scripts/run_lineage_validation.py --dir artifacts/ --output outputs/lineage_validation.json

Exit Codes
----------
0  All artifacts valid — lineage complete and consistent.
1  Lineage errors detected (broken chains, orphans, missing parents, etc.).
2  Schema errors detected (artifact files fail governed JSON Schema).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spectrum_systems.modules.runtime.artifact_lineage import (
    build_full_lineage_graph,
    detect_lineage_gaps,
    validate_against_schema,
    validate_full_registry,
)

_DEFAULT_OUTPUT = _ROOT / "outputs" / "lineage_validation.json"


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------


def load_artifacts_from_directory(directory: Path) -> tuple:
    """Load all *.json files from *directory* into a registry dict.

    Parameters
    ----------
    directory:
        Path to a directory containing artifact JSON files.

    Returns
    -------
    tuple[dict, list]
        ``(registry, parse_errors)`` where *registry* maps artifact_id →
        artifact metadata dict and *parse_errors* is a list of error strings
        for files that could not be parsed.

    Raises
    ------
    SystemExit
        With code 2 if directory does not exist.
    """
    if not directory.exists():
        print(f"ERROR: Directory not found: {directory}", file=sys.stderr)
        sys.exit(2)

    registry: dict = {}
    parse_errors: list = []

    for json_file in sorted(directory.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            artifact_id = data.get("artifact_id")
            if not artifact_id:
                parse_errors.append(
                    f"{json_file.name}: missing 'artifact_id' field"
                )
                continue
            registry[artifact_id] = data
        except (json.JSONDecodeError, OSError) as exc:
            parse_errors.append(f"{json_file.name}: {exc}")

    return registry, parse_errors


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def build_validation_report(
    registry: dict,
    parse_errors: list,
) -> dict:
    """Run full validation and build structured report.

    Parameters
    ----------
    registry:
        artifact_id → metadata mapping.
    parse_errors:
        Errors encountered while parsing input files.

    Returns
    -------
    dict
        Structured validation report.
    """
    # Schema validation
    schema_errors: dict = {}
    for aid, meta in registry.items():
        valid, errors = validate_against_schema(meta)
        if not valid:
            schema_errors[aid] = errors

    # Full lineage validation
    lineage_report = validate_full_registry(registry)

    # Gap detection
    gap_report = detect_lineage_gaps(registry)

    # Full graph
    graph = build_full_lineage_graph(registry)

    return {
        "summary": {
            "total_artifacts": len(registry),
            "parse_errors": len(parse_errors),
            "schema_errors": len(schema_errors),
            "lineage_errors": lineage_report["total_errors"],
            "orphan_artifacts": len(gap_report["orphan_artifacts"]),
            "missing_parent_refs": len(gap_report["missing_parents"]),
            "depth_inconsistencies": len(gap_report["depth_inconsistencies"]),
            "valid": (
                len(parse_errors) == 0
                and len(schema_errors) == 0
                and lineage_report["valid"]
            ),
        },
        "parse_errors": parse_errors,
        "schema_errors": schema_errors,
        "lineage_validation": lineage_report,
        "gap_report": gap_report,
        "lineage_graph": {k: sorted(v) for k, v in sorted(graph.items())},
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate artifact lineage from a directory of JSON files."
    )
    parser.add_argument(
        "--dir",
        required=True,
        type=Path,
        help="Directory containing artifact JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output report path (default: {_DEFAULT_OUTPUT}).",
    )
    args = parser.parse_args(argv)

    registry, parse_errors = load_artifacts_from_directory(args.dir)

    report = build_validation_report(registry, parse_errors)

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Report written to: {args.output}")

    # Determine exit code
    summary = report["summary"]
    if summary["schema_errors"] > 0 or summary["parse_errors"] > 0:
        print("RESULT: Schema errors detected.", file=sys.stderr)
        return 2
    if not summary["valid"]:
        print("RESULT: Lineage errors detected.", file=sys.stderr)
        return 1

    print("RESULT: All artifacts valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
