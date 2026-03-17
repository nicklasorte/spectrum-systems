#!/usr/bin/env python3
"""
Validate an evaluation manifest against the canonical schema and perform
evidence-reference integrity checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_BASE_DIR = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = _BASE_DIR / "contracts" / "schemas" / "evaluation_manifest.schema.json"


def load_schema() -> Dict[str, Any]:
    """Load the canonical evaluation_manifest JSON Schema."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_schema(instance: Dict[str, Any]) -> List[str]:
    """Validate *instance* against the evaluation_manifest schema.

    Returns a list of human-readable error strings (empty list means valid).
    """
    schema = load_schema()
    validator = Draft202012Validator(schema)
    errors: List[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = list(error.path)
        location = f"[{'.'.join(str(p) for p in path)}]" if path else "[root]"
        errors.append(f"Schema error at {location}: {error.message}")
    return errors


def validate_evidence_refs(
    instance: Dict[str, Any],
    bundle_path: Optional[Path] = None,
) -> List[str]:
    """Check *instance['evidence_refs']* for well-formedness.

    When *bundle_path* is provided, also verifies that any ``ref_path`` values
    resolve to existing files inside that directory.
    """
    errors: List[str] = []
    refs = instance.get("evidence_refs")
    if not isinstance(refs, list):
        errors.append("evidence_refs must be an array")
        return errors
    for i, ref in enumerate(refs):
        if not isinstance(ref, dict):
            errors.append(f"evidence_refs[{i}] must be an object")
            continue
        if "ref_type" not in ref:
            errors.append(f"evidence_refs[{i}] missing required field: ref_type")
        if "ref_id" not in ref:
            errors.append(f"evidence_refs[{i}] missing required field: ref_id")
        if bundle_path is not None and "ref_path" in ref:
            ref_file = bundle_path / ref["ref_path"]
            if not ref_file.exists():
                errors.append(
                    f"evidence_refs[{i}] ref_path not found on disk: {ref['ref_path']}"
                )
    return errors


def validate_readiness_requirements(instance: Dict[str, Any]) -> List[str]:
    """Check semantic constraints for readiness assessment.

    Rules enforced:
    - ``governance-ready`` and ``decision-support-ready`` require at least one
      evidence_ref.
    - ``status == 'fail'`` requires at least one entry in ``criteria_applied``
      so the failure is traceable.
    """
    errors: List[str] = []
    status = instance.get("status")
    readiness = instance.get("readiness_level")

    high_readiness = {"governance-ready", "decision-support-ready"}
    if readiness in high_readiness:
        refs = instance.get("evidence_refs", [])
        if not refs:
            errors.append(
                f"readiness_level '{readiness}' requires at least one evidence_ref"
            )

    if status == "fail":
        criteria = instance.get("criteria_applied", [])
        if not criteria:
            errors.append(
                "status 'fail' requires criteria_applied to be non-empty"
            )

    return errors


def validate_manifest(
    manifest_path: Path,
    bundle_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the full validation pipeline for an evaluation manifest.

    Returns a result dict with keys: ``manifest``, ``evaluation_id``,
    ``run_id``, ``status``, and ``errors``.
    """
    errors: List[str] = []

    try:
        instance: Dict[str, Any] = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "manifest": str(manifest_path),
            "evaluation_id": "unknown",
            "run_id": "unknown",
            "status": "fail",
            "errors": [f"Cannot load manifest: {exc}"],
        }

    errors.extend(validate_schema(instance))
    errors.extend(validate_evidence_refs(instance, bundle_path))
    errors.extend(validate_readiness_requirements(instance))

    status = "pass" if not errors else "fail"
    return {
        "manifest": str(manifest_path),
        "evaluation_id": instance.get("artifact_id", "unknown"),
        "run_id": instance.get("run_id", "unknown"),
        "status": status,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an evaluation manifest against the canonical schema."
    )
    parser.add_argument("manifest", help="Path to an evaluation manifest JSON file")
    parser.add_argument(
        "--bundle",
        help=(
            "Optional path to an evidence bundle directory. "
            "When provided, ref_path values in evidence_refs are verified on disk."
        ),
        default=None,
    )
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    bundle_path = Path(args.bundle).resolve() if args.bundle else None

    result = validate_manifest(manifest_path, bundle_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
