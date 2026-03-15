import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "spectrum-governance.schema.json"
EXAMPLE_MANIFEST = REPO_ROOT / "governance" / "examples" / "comment-resolution-engine.spectrum-governance.json"
STANDARDS_MANIFEST = REPO_ROOT / "contracts" / "standards-manifest.json"


def test_governance_schema_is_valid() -> None:
    assert SCHEMA_PATH.is_file(), "spectrum-governance schema is missing"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_example_manifest_conforms_to_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    validator.validate(manifest)


def test_example_contract_pins_match_standards_manifest() -> None:
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    standards = json.loads(STANDARDS_MANIFEST.read_text(encoding="utf-8"))
    standards_contracts = {contract["artifact_type"]: contract["schema_version"] for contract in standards.get("contracts", [])}
    for contract_name, pinned_version in manifest["contracts"].items():
        assert contract_name in standards_contracts, f"Contract {contract_name} not published in standards manifest"
        assert pinned_version == standards_contracts[contract_name], f"Contract {contract_name} pinned to {pinned_version} but standards manifest declares {standards_contracts[contract_name]}"
