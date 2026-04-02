#!/usr/bin/env python3
"""Build deterministic control-surface gap packet artifact (CON-034)."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.control_surface_gap_extractor import (  # noqa: E402
    ControlSurfaceGapExtractionError,
    extract_control_surface_gap_packet,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic control-surface gap packet artifact")
    parser.add_argument("--manifest", required=True, help="Path to control_surface_manifest artifact")
    parser.add_argument("--enforcement", required=True, help="Path to control_surface_enforcement_result artifact")
    parser.add_argument("--obedience", required=True, help="Path to control_surface_obedience_result artifact")
    parser.add_argument("--trust-spine", required=True, help="Path to trust-spine result artifact")
    parser.add_argument("--done-certification", required=True, help="Path to done_certification_record artifact")
    parser.add_argument("--output", required=True, help="Output file path for control_surface_gap_packet.json")
    parser.add_argument("--generated-at", required=True, help="Deterministic RFC3339 timestamp")
    parser.add_argument("--trace-id", required=True, help="Trace ID for packet lineage")
    parser.add_argument("--policy-id", default="CON-034.control_surface_gap_extraction.v1", help="Policy ID")
    parser.add_argument(
        "--governing-ref",
        default="docs/roadmaps/system_roadmap.md#con-034",
        help="Governing reference anchor",
    )
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

    try:
        manifest = _load_json(Path(args.manifest), label="control_surface_manifest")
        enforcement = _load_json(Path(args.enforcement), label="control_surface_enforcement_result")
        obedience = _load_json(Path(args.obedience), label="control_surface_obedience_result")
        trust_spine = _load_json(Path(args.trust_spine), label="trust_spine_result")
        done_cert = _load_json(Path(args.done_certification), label="done_certification_record")

        packet = extract_control_surface_gap_packet(
            manifest=manifest,
            enforcement_result=enforcement,
            obedience_result=obedience,
            trust_spine_result=trust_spine,
            done_certification_record=done_cert,
            generated_at=args.generated_at,
            trace_id=args.trace_id,
            policy_id=args.policy_id,
            governing_ref=args.governing_ref,
        )
        Draft202012Validator(load_schema("control_surface_gap_packet"), format_checker=FormatChecker()).validate(packet)
    except ControlSurfaceGapExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(output_path))

    if packet["overall_decision"] == "BLOCK":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
