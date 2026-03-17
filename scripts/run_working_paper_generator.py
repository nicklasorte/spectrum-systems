#!/usr/bin/env python3
"""
run_working_paper_generator.py

CLI entry point for the working_paper_generator pipeline.

Usage
-----
python scripts/run_working_paper_generator.py \\
    --transcript path/to/transcript.txt \\
    [--minutes path/to/minutes.txt] \\
    [--draft path/to/existing_draft.json] \\
    [--output path/to/output.json] \\
    [--format json|markdown] \\
    [--meeting-title "Meeting Title"]

All inputs are plain text or JSON files.  The output is a JSON or Markdown
rendering of a WorkingPaperDraft artifact.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

# Allow the script to be run from the repo root without installation.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from working_paper_generator.transcript_parser import parse_transcript  # noqa: E402
from working_paper_generator.paper_state_reader import read_paper_state, read_plain_text  # noqa: E402
from working_paper_generator.meeting_delta_engine import compute_delta  # noqa: E402
from working_paper_generator.argument_builder import build_arguments  # noqa: E402
from working_paper_generator.question_engine import extract_questions  # noqa: E402
from working_paper_generator.readiness_scorer import score_readiness  # noqa: E402
from working_paper_generator.patch_generator import generate_patch  # noqa: E402
from working_paper_generator.draft_writer import write_draft  # noqa: E402
from working_paper_generator.schemas import PaperState, ReadinessReport  # noqa: E402


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _to_dict(obj: object) -> object:
    """Recursively convert dataclass instances to plain dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _render_markdown(draft: object) -> str:
    """Render a WorkingPaperDraft as a Markdown document."""
    d = _to_dict(draft)
    lines: list[str] = []
    lines.append(f"# {d.get('title', 'Working Paper Draft')}")
    lines.append(f"\n**Paper ID:** {d.get('paper_id')}  ")
    lines.append(f"**Version:** {d.get('version')}  ")
    if d.get("source_transcript"):
        lines.append(f"**Source Transcript:** {d['source_transcript']}  ")
    if d.get("source_minutes"):
        lines.append(f"**Source Minutes:** {d['source_minutes']}  ")
    lines.append("")

    for sec in d.get("sections", []):
        lines.append(f"## {sec['title']}")
        lines.append(f"\n*Section ID:* `{sec['section_id']}` | *Status:* {sec['status']}\n")
        lines.append(sec.get("content", "") or "_No content yet._")
        if sec.get("open_issues"):
            lines.append("\n**Open Issues:**")
            for issue in sec["open_issues"]:
                lines.append(f"- {issue}")
        lines.append("")

    # Open questions
    questions = d.get("open_questions", [])
    if questions:
        lines.append("## Open Questions\n")
        for q in questions:
            status_tag = f"[{q['resolution_status']}]"
            raised = f"(raised by {q['raised_by']})" if q.get("raised_by") else ""
            lines.append(f"- **{q['question_id']}** {status_tag} {raised}: {q['text']}")
        lines.append("")

    # Readiness
    readiness = d.get("readiness", {})
    lines.append("## Readiness Assessment\n")
    lines.append(f"**Overall score:** {readiness.get('overall_score', 0.0):.2f}  ")
    ready = "✅ Ready to draft" if readiness.get("ready_to_draft") else "⚠️ Not yet ready"
    lines.append(f"**Status:** {ready}\n")
    for sr in readiness.get("sections", []):
        lines.append(
            f"- `{sr['section_id']}` — score: {sr['score']:.2f} — {sr['rationale']}"
        )
        for bq in sr.get("blocking_questions", []):
            lines.append(f"  - ⛔ {bq}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    transcript_path: str,
    minutes_path: str | None,
    draft_path: str | None,
    meeting_title: str,
) -> object:
    """Execute the full working paper generator pipeline.

    Returns a :class:`~working_paper_generator.schemas.WorkingPaperDraft`.
    """
    # 1. Parse transcript
    transcript_text = Path(transcript_path).read_text(encoding="utf-8")
    transcript = parse_transcript(transcript_text, meeting_title=meeting_title)

    # 2. Read existing paper state (optional)
    paper_state: PaperState | None = None
    if draft_path:
        paper_state = read_paper_state(draft_path)

    # 3. Incorporate minutes into paper state if no existing draft was given
    if minutes_path and paper_state is None:
        minutes_text = Path(minutes_path).read_text(encoding="utf-8")
        paper_state = read_plain_text(minutes_text, minutes_path)

    # 4. Compute meeting delta
    delta = compute_delta(transcript, paper_state)

    # 5. Build arguments
    arguments = build_arguments(transcript, paper_state)

    # 6. Extract questions
    questions = extract_questions(transcript, paper_state)

    # 7. Score readiness (requires a paper_state; scaffold a minimal one if absent)
    if paper_state is not None:
        readiness = score_readiness(paper_state, delta, questions)
    else:
        readiness = ReadinessReport(overall_score=0.0, sections=[], ready_to_draft=False)

    # 8. Generate patch
    patch = generate_patch(delta, paper_state, meeting_title=meeting_title)

    # 9. Write draft
    draft = write_draft(
        patch=patch,
        paper_state=paper_state,
        arguments=arguments,
        questions=questions,
        readiness=readiness,
        source_transcript=transcript_path,
        source_minutes=minutes_path,
    )

    return draft


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--transcript",
        required=True,
        metavar="PATH",
        help="Path to the meeting transcript file (plain text).",
    )
    parser.add_argument(
        "--minutes",
        default=None,
        metavar="PATH",
        help="Optional path to meeting minutes file (plain text or JSON).",
    )
    parser.add_argument(
        "--draft",
        default=None,
        metavar="PATH",
        help="Optional path to an existing working paper draft (JSON or Markdown).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Output file path.  When omitted the result is written to stdout.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--meeting-title",
        default="Meeting",
        metavar="TITLE",
        help="Human-readable meeting title used for attribution (default: 'Meeting').",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    draft = run_pipeline(
        transcript_path=args.transcript,
        minutes_path=args.minutes,
        draft_path=args.draft,
        meeting_title=args.meeting_title,
    )

    if args.format == "markdown":
        output_text = _render_markdown(draft)
    else:
        output_text = json.dumps(_to_dict(draft), indent=2, sort_keys=True)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
