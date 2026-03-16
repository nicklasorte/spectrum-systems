#!/usr/bin/env python3
"""Generate a new design review artifact in design-reviews/."""

from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys


def slugify(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    if not slug:
        raise ValueError("topic must contain at least one alphanumeric character")
    return slug


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/new_design_review.py <topic>")
        return 1

    topic = sys.argv[1].strip()
    if not topic:
        print("Error: topic cannot be empty")
        return 1

    today = dt.date.today().isoformat()
    slug = slugify(topic)

    reviews_dir = pathlib.Path("design-reviews")
    reviews_dir.mkdir(parents=True, exist_ok=True)
    output_path = reviews_dir / f"{today}-{slug}.md"

    if output_path.exists():
        print(f"Error: review artifact already exists: {output_path}")
        return 1

    template = f"""# Architecture Review

Date: {today}  
Topic: {topic}

## Scope
Describe what part of the system was reviewed.

## Findings
List architectural findings.

## Risks
Describe any structural risks.

## Recommendations
Recommended changes.

## Repository Actions
- ADRs to create
- Issues to open
- Files to modify
"""

    output_path.write_text(template, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
