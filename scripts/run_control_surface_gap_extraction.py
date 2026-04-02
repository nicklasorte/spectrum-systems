#!/usr/bin/env python3
"""Run deterministic control-surface gap extraction and PQX triage conversion."""

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
from spectrum_systems.modules.runtime.control_surface_gap_extractor import (
    ControlSurfaceGapExtractionError,
    extract_control_surface_gaps,
)
from spectrum_systems.modules.runtime.control_surface_gap_to_pqx import (
    ControlSurfaceGapToPQXError,
    convert_gaps_to_pqx_work_items,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run control-surface gap extraction")
    parser.add_argument("--manifest", required=True, help="Path to control_surface_manifest.json")
    parser.add_argument("--enforcement", required=True, help="Path to control_surface_enforcement_result.json")
    parser.add_argument("--obedience", required=True, help="Path to control_surface_obedience_result.json")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    return parser.parse_args()


def _load_json(path: Path, *, label: str) -> dict:
    if not path.is_file():
        raise ControlSurfaceGapExtractionError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ControlSurfaceGapExtractionError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ControlSurfaceGapExtractionError(f"{label} must be a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        manifest = _load_json(Path(args.manifest), label="manifest")
        enforcement = _load_json(Path(args.enforcement), label="enforcement")
        obedience = _load_json(Path(args.obedience), label="obedience")

        gap_result = extract_control_surface_gaps(manifest, enforcement, obedience)
        Draft202012Validator(load_schema("control_surface_gap_result"), format_checker=FormatChecker()).validate(gap_result)

        pqx_work_items = convert_gaps_to_pqx_work_items(gap_result)
        if gap_result["status"] == "gaps_detected" and not pqx_work_items:
            raise ControlSurfaceGapToPQXError("gap extraction produced gaps but no PQX work items")

    except (ControlSurfaceGapExtractionError, ControlSurfaceGapToPQXError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    gap_path = output_dir / "control_surface_gap_result.json"
    pqx_path = output_dir / "control_surface_gap_pqx_work_items.json"
    gap_path.write_text(json.dumps(gap_result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pqx_path.write_text(json.dumps(pqx_work_items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(gap_path))
    if gap_result["status"] == "gaps_detected" and not pqx_work_items:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
