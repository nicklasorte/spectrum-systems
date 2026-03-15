#!/usr/bin/env python3
"""
Validate a governance manifest against the schema, ecosystem registry, and standards manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "spectrum-governance.schema.json"
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_registry_map(registry: dict) -> Dict[str, dict]:
    repos = registry.get("repositories", [])
    return {repo["system_id"]: repo for repo in repos if repo.get("system_id")}


def build_standards_contracts(standards: dict) -> Dict[str, str]:
    contracts = standards.get("contracts", [])
    return {contract["artifact_type"]: contract["schema_version"] for contract in contracts if contract.get("artifact_type")}


def validate_manifest(manifest_path: Path) -> dict:
    schema = load_json(SCHEMA_PATH)
    registry = load_json(REGISTRY_PATH)
    standards = load_json(STANDARDS_PATH)
    manifest = load_json(manifest_path)

    validator = Draft202012Validator(schema)
    errors: List[str] = [
        f"Schema violation at {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(manifest), key=lambda e: e.path)
    ]

    registry_map = build_registry_map(registry)
    system_id = manifest.get("system_id")
    registry_entry = registry_map.get(system_id)
    if not registry_entry:
        errors.append(f"Unknown system_id: {system_id}")
    else:
        if manifest.get("repo_name") != registry_entry.get("repo_name"):
            errors.append(
                f"repo_name mismatch for {system_id}: manifest={manifest.get('repo_name')} registry={registry_entry.get('repo_name')}"
            )
        if manifest.get("repo_type") != registry_entry.get("repo_type"):
            errors.append(
                f"repo_type mismatch for {system_id}: manifest={manifest.get('repo_type')} registry={registry_entry.get('repo_type')}"
            )

    standards_contracts = build_standards_contracts(standards)
    for contract_name, version in sorted((manifest.get("contracts") or {}).items()):
        if contract_name not in standards_contracts:
            errors.append(f"Unknown contract {contract_name}")
            continue
        expected_version = standards_contracts[contract_name]
        if version != expected_version:
            errors.append(
                f"Contract {contract_name} pinned to {version} but standards manifest declares {expected_version}"
            )

    status = "pass" if not errors else "fail"
    return {
        "manifest": str(manifest_path),
        "status": status,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a governance manifest.")
    parser.add_argument(
        "manifest",
        nargs="?",
        default=".spectrum-governance.json",
        help="Path to governance manifest (default: .spectrum-governance.json)",
    )
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    result = validate_manifest(manifest_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
