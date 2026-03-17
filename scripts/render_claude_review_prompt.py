#!/usr/bin/env python3
"""
Render a Claude review prompt for a given scope ID and print it to stdout.

Usage:
    python scripts/render_claude_review_prompt.py --scope-id p_gap_detection
    python scripts/render_claude_review_prompt.py --scope-id p1_slide_intelligence --output /tmp/prompt.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spectrum_systems.modules.review_orchestrator import render_claude_review_prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a Claude review prompt from a review manifest."
    )
    parser.add_argument(
        "--scope-id",
        required=True,
        metavar="SCOPE_ID",
        help="Scope identifier matching a review manifest (e.g. p_gap_detection).",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Optional output file path. If omitted, prints to stdout.",
    )
    args = parser.parse_args(argv)

    try:
        prompt = render_claude_review_prompt(args.scope_id)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        print(f"Prompt written to {output_path}")
    else:
        print(prompt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
