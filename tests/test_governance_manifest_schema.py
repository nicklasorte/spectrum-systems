import json
from pathlib import Path
from typing import Iterator

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "spectrum-governance.schema.json"
MANIFEST_DIR = REPO_ROOT / "governance" / "examples" / "manifests"
STANDARDS_MANIFEST = REPO_ROOT / "contracts" / "standards-manifest.json"
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"


def iter_manifest_paths() -> Iterator[Path]:
    yield from sorted(MANIFEST_DIR.glob("*.spectrum-governance.json"))


def test_governance_schema_is_valid() -> None:
    assert SCHEMA_PATH.is_file(), "spectrum-governance schema is missing"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_example_manifest_conforms_to_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for manifest_path in iter_manifest_paths():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validator.validate(manifest)


def test_example_contract_pins_match_standards_manifest() -> None:
    standards = json.loads(STANDARDS_MANIFEST.read_text(encoding="utf-8"))
    standards_contracts = {contract["artifact_type"]: contract["schema_version"] for contract in standards.get("contracts", [])}
    for manifest_path in iter_manifest_paths():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for contract_name, pinned_version in manifest["contracts"].items():
            assert contract_name in standards_contracts, f"Contract {contract_name} not published in standards manifest"
            assert pinned_version == standards_contracts[contract_name], f"Contract {contract_name} pinned to {pinned_version} but standards manifest declares {standards_contracts[contract_name]}"


def test_systems_match_registry_and_references_are_known() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry_systems = {repo["system_id"]: repo for repo in registry.get("repositories", []) if repo.get("system_id")}
    known_ids = set(registry_systems.keys())

    for manifest_path in iter_manifest_paths():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        system_id = manifest["system_id"]
        assert system_id in registry_systems, f"Manifest {manifest_path.name} references unknown system_id {system_id}"
        registry_entry = registry_systems[system_id]
        assert manifest["repo_name"] == registry_entry["repo_name"], f"{system_id} repo_name mismatch"
        assert manifest["repo_type"] == registry_entry["repo_type"], f"{system_id} repo_type mismatch"

        for upstream in manifest.get("upstream_systems", []):
            assert upstream in known_ids, f"{system_id} upstream_system {upstream} missing from registry"
        for downstream in manifest.get("downstream_systems", []):
            assert downstream in known_ids, f"{system_id} downstream_system {downstream} missing from registry"
