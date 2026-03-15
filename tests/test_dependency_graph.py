import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import build_dependency_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = REPO_ROOT / "ecosystem" / "dependency-graph.json"
SCHEMA_PATH = REPO_ROOT / "ecosystem" / "dependency-graph.schema.json"
SUMMARY_PATH = REPO_ROOT / "artifacts" / "dependency-graph-summary.md"
MERMAID_PATH = REPO_ROOT / "artifacts" / "dependency-graph.mmd"
DOC_PATH = REPO_ROOT / "docs" / "ecosystem-dependency-graph.md"


def test_dependency_graph_pipeline() -> None:
    assert DOC_PATH.is_file(), "Dependency graph overview doc is missing"
    assert SCHEMA_PATH.is_file(), "Dependency graph schema is missing"

    exit_code = build_dependency_graph.main()
    assert exit_code == 0

    assert GRAPH_PATH.is_file(), "dependency-graph.json was not generated"
    assert SUMMARY_PATH.is_file(), "dependency-graph-summary.md was not generated"
    assert MERMAID_PATH.is_file(), "dependency-graph.mmd was not generated"

    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(graph)

    system_ids = {system["system_id"] for system in graph["systems"]}
    artifact_ids = {artifact["artifact_type"] for artifact in graph["artifacts"]}
    contract_ids = {contract["contract_name"] for contract in graph["contracts"]}

    for edge in graph["edges"]:
        if edge["from_type"] == "system":
            assert edge["from_id"] in system_ids
        elif edge["from_type"] == "artifact":
            assert edge["from_id"] in artifact_ids
        else:
            assert edge["from_id"] in contract_ids

        if edge["to_type"] == "system":
            assert edge["to_id"] in system_ids
        elif edge["to_type"] == "artifact":
            assert edge["to_id"] in artifact_ids
        else:
            assert edge["to_id"] in contract_ids
