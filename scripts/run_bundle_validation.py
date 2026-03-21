#!/usr/bin/env python3
"""Backward-compatible CLI for run-bundle validation workflows.

Supports both:
1) Legacy Prompt BD manifest validation (positional path argument).
2) New bundle-directory validator path (`--bundle <dir>`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.run_bundle import (  # noqa: E402
    load_run_bundle_manifest,
    normalize_run_bundle_manifest,
    validate_bundle_contract,
)
from spectrum_systems.modules.runtime.run_bundle_validator import (  # noqa: E402
    validate_and_emit_decision,
)

_DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "run_bundle_validation_decision.json"
_DEFAULT_ARCHIVE_DIR = _REPO_ROOT / "data" / "run_bundle_decisions"
_ARCHIVE_DIR = _DEFAULT_ARCHIVE_DIR
_DECISION_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "run_bundle_validation_decision.schema.json"
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_legacy_decision_against_schema(decision: Dict[str, Any]) -> None:
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


def _persist_output(decision: Dict[str, Any]) -> Path:
    _DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEFAULT_OUTPUT_PATH.write_text(json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8")
    return _DEFAULT_OUTPUT_PATH


def _persist_archive(decision: Dict[str, Any]) -> Path:
    archive_dir = _ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    decision_id = str(decision.get("decision_id") or "decision")
    safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in decision_id)
    target = archive_dir / f"{safe_id}.json"
    target.write_text(json.dumps(decision, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _resolve_legacy_manifest_path(raw_path: str) -> Path:
    manifest_path = Path(raw_path).resolve()
    if manifest_path.is_dir():
        manifest_path = manifest_path / "run_bundle_manifest.json"
    return manifest_path


def _run_legacy_manifest_validation(manifest_arg: str, bundle_root_arg: str | None) -> int:
    manifest_path = _resolve_legacy_manifest_path(manifest_arg)
    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = load_run_bundle_manifest(manifest_path)
        manifest = normalize_run_bundle_manifest(manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot load bundle manifest: {exc}", file=sys.stderr)
        return 2

    bundle_root = Path(bundle_root_arg).resolve() if bundle_root_arg else manifest_path.parent

    try:
        decision = validate_bundle_contract(manifest, bundle_root=bundle_root)
        _validate_legacy_decision_against_schema(decision)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Validation failed unexpectedly: {exc}", file=sys.stderr)
        return 2

    try:
        _persist_output(decision)
        _persist_archive(decision)
    except OSError as exc:
        print(f"ERROR: Cannot persist decision artifacts: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0 if decision.get("valid") else 1


def _run_new_bundle_validation(bundle_path: str) -> int:
    bundle = Path(bundle_path).resolve()
    if not bundle.exists():
        print(f"ERROR: bundle path not found: {bundle}", file=sys.stderr)
        return 2

    try:
        decision = validate_and_emit_decision(bundle)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: bundle validation failed: {exc}", file=sys.stderr)
        return 2

    try:
        _persist_output(decision)
        _persist_archive(decision)
    except OSError as exc:
        print(f"ERROR: Cannot persist decision artifacts: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(decision, indent=2, sort_keys=True))

    mapping = {
        "allow": 0,
        "require_rebuild": 1,
        "block": 2,
    }
    response = decision.get("system_response")
    if response not in mapping:
        print(f"ERROR: unknown system_response: {response}", file=sys.stderr)
        return 2
    return mapping[response]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bundle validation CLI (legacy + new modes).")
    parser.add_argument(
        "bundle_manifest",
        nargs="?",
        help="Legacy mode: path to run_bundle_manifest.json, or to directory containing it.",
    )
    parser.add_argument(
        "--bundle-root",
        dest="bundle_root",
        default=None,
        help="Legacy mode: optional base dir for resolving relative input paths.",
    )
    parser.add_argument(
        "--bundle",
        dest="bundle",
        default=None,
        help="New mode: path to bundle directory for schema-first artifact validation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.bundle:
        if args.bundle_manifest is not None:
            print("ERROR: provide either --bundle or positional bundle_manifest, not both", file=sys.stderr)
            return 2
        return _run_new_bundle_validation(args.bundle)

    if args.bundle_manifest:
        return _run_legacy_manifest_validation(args.bundle_manifest, args.bundle_root)

    print("ERROR: missing input path; provide --bundle <dir> or positional manifest path", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
