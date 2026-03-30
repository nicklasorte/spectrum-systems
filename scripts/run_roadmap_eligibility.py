#!/usr/bin/env python3
"""Run deterministic governed roadmap eligibility evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.orchestration.roadmap_eligibility import (  # noqa: E402
    RoadmapEligibilityError,
    evaluate_roadmap_eligibility_to_path,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate governed roadmap eligibility and emit artifact.")
    parser.add_argument("--roadmap", required=True, help="Path to governed roadmap artifact JSON.")
    parser.add_argument("--output", required=True, help="Path to write roadmap eligibility artifact JSON.")
    return parser.parse_args()


def _validate_output(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = load_schema("roadmap_eligibility_artifact")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def main() -> int:
    args = _parse_args()
    roadmap_path = Path(args.roadmap)
    output_path = Path(args.output)

    try:
        evaluate_roadmap_eligibility_to_path(roadmap_path, output_path)
        _validate_output(output_path)
    except (RoadmapEligibilityError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[roadmap-eligibility] error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[roadmap-eligibility] unexpected error: {exc}", file=sys.stderr)
        return 1

    print(f"[roadmap-eligibility] wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
