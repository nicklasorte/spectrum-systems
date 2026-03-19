#!/usr/bin/env python3
"""Run BC runtime compatibility validation for an execution bundle.

Usage
-----
    python scripts/run_runtime_validation.py <bundle_manifest_path> [--runtime-env <json>]

Outputs
-------
- Prints a summary to stdout.
- Writes the full decision artifact to outputs/runtime_validation_decision.json.
- Archives a timestamped copy under data/runtime_decisions/.

Exit code
---------
0   Compatible — execution allowed.
1   Incompatible — execution blocked.
2   Unexpected error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.runtime_compatibility import (  # noqa: E402
    validate_runtime_environment,
)

_DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "runtime_validation_decision.json"
_ARCHIVE_DIR = _REPO_ROOT / "data" / "runtime_decisions"
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "runtime_compatibility_decision.schema.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_against_schema(decision: Dict[str, Any]) -> None:
    schema = _load_json(_SCHEMA_PATH)
    required = schema.get("required", [])
    for field in required:
        if field not in decision:
            raise ValueError(f"Decision is missing required field: {field}")

    response = decision.get("system_response")
    valid_responses = [
        e for e in schema["properties"]["system_response"]["enum"]
    ]
    if response not in valid_responses:
        raise ValueError(
            f"system_response '{response}' is not a valid enum value: {valid_responses}"
        )

    failure_type = decision.get("failure_type")
    valid_failure_types = [
        e for e in schema["properties"]["failure_type"]["enum"]
    ]
    if failure_type not in valid_failure_types:
        raise ValueError(
            f"failure_type '{failure_type}' is not a valid enum value: {valid_failure_types}"
        )


def _persist_archive(decision: Dict[str, Any]) -> Path:
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = _ARCHIVE_DIR / f"runtime_compatibility_decision_{stamp}.json"
    suffix = 1
    while target.exists():
        target = _ARCHIVE_DIR / f"runtime_compatibility_decision_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return target


def _persist_output(decision: Dict[str, Any]) -> Path:
    _DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEFAULT_OUTPUT_PATH.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return _DEFAULT_OUTPUT_PATH


def _print_summary(decision: Dict[str, Any]) -> None:
    print(f"compatible:            {decision['compatible']}")
    print(f"system_response:       {decision['system_response']}")
    print(f"failure_type:          {decision['failure_type']}")
    conditions = decision.get("triggering_conditions") or []
    if conditions:
        print("triggering_conditions:")
        for cond in conditions:
            print(f"  - {cond}")
    else:
        print("triggering_conditions: []")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an execution bundle against runtime compatibility requirements (Prompt BC)."
    )
    parser.add_argument(
        "bundle_manifest",
        help="Path to a JSON file containing the run-bundle manifest.",
    )
    parser.add_argument(
        "--runtime-env",
        dest="runtime_env",
        default=None,
        help=(
            "Optional JSON string or path to a JSON file describing the runtime "
            "environment.  When omitted, the environment is auto-detected."
        ),
    )
    parser.add_argument(
        "--base-path",
        dest="base_path",
        default=None,
        help=(
            "Optional base directory used to resolve relative file paths declared "
            "in the bundle manifest."
        ),
    )

    args = parser.parse_args(argv)

    try:
        manifest_path = Path(args.bundle_manifest).resolve()
        bundle_manifest = _load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot load bundle manifest: {exc}", file=sys.stderr)
        return 2

    runtime_env: Optional[Dict[str, Any]] = None
    if args.runtime_env:
        env_input = args.runtime_env.strip()
        if env_input.startswith("{"):
            try:
                runtime_env = json.loads(env_input)
            except json.JSONDecodeError as exc:
                print(f"ERROR: Invalid --runtime-env JSON: {exc}", file=sys.stderr)
                return 2
        else:
            try:
                runtime_env = _load_json(Path(env_input).resolve())
            except (OSError, json.JSONDecodeError) as exc:
                print(f"ERROR: Cannot load runtime-env file: {exc}", file=sys.stderr)
                return 2

    base_path = Path(args.base_path).resolve() if args.base_path else None

    try:
        decision = validate_runtime_environment(
            bundle_manifest,
            runtime_env=runtime_env,
            base_path=base_path,
        )
        _validate_against_schema(decision)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Validation failed unexpectedly: {exc}", file=sys.stderr)
        return 2

    archive_path = _persist_archive(decision)
    output_path = _persist_output(decision)

    _print_summary(decision)
    print(f"\ndecision_id:           {decision['decision_id']}")
    print(f"archived at:           {archive_path}")
    print(f"output written to:     {output_path}")

    return 0 if decision["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
