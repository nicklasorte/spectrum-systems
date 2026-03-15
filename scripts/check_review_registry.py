#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import List, Mapping, Optional

import jsonschema


def load_registry(path: Path) -> List[Mapping[str, object]]:
    if not path.is_file():
        raise FileNotFoundError(f"Registry file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Registry must be a JSON array")
    return data


def validate_against_schema(payload: object, schema_path: Path) -> None:
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: err.json_path)
    if errors:
        formatted = "\n".join(f"{err.json_path or '$'}: {err.message}" for err in errors)
        raise ValueError(f"Schema validation errors:\n{formatted}")


def detect_overdue(registry: List[Mapping[str, object]]) -> List[Mapping[str, object]]:
    today = date.today()
    overdue = []
    for entry in registry:
        due_raw = entry.get("follow_up_due_date")
        status = entry.get("status")
        if not due_raw or status == "Closed":
            continue
        due_date = date.fromisoformat(str(due_raw))
        if due_date < today:
            overdue.append(entry)
    return overdue


def summarize_status(registry: List[Mapping[str, object]]) -> Counter:
    return Counter(str(entry.get("status", "Unknown")) for entry in registry)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check review registry status and overdue follow-ups.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "reviews" / "review-registry.json",
        help="Path to review-registry.json",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "reviews" / "review-registry.schema.json",
        help="Path to review-registry.schema.json",
    )
    parser.add_argument(
        "--fail-on-overdue",
        action="store_true",
        help="Exit non-zero if any follow_up_due_date is past today for non-closed reviews.",
    )
    args = parser.parse_args(argv)

    registry = load_registry(args.registry)
    validate_against_schema(registry, args.schema)

    status_counts = summarize_status(registry)
    print("Review status summary:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    overdue = detect_overdue(registry)
    if overdue:
        print("\nOverdue follow-up dates:")
        for entry in overdue:
            print(f"  {entry.get('review_id')} ({entry.get('status')}) due {entry.get('follow_up_due_date')}: {entry.get('follow_up_trigger')}")
    else:
        print("\nNo overdue follow-up dates.")

    if args.fail_on_overdue and overdue:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
