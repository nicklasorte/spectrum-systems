import json
from pathlib import Path

from scripts import generate_dependency_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"


def test_dependency_graph_is_generated() -> None:
    # Ensure a clean slate
    if generate_dependency_graph.OUTPUT_JSON.exists():
        generate_dependency_graph.OUTPUT_JSON.unlink()
    if generate_dependency_graph.OUTPUT_MERMAID.exists():
        generate_dependency_graph.OUTPUT_MERMAID.unlink()

    exit_code = generate_dependency_graph.main()
    assert exit_code == 0

    assert generate_dependency_graph.OUTPUT_JSON.is_file(), "JSON dependency graph was not created"
    assert generate_dependency_graph.OUTPUT_MERMAID.is_file(), "Mermaid dependency graph was not created"

    graph = json.loads(generate_dependency_graph.OUTPUT_JSON.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry_systems = {repo["system_id"] for repo in registry.get("repositories", []) if repo.get("system_id")}

    assert "systems" in graph and "contracts" in graph and "dependencies" in graph
    assert set(graph["systems"].keys()) <= registry_systems

    for dependency in graph["dependencies"]:
        assert dependency["system_id"] in registry_systems
        assert dependency["contract"] in graph["contracts"]
        assert graph["contracts"][dependency["contract"]]["version"] == dependency["version"]

    mermaid = generate_dependency_graph.OUTPUT_MERMAID.read_text(encoding="utf-8")
    assert mermaid.startswith("graph TD")
    for system_id in graph["systems"].keys():
        assert system_id in mermaid
