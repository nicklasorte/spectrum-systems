#!/usr/bin/env python3
"""
run_working_paper_engine.py — CLI for the Working Paper Engine.

Usage:
    python scripts/run_working_paper_engine.py \\
        --inputs <path-to-inputs.json> \\
        --output <path-to-output.json> \\
        [--pretty-report-out <path-to-report.md>]

Or pass inputs as a JSON string directly:
    python scripts/run_working_paper_engine.py \\
        --inputs '{"title": "...", "transcripts": [...]}' \\
        --output bundle.json

Exit codes:
    0 — success (validation may include warnings, but no errors)
    1 — validation errors or schema failures
    2 — runtime / input errors
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Allow running from repo root without installing the package
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.working_paper_engine.artifacts import (
    bundle_to_dict,
    bundle_to_markdown,
    validate_bundle_schema,
)
from spectrum_systems.modules.working_paper_engine.service import (
    inputs_from_dict,
    run_pipeline,
)


def _load_inputs(inputs_arg: str) -> dict:
    """Load inputs from a file path or a JSON string."""
    # Try as file path first (guarded against filenames that are too long)
    try:
        path = Path(inputs_arg)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                print(f"ERROR: Could not parse inputs file as JSON: {exc}", file=sys.stderr)
                sys.exit(2)
    except OSError:
        # Filename too long or other OS error — treat as inline JSON
        pass
    # Try as inline JSON string
    try:
        return json.loads(inputs_arg)
    except json.JSONDecodeError:
        print(
            f"ERROR: --inputs must be a valid file path or a JSON string. "
            f"Got: {inputs_arg[:80]!r}...",
            file=sys.stderr,
        )
        sys.exit(2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Working Paper Engine — generate federal spectrum-study working papers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--inputs",
        required=True,
        metavar="PATH_OR_JSON",
        help="Path to a JSON inputs file, or a JSON string.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output path for the governed JSON bundle.",
    )
    parser.add_argument(
        "--pretty-report-out",
        metavar="PATH",
        default=None,
        help="Optional path to write a human-readable Markdown version of the report.",
    )
    args = parser.parse_args(argv)

    # ── Load inputs ──────────────────────────────────────────────────────────
    print("Loading inputs ...", flush=True)
    raw_inputs = _load_inputs(args.inputs)

    try:
        inputs = inputs_from_dict(raw_inputs)
    except Exception as exc:
        print(f"ERROR: Failed to parse inputs: {exc}", file=sys.stderr)
        return 2

    print(f"  Title: {inputs.title!r}")
    print(f"  Source documents: {len(inputs.source_documents)}")
    print(f"  Transcripts: {len(inputs.transcripts)}")
    print(f"  Study plan excerpts: {len(inputs.study_plan_excerpts)}")

    # ── Run pipeline ─────────────────────────────────────────────────────────
    print("Running pipeline: OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE ...", flush=True)
    try:
        bundle = run_pipeline(inputs)
    except Exception as exc:
        print(f"ERROR: Pipeline failed: {exc}", file=sys.stderr)
        return 2

    print(f"  Artifact ID: {bundle.artifact_id}")
    print(f"  Sections generated: {len(bundle.report.sections)}")
    print(f"  FAQ items: {len(bundle.faq)}")
    print(f"  Gap register entries: {len(bundle.gap_register)}")
    rr = bundle.results_readiness
    print(
        f"  Results ready: {'Yes' if rr.quantitative_results_available else 'No'}"
    )
    v = bundle.validation
    print(
        f"  Validation: {len(v.passes)} pass / {len(v.warnings)} warning / {len(v.errors)} error"
    )

    # ── Serialize ─────────────────────────────────────────────────────────────
    bundle_dict = bundle_to_dict(bundle)

    # ── Schema validation ────────────────────────────────────────────────────
    print("Validating output bundle against schema ...", flush=True)
    schema_errors = validate_bundle_schema(bundle_dict)
    if schema_errors:
        print("WARNING: Bundle schema validation issues:", file=sys.stderr)
        for err in schema_errors[:10]:
            print(f"  - {err}", file=sys.stderr)

    # ── Write output ─────────────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bundle_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Bundle written to: {output_path}")

    # ── Markdown output ───────────────────────────────────────────────────────
    if args.pretty_report_out:
        md_path = Path(args.pretty_report_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(bundle_to_markdown(bundle), encoding="utf-8")
        print(f"Markdown report written to: {md_path}")

    # ── Exit code ─────────────────────────────────────────────────────────────
    if v.errors:
        print(
            f"FAILURE: {len(v.errors)} validation error(s) found. "
            "Review bundle for details.",
            file=sys.stderr,
        )
        return 1

    if v.warnings:
        print(f"SUCCESS with {len(v.warnings)} warning(s).")
    else:
        print("SUCCESS.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
