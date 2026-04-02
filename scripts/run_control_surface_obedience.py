#!/usr/bin/env python3
"""Run deterministic control surface obedience proof (CON-031)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.control_surface_obedience import (
    ControlSurfaceObedienceError,
    run_control_surface_obedience,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run control surface obedience proof")
    parser.add_argument("--manifest", required=True, help="Path to control_surface_manifest.json")
    parser.add_argument("--enforcement-result", required=True, help="Path to control_surface_enforcement_result.json")
    parser.add_argument("--invariant-result", required=True, help="Path to trust_spine invariant result JSON object")
    parser.add_argument("--done-certification", required=True, help="Path to done_certification_record.json")
    parser.add_argument("--promotion-decision", required=True, help="Path to promotion decision JSON object")
    parser.add_argument("--output-dir", default="outputs/control_surface_obedience", help="Output directory")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "control_surface_obedience_result.json"

    try:
        result = run_control_surface_obedience(
            manifest_path=Path(args.manifest),
            enforcement_result_path=Path(args.enforcement_result),
            invariant_result_path=Path(args.invariant_result),
            done_certification_path=Path(args.done_certification),
            promotion_decision_path=Path(args.promotion_decision),
        )
        schema = load_schema("control_surface_obedience_result")
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)
    except ControlSurfaceObedienceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(output_path))
    if result["overall_decision"] == "BLOCK":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
