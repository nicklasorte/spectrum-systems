#!/usr/bin/env python3
"""CLI runner for trust-spine evidence cohesion evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.trust_spine_evidence_cohesion import (  # noqa: E402
    TrustSpineEvidenceCohesionError,
    evaluate_trust_spine_evidence_cohesion,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate trust-spine evidence cohesion")
    parser.add_argument("--manifest", required=True, help="Path to control_surface_manifest.json")
    parser.add_argument("--enforcement", required=True, help="Path to control_surface_enforcement_result.json")
    parser.add_argument("--obedience", required=True, help="Path to control_surface_obedience_result.json")
    parser.add_argument("--invariant", required=True, help="Path to trust_spine invariant result JSON")
    parser.add_argument("--done-certification", required=True, help="Path to done_certification_record.json")
    parser.add_argument("--promotion-decision", help="Optional path to promotion decision JSON")
    parser.add_argument("--contract-preflight", help="Optional path to contract_preflight_result_artifact.json")
    parser.add_argument("--output-dir", default="outputs/trust_spine_evidence_cohesion", help="Output directory")
    return parser.parse_args()


def _load_json(path_value: str, *, label: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise TrustSpineEvidenceCohesionError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustSpineEvidenceCohesionError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TrustSpineEvidenceCohesionError(f"{label} must be a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        artifacts: dict[str, dict[str, Any]] = {
            "manifest": _load_json(args.manifest, label="control_surface_manifest"),
            "enforcement_result": _load_json(args.enforcement, label="control_surface_enforcement_result"),
            "obedience_result": _load_json(args.obedience, label="control_surface_obedience_result"),
            "invariant_result": _load_json(args.invariant, label="trust_spine_invariant_result"),
            "done_certification_record": _load_json(args.done_certification, label="done_certification_record"),
        }
        refs = {
            "manifest_ref": args.manifest,
            "enforcement_result_ref": args.enforcement,
            "obedience_result_ref": args.obedience,
            "invariant_result_ref": args.invariant,
            "done_certification_ref": args.done_certification,
        }
        if args.promotion_decision:
            artifacts["promotion_decision"] = _load_json(args.promotion_decision, label="promotion_decision")
            refs["promotion_decision_ref"] = args.promotion_decision
        if args.contract_preflight:
            artifacts["contract_preflight_result"] = _load_json(args.contract_preflight, label="contract_preflight_result_artifact")
            refs["contract_preflight_ref"] = args.contract_preflight

        result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
        Draft202012Validator(load_schema("trust_spine_evidence_cohesion_result"), format_checker=FormatChecker()).validate(result)
    except TrustSpineEvidenceCohesionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output_path = output_dir / "trust_spine_evidence_cohesion_result.json"
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(str(output_path))

    if result["overall_decision"] == "BLOCK":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
