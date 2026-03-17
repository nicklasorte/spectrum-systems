#!/usr/bin/env python3
"""
Generate a governance-compliant repository scaffold aligned to spectrum-systems.

Usage
-----
  python scripts/scaffold_governed_repo.py \\
      --repo-name my-new-engine \\
      --repo-type operational_engine \\
      --system-id my-new-engine \\
      --owner nicklasorte \\
      --output-dir /path/to/output

Reads (from the spectrum-systems repo root)
-------------------------------------------
  contracts/standards-manifest.json        (current contract versions)
  scaffold-templates/repo-type-contracts.json  (default contract list per repo type)

Generates (in --output-dir)
---------------------------
  .spectrum-governance.json               governance manifest
  governance/governance-declaration.json  machine-readable governance declaration
  .github/workflows/validate-governance.yml  baseline CI workflow
  README.md                               stub README
  registry-entry.json                     ready-to-add ecosystem registry entry

No network calls are made.  All output is deterministic for a given set of inputs.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
REPO_TYPE_CONTRACTS_PATH = REPO_ROOT / "scaffold-templates" / "repo-type-contracts.json"
CI_WORKFLOW_TEMPLATE_PATH = (
    REPO_ROOT / "scaffold-templates" / "ci-workflows" / "validate-governance.yml"
)

GOVERNANCE_VERSION = "1.0.0"
GOVERNANCE_DECLARATION_VERSION = "1.0.0"
ARCHITECTURE_SOURCE = "nicklasorte/spectrum-systems"

VALID_REPO_TYPES = frozenset(
    ["governance", "factory", "operational_engine", "advisory", "pipeline"]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_standards_contracts(path: Path) -> Dict[str, str]:
    """Return {artifact_type: schema_version} from the standards manifest."""
    manifest = _load_json(path)
    return {
        contract["artifact_type"]: contract["schema_version"]
        for contract in manifest.get("contracts", [])
        if contract.get("artifact_type")
    }


def _load_standards_manifest_version(path: Path) -> str:
    manifest = _load_json(path)
    return manifest.get("standards_version", "")


def _load_repo_type_defaults(path: Path, repo_type: str) -> dict:
    mapping = _load_json(path)
    mapping.pop("_instructions", None)
    entry = mapping.get(repo_type)
    if entry is None:
        raise ValueError(
            f"No scaffold defaults defined for repo_type '{repo_type}'. "
            f"Valid types: {sorted(mapping.keys())}"
        )
    return entry


# ---------------------------------------------------------------------------
# Scaffold builders
# ---------------------------------------------------------------------------


def build_spectrum_governance(
    *,
    repo_name: str,
    repo_type: str,
    system_id: str,
    contracts: Dict[str, str],
) -> dict:
    """Build .spectrum-governance.json content."""
    return {
        "system_id": system_id,
        "repo_name": repo_name,
        "repo_type": repo_type,
        "governance_repo": "spectrum-systems",
        "governance_version": GOVERNANCE_VERSION,
        "contracts": contracts,
    }


def build_governance_declaration(
    *,
    system_id: str,
    owner: str,
    repo_name: str,
    standards_manifest_version: str,
    contract_pins: Dict[str, str],
    schema_pins: Dict[str, str],
    declared_at: str,
) -> dict:
    """Build governance/governance-declaration.json content."""
    return {
        "governance_declaration_version": GOVERNANCE_DECLARATION_VERSION,
        "architecture_source": ARCHITECTURE_SOURCE,
        "standards_manifest_version": standards_manifest_version,
        "system_id": system_id,
        "implementation_repo": f"{owner}/{repo_name}",
        "declared_at": declared_at,
        "contract_pins": contract_pins,
        "schema_pins": schema_pins,
        "rule_version": None,
        "prompt_set_hash": None,
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": None,
        "external_storage_policy": "none",
    }


def build_registry_entry(
    *,
    repo_name: str,
    owner: str,
    repo_type: str,
    layer: str,
    system_id: str,
    contracts: List[str],
    description: str,
) -> dict:
    """Build a ready-to-add ecosystem-registry.json entry."""
    return {
        "repo_name": repo_name,
        "repo_url": f"https://github.com/{owner}/{repo_name}",
        "repo_type": repo_type,
        "status": "planned",
        "layer": layer,
        "system_id": system_id,
        "manifest_required": True,
        "contracts": sorted(contracts),
        "description": description,
    }


def build_readme(*, repo_name: str, repo_type: str, system_id: str, description: str) -> str:
    """Build a stub README.md."""
    return f"""\
# {repo_name}

> **Repo type:** `{repo_type}` | **System ID:** `{system_id}` | **Layer:** see ecosystem registry

{description}

## Governance

This repository was scaffolded as a governance-compliant spectrum-systems repo.

| File | Purpose |
|------|---------|
| `.spectrum-governance.json` | Governance manifest — pinned contracts and repo metadata |
| `governance/governance-declaration.json` | Full governance declaration with schema/contract pins |
| `.github/workflows/validate-governance.yml` | CI workflow for governance compliance |

## Getting started

1. Fill in placeholder values in `governance/governance-declaration.json` (fields marked `null`).
2. Add this repo to the ecosystem registry in spectrum-systems:
   see `registry-entry.json` for the entry to add.
3. Create a design package at `design-packages/{system_id}.design-package.json` in spectrum-systems.
4. Run `python scripts/validate_governance_manifest.py .spectrum-governance.json` to validate.

## Contracts consumed

See `.spectrum-governance.json` for the pinned contract versions.
Contract schemas are maintained in `nicklasorte/spectrum-systems/contracts/schemas/`.

## CI

The `.github/workflows/validate-governance.yml` workflow validates governance artifacts on every
push to `main` and on pull requests.
"""


# ---------------------------------------------------------------------------
# Main scaffold function
# ---------------------------------------------------------------------------


def scaffold_governed_repo(
    *,
    repo_name: str,
    repo_type: str,
    system_id: str,
    owner: str,
    output_dir: Path,
    declared_at: str | None = None,
    standards_manifest_path: Path = STANDARDS_MANIFEST_PATH,
    repo_type_contracts_path: Path = REPO_TYPE_CONTRACTS_PATH,
    ci_workflow_template_path: Path = CI_WORKFLOW_TEMPLATE_PATH,
) -> dict:
    """
    Generate a complete governed repository scaffold in *output_dir*.

    Parameters
    ----------
    declared_at:
        ISO 8601 date string (``YYYY-MM-DD``) written into the governance
        declaration's ``declared_at`` field.  Defaults to today's date when
        ``None``.  Pass an explicit value to get deterministic output in tests.

    Returns a summary dict describing what was written.
    """
    if repo_type not in VALID_REPO_TYPES:
        raise ValueError(
            f"Invalid repo_type '{repo_type}'. Must be one of: {sorted(VALID_REPO_TYPES)}"
        )

    if declared_at is None:
        declared_at = date.today().isoformat()

    # Load governance data from spectrum-systems
    all_contract_versions = _load_standards_contracts(standards_manifest_path)
    standards_manifest_version = _load_standards_manifest_version(standards_manifest_path)
    repo_defaults = _load_repo_type_defaults(repo_type_contracts_path, repo_type)

    # Resolve contract pins: only include contracts that exist in the standards manifest
    default_contract_names: List[str] = repo_defaults.get("contracts", [])
    contract_pins: Dict[str, str] = {}
    for name in default_contract_names:
        version = all_contract_versions.get(name)
        if version is not None:
            contract_pins[name] = version

    # Resolve schema pins
    schema_pin_paths: List[str] = repo_defaults.get("schema_pins", [])
    schema_pins: Dict[str, str] = {path: "1.0.0" for path in schema_pin_paths}

    layer: str = repo_defaults.get("layer", "")
    description: str = repo_defaults.get("description", f"{repo_type} repository")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    written_files: List[str] = []

    # --- .spectrum-governance.json ---
    governance_manifest = build_spectrum_governance(
        repo_name=repo_name,
        repo_type=repo_type,
        system_id=system_id,
        contracts=contract_pins,
    )
    _write_json(output_dir / ".spectrum-governance.json", governance_manifest)
    written_files.append(".spectrum-governance.json")

    # --- governance/governance-declaration.json ---
    governance_dir = output_dir / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    declaration = build_governance_declaration(
        system_id=system_id,
        owner=owner,
        repo_name=repo_name,
        standards_manifest_version=standards_manifest_version,
        contract_pins=contract_pins,
        schema_pins=schema_pins,
        declared_at=declared_at,
    )
    _write_json(governance_dir / "governance-declaration.json", declaration)
    written_files.append("governance/governance-declaration.json")

    # --- .github/workflows/validate-governance.yml ---
    workflows_dir = output_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_dest = workflows_dir / "validate-governance.yml"
    shutil.copy2(ci_workflow_template_path, workflow_dest)
    written_files.append(".github/workflows/validate-governance.yml")

    # --- README.md ---
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        build_readme(
            repo_name=repo_name,
            repo_type=repo_type,
            system_id=system_id,
            description=description,
        ),
        encoding="utf-8",
    )
    written_files.append("README.md")

    # --- registry-entry.json ---
    registry_entry = build_registry_entry(
        repo_name=repo_name,
        owner=owner,
        repo_type=repo_type,
        layer=layer,
        system_id=system_id,
        contracts=list(contract_pins.keys()),
        description=description,
    )
    _write_json(output_dir / "registry-entry.json", registry_entry)
    written_files.append("registry-entry.json")

    return {
        "repo_name": repo_name,
        "repo_type": repo_type,
        "system_id": system_id,
        "owner": owner,
        "output_dir": str(output_dir),
        "declared_at": declared_at,
        "contracts_scaffolded": sorted(contract_pins.keys()),
        "schema_pins_scaffolded": sorted(schema_pins.keys()),
        "files_written": written_files,
        "registry_entry": registry_entry,
    }


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a governance-compliant repository scaffold.",
    )
    parser.add_argument(
        "--repo-name",
        required=True,
        help="Repository name (e.g. my-new-engine). Must match ecosystem slug format.",
    )
    parser.add_argument(
        "--repo-type",
        required=True,
        choices=sorted(VALID_REPO_TYPES),
        help="Repository archetype.",
    )
    parser.add_argument(
        "--system-id",
        required=True,
        help="Canonical system identifier. Typically equals --repo-name.",
    )
    parser.add_argument(
        "--owner",
        required=True,
        help="GitHub organization or username (e.g. nicklasorte).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write the scaffold into. Created if it does not exist.",
    )
    parser.add_argument(
        "--declared-at",
        default=None,
        help=(
            "ISO 8601 date for governance-declaration.json declared_at field "
            "(default: today's date). Override for deterministic testing."
        ),
    )
    args = parser.parse_args(argv)

    summary = scaffold_governed_repo(
        repo_name=args.repo_name,
        repo_type=args.repo_type,
        system_id=args.system_id,
        owner=args.owner,
        output_dir=args.output_dir,
        declared_at=args.declared_at,
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    print()
    print("Scaffold complete.")
    print(f"  Files written to: {summary['output_dir']}")
    print()
    print("Next steps:")
    print("  1. Fill in null fields in governance/governance-declaration.json")
    print("  2. Add registry-entry.json to ecosystem/ecosystem-registry.json in spectrum-systems")
    print(
        f"  3. Create design-packages/{summary['system_id']}.design-package.json in spectrum-systems"
    )
    print("  4. Run: python spectrum-systems/scripts/validate_governance_manifest.py .spectrum-governance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
