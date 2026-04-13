import json
from pathlib import Path

from spectrum_systems.contracts.artifact_class_taxonomy import load_allowed_artifact_classes


REPO_ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_GRAPH_SCHEMA_PATH = REPO_ROOT / "ecosystem" / "dependency-graph.schema.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"


def test_dependency_graph_schema_enum_matches_canonical_artifact_taxonomy() -> None:
    allowed = sorted(load_allowed_artifact_classes())
    schema = json.loads(DEPENDENCY_GRAPH_SCHEMA_PATH.read_text(encoding="utf-8"))

    contract_enum = sorted(
        schema["properties"]["contracts"]["items"]["properties"]["artifact_class"]["enum"]
    )
    artifact_enum = sorted(
        schema["properties"]["artifacts"]["items"]["properties"]["artifact_class"]["enum"]
    )

    assert contract_enum == allowed
    assert artifact_enum == allowed


def test_standards_manifest_artifact_classes_are_canonical() -> None:
    allowed = set(load_allowed_artifact_classes())
    manifest = json.loads(STANDARDS_MANIFEST_PATH.read_text(encoding="utf-8"))

    invalid = [
        contract["artifact_type"]
        for contract in manifest.get("contracts", [])
        if contract.get("artifact_class") not in allowed
    ]

    assert not invalid, f"standards-manifest contains non-canonical artifact classes: {invalid}"
