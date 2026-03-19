#!/usr/bin/env python3
"""Run BD bundle contract + manifest hardening validation for an execution bundle.

Usage
-----
    python scripts/run_bundle_validation.py <bundle_manifest_path> \
        [--bundle-root <directory>]

Outputs
-------
- Prints a concise summary to stdout.
- Writes the full decision artifact to outputs/run_bundle_validation_decision.json.
- Archives a timestamped copy under data/run_bundle_decisions/.

Exit code
---------
0   Valid — bundle contract satisfied.
1   Invalid manifest or contract violation.
2   Runtime/path-related error (bad input, schema load failure).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.run_bundle import (  # noqa: E402
    load_run_bundle_manifest,
    normalize_run_bundle_manifest,
    validate_bundle_contract,
    derive_bundle_summary,
)

_DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "run_bundle_validation_decision.json"
_ARCHIVE_DIR = _REPO_ROOT / "data" / "run_bundle_decisions"
_DECISION_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "run_bundle_validation_decision.schema.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_decision_against_schema(decision: Dict[str, Any]) -> None:
    """Lightweight structural check against the decision schema required fields."""
    schema = _load_json(_DECISION_SCHEMA_PATH)
    required = schema.get("required", [])
    for field in required:
        if field not in decision:
            raise ValueError(f"Decision is missing required field: {field}")

    failure_type = decision.get("failure_type")
    valid_failure_types = schema["properties"]["failure_type"]["enum"]
    if failure_type not in valid_failure_types:
        raise ValueError(
            f"failure_type '{failure_type}' is not a valid enum value: {valid_failure_types}"
        )


def _persist_archive(decision: Dict[str, Any]) -> Path:
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = _ARCHIVE_DIR / f"run_bundle_validation_decision_{stamp}.json"
    suffix = 1
    while target.exists():
        target = _ARCHIVE_DIR / f"run_bundle_validation_decision_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return target


def _persist_output(decision: Dict[str, Any]) -> Path:
    _DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEFAULT_OUTPUT_PATH.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return _DEFAULT_OUTPUT_PATH


def _print_summary(decision: Dict[str, Any]) -> None:
    print(f"valid:                 {decision['valid']}")
    print(f"failure_type:          {decision['failure_type']}")
    conditions = decision.get("triggering_conditions") or []
    if conditions:
        print("triggering_conditions:")
        for cond in conditions:
            print(f"  - {cond}")
    else:
        print("triggering_conditions: []")
    summary = decision.get("bundle_summary") or {}
    print("bundle_summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a run-bundle manifest against the governed bundle contract (Prompt BD)."
    )
    parser.add_argument(
        "bundle_manifest",
        help="Path to a JSON file containing the run-bundle manifest, or to the bundle root directory.",
    )
    parser.add_argument(
        "--bundle-root",
        dest="bundle_root",
        default=None,
        help=(
            "Optional base directory used to resolve relative input file paths declared "
            "in the bundle manifest.  When omitted, on-disk input existence checks are skipped."
        ),
    )

    args = parser.parse_args(argv)

    manifest_path = Path(args.bundle_manifest).resolve()

    # Accept either a manifest file or a bundle root directory
    if manifest_path.is_dir():
        candidate = manifest_path / "run_bundle_manifest.json"
        if not candidate.exists():
            print(
                f"ERROR: Directory provided but no run_bundle_manifest.json found in: {manifest_path}",
                file=sys.stderr,
            )
            return 2
        manifest_path = candidate
        if args.bundle_root is None:
            args.bundle_root = str(manifest_path.parent)

    try:
        manifest = load_run_bundle_manifest(manifest_path)
        manifest = normalize_run_bundle_manifest(manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot load bundle manifest: {exc}", file=sys.stderr)
        return 2

    bundle_root = Path(args.bundle_root).resolve() if args.bundle_root else None

    try:
        decision = validate_bundle_contract(manifest, bundle_root=bundle_root)
        _validate_decision_against_schema(decision)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Validation failed unexpectedly: {exc}", file=sys.stderr)
        return 2

    try:
        archive_path = _persist_archive(decision)
        output_path = _persist_output(decision)
    except OSError as exc:
        print(f"ERROR: Cannot persist decision artifacts: {exc}", file=sys.stderr)
        return 2

    _print_summary(decision)
    print(f"\ndecision_id:           {decision['decision_id']}")
    print(f"archived at:           {archive_path}")
    print(f"output written to:     {output_path}")

    return 0 if decision["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
