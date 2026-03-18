#!/usr/bin/env python3
"""
Feedback Session CLI — scripts/run_feedback_session.py

Interactive command-line tool for conducting structured human feedback review
sessions over AI-generated artifacts.

Usage
-----
    python scripts/run_feedback_session.py --artifact ARTIFACT_ID --reviewer USER_ID

The script:
1. Prompts the reviewer for artifact metadata (type, role).
2. Loads or accepts the artifact document.
3. Extracts claim-level units from the artifact.
4. Iterates through claims, prompting the reviewer for structured feedback.
5. Persists each feedback record as it is collected.
6. Prints a session summary on exit.

Run with ``--help`` for full option descriptions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repo root is on sys.path when run as a script
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.feedback.human_feedback import FeedbackStore
from spectrum_systems.modules.feedback.review_session import ReviewSession

# ---------------------------------------------------------------------------
# Enum choices (mirrors schema)
# ---------------------------------------------------------------------------

_REVIEWER_ROLES = ["engineer", "policy", "legal", "leadership"]
_ACTIONS = ["accept", "minor_edit", "major_edit", "reject", "rewrite", "needs_support"]
_SOURCES_OF_TRUTH = [
    "transcript", "slides", "statute", "policy", "engineering_analysis", "external_reference"
]
_FAILURE_TYPES = [
    "extraction_error", "reasoning_error", "grounding_failure",
    "hallucination", "schema_violation", "unclear"
]
_SEVERITIES = ["low", "medium", "high", "critical"]
_ARTIFACT_TYPES = [
    "meeting_minutes", "working_paper", "slide_intelligence",
    "pass_result", "pass_chain_record", "context_bundle", "evaluation_result"
]

# ---------------------------------------------------------------------------
# Helper I/O utilities
# ---------------------------------------------------------------------------


def _prompt_choice(prompt: str, choices: list, default: Optional[str] = None) -> str:
    """Prompt the user to pick from a numbered list of choices."""
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        marker = " (default)" if choice == default else ""
        print(f"  {i}. {choice}{marker}")
    while True:
        raw = input("Enter number or value: ").strip()
        if not raw and default:
            return default
        if raw in choices:
            return raw
        try:
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        except ValueError:
            pass
        print(f"  Invalid choice. Please enter a number (1–{len(choices)}) or the value directly.")


def _prompt_text(prompt: str, required: bool = True) -> str:
    """Prompt for free text input."""
    while True:
        value = input(f"\n{prompt}: ").strip()
        if value:
            return value
        if not required:
            return ""
        print("  This field is required.")


def _prompt_bool(prompt: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer."""
    default_hint = "Y/n" if default else "y/N"
    raw = input(f"\n{prompt} [{default_hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------


def _load_artifact(artifact_path: Optional[str]) -> Dict[str, Any]:
    """Load an artifact from a JSON file path, or accept inline JSON."""
    if artifact_path:
        path = Path(artifact_path)
        if not path.exists():
            print(f"ERROR: Artifact file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return json.loads(path.read_text(encoding="utf-8"))

    print("\nNo --artifact-file provided.  Enter artifact JSON inline (end with a blank line):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    if not lines:
        print("ERROR: No artifact provided.", file=sys.stderr)
        sys.exit(1)
    return json.loads("\n".join(lines))


# ---------------------------------------------------------------------------
# Main review flow
# ---------------------------------------------------------------------------


def run_feedback_session(args: argparse.Namespace) -> None:
    """Execute the interactive feedback session."""
    print("\n" + "=" * 60)
    print("  Spectrum Systems — Human Feedback Review Session")
    print("=" * 60)

    artifact_id: str = args.artifact
    reviewer_id: str = args.reviewer

    # Reviewer role
    reviewer_role = args.role or _prompt_choice(
        "Reviewer role:", _REVIEWER_ROLES, default="engineer"
    )

    # Artifact type
    artifact_type = args.artifact_type or _prompt_choice(
        "Artifact type:", _ARTIFACT_TYPES, default="working_paper"
    )

    # Load artifact document
    artifact_doc = _load_artifact(args.artifact_file)

    # Ensure artifact doc has required fields for the store
    artifact_doc.setdefault("artifact_id", artifact_id)
    artifact_doc.setdefault("artifact_type", artifact_type)

    store = FeedbackStore()
    session = ReviewSession(
        artifact_id=artifact_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        artifact=artifact_doc,
        artifact_type=artifact_type,
        store=store,
    )

    session.start_session()

    if not session.claims:
        print("\nNo reviewable claims could be extracted from this artifact.")
        session.close_session()
        return

    print(f"\nExtracted {len(session.claims)} claim(s) from artifact '{artifact_id}'.")
    print("Review each claim and provide structured feedback.\n")
    print("(Press Enter to skip a claim.)\n")
    print("-" * 60)

    reviewed = 0
    for i, claim in enumerate(session.iterate_claims(), 1):
        print(f"\n[{i}/{len(session.claims)}] Claim ID: {claim.claim_id}")
        print(f"  Section:  {claim.section_id}")
        print(f"  Text:     {claim.claim_text}")

        skip = input("\n  Skip this claim? [y/N]: ").strip().lower()
        if skip in ("y", "yes"):
            print("  Skipped.")
            continue

        action = _prompt_choice("  Action:", _ACTIONS, default="accept")

        edited_text: Optional[str] = None
        if action in ("minor_edit", "major_edit", "rewrite"):
            edited_text = _prompt_text("  Provide corrected text")

        rationale = _prompt_text("  Rationale (why this action?)")
        source_of_truth = _prompt_choice(
            "  Source of truth:", _SOURCES_OF_TRUTH, default="transcript"
        )
        failure_type = _prompt_choice("  Failure type:", _FAILURE_TYPES, default="unclear")
        severity = _prompt_choice("  Severity:", _SEVERITIES, default="low")

        print("\n  Should this feedback trigger updates?")
        golden_dataset = _prompt_bool("    Update golden dataset?", default=False)
        prompts_update = _prompt_bool("    Update prompts?", default=False)
        retrieval_memory = _prompt_bool("    Update retrieval memory?", default=False)

        feedback = {
            "action": action,
            "edited_text": edited_text,
            "rationale": rationale,
            "source_of_truth": source_of_truth,
            "failure_type": failure_type,
            "severity": severity,
            "should_update": {
                "golden_dataset": golden_dataset,
                "prompts": prompts_update,
                "retrieval_memory": retrieval_memory,
            },
        }

        record = session.record_feedback(claim.claim_id, feedback)
        print(f"  ✓ Feedback recorded: {record.feedback_id}")
        reviewed += 1

    summary = session.close_session()

    print("\n" + "=" * 60)
    print("  Session Summary")
    print("=" * 60)
    print(f"  Artifact:        {summary['artifact_id']}")
    print(f"  Reviewer:        {summary['reviewer_id']} ({summary['reviewer_role']})")
    print(f"  Total claims:    {summary['total_claims']}")
    print(f"  Reviewed:        {summary['reviewed_claims']}")
    print(f"  Skipped:         {summary['skipped_claims']}")
    print(f"  Started:         {summary['started_at']}")
    print(f"  Closed:          {summary['closed_at']}")
    print(f"\n  Feedback IDs saved:")
    for fid in summary["feedback_ids"]:
        print(f"    - {fid}")
    print("=" * 60)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nSession summary written to: {out_path}")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_feedback_session.py",
        description=(
            "Conduct a structured human feedback review session over an AI-generated artifact."
        ),
    )
    parser.add_argument(
        "--artifact",
        required=True,
        metavar="ARTIFACT_ID",
        help="Unique identifier of the artifact to review.",
    )
    parser.add_argument(
        "--reviewer",
        required=True,
        metavar="USER_ID",
        help="Unique identifier of the reviewer.",
    )
    parser.add_argument(
        "--role",
        choices=_REVIEWER_ROLES,
        default=None,
        help="Reviewer role.  Prompted interactively if not provided.",
    )
    parser.add_argument(
        "--artifact-type",
        dest="artifact_type",
        choices=_ARTIFACT_TYPES,
        default=None,
        help="Artifact type.  Prompted interactively if not provided.",
    )
    parser.add_argument(
        "--artifact-file",
        dest="artifact_file",
        default=None,
        metavar="PATH",
        help="Path to a JSON file containing the artifact document.",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Path to write the session summary JSON.",
    )
    return parser


if __name__ == "__main__":
    _parser = _build_parser()
    _args = _parser.parse_args()
    run_feedback_session(_args)
