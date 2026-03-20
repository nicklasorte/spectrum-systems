#!/usr/bin/env python3
"""
run_working_paper_engine.py

CLI for the working_paper_engine module.

Ingests source documents, meeting transcripts, and study plan / tasking
guidance from a JSON inputs file or inline JSON, then runs the full
OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE pipeline and emits a governed
JSON output bundle.

Usage
-----
    python scripts/run_working_paper_engine.py \\
        --inputs path/to/inputs.json \\
        --output path/to/bundle.json \\
        [--pretty-report-out path/to/report.md]

Input JSON format
-----------------
{
  "title_hint": "...",
  "study_id": "...",
  "quantitative_results_available": false,
  "source_documents": [
    {"content": "...", "artifact_id": "...", "source_locator": "...", "title": "..."}
  ],
  "transcripts": [
    {"content": "...", "artifact_id": "...", "speaker": "...", "meeting_title": "..."}
  ],
  "study_plans": [
    {"content": "...", "artifact_id": "...", "study_title": "..."}
  ]
}

Exit codes
----------
0   Success (bundle written; validation may have warnings)
1   Input or runtime error
2   Schema validation failed on output bundle
3   Validation errors in the output bundle
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so spectrum_systems is importable.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.working_paper_engine.artifacts import (  # noqa: E402
    render_markdown,
    validate_bundle_schema,
)
from spectrum_systems.modules.working_paper_engine.models import (  # noqa: E402
    EngineInputs,
    ProvenanceMode,
    SourceDocumentExcerpt,
    SourceType,
    StudyPlanExcerpt,
    TranscriptExcerpt,
)
from spectrum_systems.modules.working_paper_engine.service import run_pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------


def _load_inputs_from_dict(data: dict) -> EngineInputs:
    """Parse a dict (from JSON) into EngineInputs."""
    source_documents = [
        SourceDocumentExcerpt(
            content=doc.get("content", ""),
            artifact_id=doc.get("artifact_id", ""),
            source_locator=doc.get("source_locator", ""),
            title=doc.get("title", ""),
            document_date=doc.get("document_date", ""),
        )
        for doc in data.get("source_documents", [])
    ]

    transcripts = [
        TranscriptExcerpt(
            content=t.get("content", ""),
            artifact_id=t.get("artifact_id", ""),
            source_locator=t.get("source_locator", ""),
            speaker=t.get("speaker", ""),
            meeting_title=t.get("meeting_title", ""),
            meeting_date=t.get("meeting_date", ""),
        )
        for t in data.get("transcripts", [])
    ]

    study_plans = [
        StudyPlanExcerpt(
            content=p.get("content", ""),
            artifact_id=p.get("artifact_id", ""),
            source_locator=p.get("source_locator", ""),
            study_title=p.get("study_title", ""),
            study_date=p.get("study_date", ""),
        )
        for p in data.get("study_plans", [])
    ]

    return EngineInputs(
        source_documents=source_documents,
        transcripts=transcripts,
        study_plans=study_plans,
        title_hint=data.get("title_hint", ""),
        study_id=data.get("study_id", ""),
    )


def _load_inputs(inputs_arg: str) -> tuple[dict, EngineInputs]:
    """Load inputs from a file path or inline JSON string.

    Returns (raw_data_dict, EngineInputs).
    """
    raw: dict

    path = Path(inputs_arg)
    is_file = False
    try:
        is_file = path.exists() and path.is_file()
    except OSError:
        # Path string is too long to be a valid filesystem path; treat as inline JSON
        is_file = False

    if is_file:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: Could not parse inputs JSON file: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        # Try parsing as inline JSON
        try:
            raw = json.loads(inputs_arg)
        except json.JSONDecodeError:
            print(
                f"ERROR: --inputs must be a path to a JSON file or inline JSON. "
                f"Could not find file at '{inputs_arg}' and could not parse as JSON.",
                file=sys.stderr,
            )
            sys.exit(1)

    return raw, _load_inputs_from_dict(raw)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_working_paper_engine",
        description=(
            "Generate a federal spectrum-study working paper bundle using the "
            "working_paper_engine pipeline (OBSERVE → INTERPRET → SYNTHESIZE → VALIDATE)."
        ),
    )
    parser.add_argument(
        "--inputs",
        required=True,
        metavar="PATH_OR_JSON",
        help="Path to a JSON inputs file, or an inline JSON string.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Path to write the governed JSON output bundle.",
    )
    parser.add_argument(
        "--pretty-report-out",
        metavar="PATH",
        default=None,
        help="Optional: path to write a human-readable Markdown version of the report.",
    )
    parser.add_argument(
        "--provenance-mode",
        choices=["best_effort", "strict", "none"],
        default="best_effort",
        help="Provenance tracking mode (default: best_effort).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ----------------------------------------------------------------
    # Load inputs
    # ----------------------------------------------------------------
    print("[1/5] Loading inputs...")
    raw_data, inputs = _load_inputs(args.inputs)
    quant_available = bool(raw_data.get("quantitative_results_available", False))
    provenance_mode = ProvenanceMode(args.provenance_mode)

    n_docs = len(inputs.source_documents)
    n_transcripts = len(inputs.transcripts)
    n_plans = len(inputs.study_plans)
    print(
        f"       Source documents: {n_docs}, Transcripts: {n_transcripts}, "
        f"Study plans: {n_plans}"
    )

    # ----------------------------------------------------------------
    # Run pipeline
    # ----------------------------------------------------------------
    print("[2/5] Running OBSERVE stage...")
    print("[3/5] Running INTERPRET stage...")
    print("[4/5] Running SYNTHESIZE stage...")
    print("[5/5] Running VALIDATE stage...")

    try:
        bundle = run_pipeline(
            inputs=inputs,
            quantitative_results_available=quant_available,
            provenance_mode=provenance_mode,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # ----------------------------------------------------------------
    # Validate bundle against JSON Schema
    # ----------------------------------------------------------------
    schema_errors = validate_bundle_schema(bundle)
    if schema_errors:
        print(
            f"ERROR: Output bundle failed schema validation ({len(schema_errors)} error(s)):",
            file=sys.stderr,
        )
        for err in schema_errors[:5]:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(2)

    # ----------------------------------------------------------------
    # Write output bundle
    # ----------------------------------------------------------------
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nBundle written to: {output_path}")

    # ----------------------------------------------------------------
    # Write optional Markdown report
    # ----------------------------------------------------------------
    if args.pretty_report_out:
        md_path = Path(args.pretty_report_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(bundle), encoding="utf-8")
        print(f"Markdown report written to: {md_path}")

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    validation = bundle.get("validation", {})
    n_errors = len(validation.get("errors", []))
    n_warnings = len(validation.get("warnings", []))
    n_passes = len(validation.get("passes", []))
    n_gaps = len(bundle.get("gap_register", []))
    n_faq = len(bundle.get("faq", []))

    print(
        f"\nSummary: {n_passes} pass(es), {n_warnings} warning(s), {n_errors} error(s) | "
        f"{n_gaps} gap(s) | {n_faq} FAQ item(s)"
    )

    if n_errors > 0:
        print("VALIDATION ERRORS detected. See bundle validation section.", file=sys.stderr)
        for err in validation.get("errors", []):
            print(f"  ERROR: {err}", file=sys.stderr)
        sys.exit(3)

    print("Done.")


if __name__ == "__main__":
    main()
