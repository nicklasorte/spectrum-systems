#!/usr/bin/env python3
"""
Generate a machine-readable dependency graph across governed systems and contracts.

Inputs:
- ecosystem/ecosystem-registry.json
- governance/examples/manifests/*.spectrum-governance.json
- governance/schemas/spectrum-governance.schema.json
- contracts/standards-manifest.json

Outputs:
- artifacts/ecosystem-dependency-graph.json
- artifacts/ecosystem-dependency-graph.mmd
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "spectrum-governance.schema.json"
MANIFESTS_DIR = REPO_ROOT / "governance" / "examples" / "manifests"
OUTPUT_JSON = REPO_ROOT / "artifacts" / "ecosystem-dependency-graph.json"
OUTPUT_MERMAID = REPO_ROOT / "artifacts" / "ecosystem-dependency-graph.mmd"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path) -> Dict[str, dict]:
    data = load_json(path)
    registry_entries = {}
    for repo in data.get("repositories", []):
        system_id = repo.get("system_id")
        if system_id:
            registry_entries[system_id] = repo
    return registry_entries


def load_standards_contracts(path: Path) -> Dict[str, str]:
    data = load_json(path)
    return {
        contract["artifact_type"]: contract["schema_version"]
        for contract in data.get("contracts", [])
    }


def validate_manifest_against_registry(manifest: dict, registry: Dict[str, dict]) -> None:
    system_id = manifest["system_id"]
    registry_entry = registry.get(system_id)
    if not registry_entry:
        raise ValueError(f"System id {system_id} not found in ecosystem registry")

    if manifest["repo_name"] != registry_entry.get("repo_name"):
        raise ValueError(
            f"Manifest repo_name {manifest['repo_name']} does not match registry repo_name {registry_entry.get('repo_name')}"
        )

    if manifest["repo_type"] != registry_entry.get("repo_type"):
        raise ValueError(
            f"Manifest repo_type {manifest['repo_type']} does not match registry repo_type {registry_entry.get('repo_type')}"
        )


def validate_manifest_contracts(manifest: dict, standards_contracts: Dict[str, str]) -> None:
    for contract_name, version in manifest["contracts"].items():
        if contract_name not in standards_contracts:
            raise ValueError(f"Contract {contract_name} is not published in standards manifest")
        expected_version = standards_contracts[contract_name]
        if version != expected_version:
            raise ValueError(
                f"Contract {contract_name} pinned to {version} but standards manifest declares {expected_version}"
            )


def load_manifests(
    manifests_dir: Path, schema: dict, registry: Dict[str, dict], standards_contracts: Dict[str, str]
) -> List[dict]:
    validator = Draft202012Validator(schema)
    manifests: List[dict] = []
    for manifest_path in sorted(manifests_dir.glob("*.spectrum-governance.json")):
        manifest = load_json(manifest_path)
        validator.validate(manifest)
        validate_manifest_against_registry(manifest, registry)
        validate_manifest_contracts(manifest, standards_contracts)
        manifests.append(manifest)
    return manifests


def build_graph(manifests: List[dict]) -> dict:
    systems: Dict[str, dict] = {}
    contracts: Dict[str, dict] = {}
    dependencies: List[dict] = []

    for manifest in manifests:
        system_id = manifest["system_id"]
        system_entry = {
            "repo_name": manifest["repo_name"],
            "repo_type": manifest["repo_type"],
            "contracts": sorted(manifest["contracts"].keys()),
            "upstream_systems": manifest.get("upstream_systems", []),
            "downstream_systems": manifest.get("downstream_systems", []),
        }
        systems[system_id] = system_entry

        for contract_name, version in sorted(manifest["contracts"].items()):
            if contract_name not in contracts:
                contracts[contract_name] = {"version": version, "consumers": []}
            elif contracts[contract_name]["version"] != version:
                raise ValueError(
                    f"Contract {contract_name} has conflicting versions across manifests: "
                    f"{contracts[contract_name]['version']} vs {version}"
                )

            contracts[contract_name]["consumers"].append(system_id)
            dependencies.append({"system_id": system_id, "contract": contract_name, "version": version})

    for contract in contracts.values():
        contract["consumers"].sort()

    dependencies.sort(key=lambda item: (item["system_id"], item["contract"]))

    return {
        "systems": systems,
        "contracts": contracts,
        "dependencies": dependencies,
    }


def sanitize_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def render_mermaid(graph: dict) -> str:
    lines: List[str] = ["graph TD"]

    for system_id, system in sorted(graph["systems"].items()):
        label_text = f"{system['repo_name']} ({system['repo_type']})"
        label = f'{system_id}["{label_text}"]'
        lines.append(f"  {label}")

    for contract_name, contract in sorted(graph["contracts"].items()):
        node_id = f"contract_{sanitize_id(contract_name)}"
        label_text = f"{contract_name} v{contract['version']}"
        label = f'{node_id}["{label_text}"]'
        lines.append(f"  {label}")

    for dependency in graph["dependencies"]:
        contract_node = f"contract_{sanitize_id(dependency['contract'])}"
        lines.append(f"  {dependency['system_id']} --> {contract_node}")

    for system_id, system in sorted(graph["systems"].items()):
        for downstream in system.get("downstream_systems", []):
            lines.append(f"  {system_id} -.-> {downstream}")

    return "\n".join(lines)


def write_outputs(graph: dict) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(graph, indent=2, sort_keys=True), encoding="utf-8")
    mermaid = render_mermaid(graph)
    OUTPUT_MERMAID.write_text(mermaid + "\n", encoding="utf-8")


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    registry = load_registry(REGISTRY_PATH)
    standards_contracts = load_standards_contracts(STANDARDS_PATH)
    manifests = load_manifests(MANIFESTS_DIR, schema, registry, standards_contracts)
    graph = build_graph(manifests)
    write_outputs(graph)
    return 0


if __name__ == "__main__":
    sys.exit(main())
