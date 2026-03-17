#!/usr/bin/env python3
"""
Validate a Claude review output JSON file against the review contract schema.

Usage:
    python scripts/validate_review_output.py --input reviews/output/sample.json
    python scripts/validate_review_output.py --input reviews/output/sample.json --verbose
"""
from __future__ import annotations

import argparse
import json
import sys

from spectrum_systems.modules.review_orchestrator import validate_review_output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Claude review output JSON file against the review contract schema."
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to the review output JSON file to validate.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print the full review summary even on pass.",
    )
    args = parser.parse_args(argv)

    result = validate_review_output(args.input)

    status = "PASS" if result["passed"] else "FAIL"
    print(f"{status}  {result['file']}")
    print(f"      review_id: {result['review_id']}")
    print(f"      verdict:   {result['verdict']}")

    if not result["passed"]:
        for error in result["errors"]:
            print(f"      ERROR: {error}")
        return 1

    if args.verbose:
        print("      All schema checks passed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
