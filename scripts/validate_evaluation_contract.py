#!/usr/bin/env python3
"""
Validate that evaluation manifest files satisfy the control-loop contract.

Contract rules enforced beyond JSON Schema:
  1. Every evaluation result MUST have an ``action_required`` field.
  2. When ``action_required`` is true, ``linked_work_item_id`` must be a
     non-null, non-empty string.
  3. When ``action_required`` is false, ``rationale`` must be a non-empty string
     explaining why no action was taken.

Usage:
    python scripts/validate_evaluation_contract.py <manifest.json> [<manifest2.json> ...]
    python scripts/validate_evaluation_contract.py --all   # scan all eval manifests in contracts/examples/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_BASE_DIR = Path(__file__).resolve().parents[1]


def validate_contract(instance: Dict[str, Any]) -> List[str]:
    """Validate the evaluation → work-item linkage contract.

    Returns a list of human-readable error strings (empty list means valid).
    """
    errors: List[str] = []
    artifact_id = instance.get("artifact_id", "<unknown>")

    # Rule 1: action_required must be present
    if "action_required" not in instance:
        errors.append(
            f"[{artifact_id}] Missing required contract field: action_required"
        )
        # Can't evaluate rules 2 and 3 without this field
        return errors

    action_required = instance["action_required"]
    if not isinstance(action_required, bool):
        errors.append(
            f"[{artifact_id}] action_required must be a boolean, got: {type(action_required).__name__}"
        )
        return errors

    # Rule 2: action_required=true → linked_work_item_id must exist and be non-empty
    if action_required:
        linked = instance.get("linked_work_item_id")
        if linked is None or (isinstance(linked, str) and not linked.strip()):
            errors.append(
                f"[{artifact_id}] action_required=true but linked_work_item_id is missing or null. "
                "Generate a work item and populate this field."
            )

    # Rule 3: action_required=false → rationale must be present and non-empty
    else:
        rationale = instance.get("rationale", "")
        if not rationale or not str(rationale).strip():
            errors.append(
                f"[{artifact_id}] action_required=false but rationale is missing or empty. "
                "Document why no action is required."
            )

    return errors


def validate_file(path: Path) -> Dict[str, Any]:
    """Load and validate a single evaluation manifest file.

    Returns a result dict with keys: ``file``, ``artifact_id``, ``status``,
    and ``errors``.
    """
    try:
        instance: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "file": str(path),
            "artifact_id": "unknown",
            "status": "fail",
            "errors": [f"Cannot load file: {exc}"],
        }

    errors = validate_contract(instance)
    return {
        "file": str(path),
        "artifact_id": instance.get("artifact_id", "unknown"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def discover_manifests() -> List[Path]:
    """Discover evaluation manifest examples under contracts/examples/."""
    examples_dir = _BASE_DIR / "contracts" / "examples"
    return list(examples_dir.glob("evaluation_manifest*.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate evaluation manifests against the control-loop contract."
    )
    parser.add_argument(
        "manifests",
        nargs="*",
        help="Path(s) to evaluation manifest JSON file(s).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all evaluation manifests in contracts/examples/.",
    )
    args = parser.parse_args(argv)

    if args.all:
        paths = discover_manifests()
        if not paths:
            print("No evaluation manifests found under contracts/examples/.")
            return 0
    elif args.manifests:
        paths = [Path(p).resolve() for p in args.manifests]
    else:
        parser.print_help()
        return 1

    results = [validate_file(p) for p in paths]
    failures = [r for r in results if r["status"] == "fail"]

    for result in results:
        if result["status"] == "pass":
            print(f"PASS  {result['file']}")
        else:
            print(f"FAIL  {result['file']}")
            for error in result["errors"]:
                print(f"      - {error}")

    if failures:
        print(f"\n{len(failures)} of {len(results)} manifest(s) failed contract validation.")
        return 1

    print(f"\nAll {len(results)} manifest(s) passed contract validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
