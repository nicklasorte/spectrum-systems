#!/usr/bin/env python3
"""
Build and display a review pack for a given scope ID.

Usage:
    python scripts/build_review_pack.py --scope-id p_gap_detection
    python scripts/build_review_pack.py --scope-id p1_slide_intelligence --json
"""
from __future__ import annotations

import argparse
import json
import sys

from spectrum_systems.modules.review_orchestrator import (
    build_review_pack,
    summarize_review_pack,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble a scoped review pack from a review manifest."
    )
    parser.add_argument(
        "--scope-id",
        required=True,
        metavar="SCOPE_ID",
        help="Scope identifier matching a review manifest (e.g. p_gap_detection).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit the review pack as JSON instead of the human-readable summary.",
    )
    args = parser.parse_args(argv)

    try:
        if args.json:
            pack = build_review_pack(args.scope_id)
            print(json.dumps(pack, indent=2, sort_keys=True))
        else:
            summary = summarize_review_pack(args.scope_id)
            print(summary)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
