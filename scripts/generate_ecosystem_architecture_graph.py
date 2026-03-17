#!/usr/bin/env python3
"""
Generate an ecosystem architecture/dependency graph for the governed repository ecosystem.

Reads from:
- ecosystem/ecosystem-registry.json
- contracts/standards-manifest.json
- governance/reports/contract-dependency-graph.json  (optional, for consumer/producer edges)

Outputs:
- governance/reports/ecosystem-architecture-graph.json   (machine-readable graph)
- governance/reports/ecosystem-architecture-graph.mmd    (Mermaid diagram)

Exit codes
----------
0 — success
1 — error generating graph
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[1]

ECOSYSTEM_REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
CONTRACT_GRAPH_PATH = REPO_ROOT / "governance" / "reports" / "contract-dependency-graph.json"

OUTPUT_JSON = REPO_ROOT / "governance" / "reports" / "ecosystem-architecture-graph.json"
OUTPUT_MERMAID = REPO_ROOT / "governance" / "reports" / "ecosystem-architecture-graph.mmd"


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def load_ecosystem_registry() -> List[dict]:
    data = load_json(ECOSYSTEM_REGISTRY_PATH) or {}
    return data.get("repositories", [])


def load_standards_contracts() -> List[dict]:
    data = load_json(STANDARDS_MANIFEST_PATH) or {}
    return data.get("contracts", [])


def load_contract_graph() -> dict:
    return load_json(CONTRACT_GRAPH_PATH) or {}


# ─────────────────────────────────────────────────────────────────────────────
# Graph builders
# ─────────────────────────────────────────────────────────────────────────────

def build_nodes(repositories: List[dict]) -> List[dict]:
    """Build repository nodes."""
    nodes: List[dict] = []
    for repo in sorted(repositories, key=lambda r: r.get("repo_name", "")):
        nodes.append({
            "id": repo["repo_name"],
            "node_type": "repository",
            "repo_type": repo.get("repo_type", ""),
            "architecture_layer": repo.get("layer", ""),
            "system_id": repo.get("system_id", ""),
            "status": repo.get("status", ""),
        })
    return nodes


def build_contract_nodes(contracts: List[dict]) -> List[dict]:
    """Build contract nodes from the standards manifest."""
    nodes: List[dict] = []
    for contract in sorted(contracts, key=lambda c: c.get("artifact_type", "")):
        nodes.append({
            "id": contract["artifact_type"],
            "node_type": "contract",
            "schema_version": contract.get("schema_version", ""),
            "stability": contract.get("stability", ""),
        })
    return nodes


def build_edges(
    repositories: List[dict],
    contract_graph: dict,
    contract_ids: Set[str],
) -> List[dict]:
    """Build directed edges: repos consuming/producing contracts."""
    edges: List[dict] = []
    edge_set: Set[tuple] = set()

    # From ecosystem registry: repo declares contracts it uses
    for repo in repositories:
        repo_name = repo.get("repo_name", "")
        for contract_name in repo.get("contracts", []):
            if contract_name not in contract_ids:
                continue
            key = (repo_name, contract_name, "consumes")
            if key not in edge_set:
                edge_set.add(key)
                edges.append({
                    "from": repo_name,
                    "from_type": "repository",
                    "to": contract_name,
                    "to_type": "contract",
                    "relationship": "consumes",
                })

    # From contract enforcement graph: add producer/consumer info when available
    for repo_data in contract_graph.get("repos", []):
        repo_name = repo_data.get("repo_name", "")
        for c in repo_data.get("contracts_consumed", []):
            contract_name = c.get("contract", "")
            if contract_name not in contract_ids:
                continue
            key = (repo_name, contract_name, "consumes")
            if key not in edge_set:
                edge_set.add(key)
                edges.append({
                    "from": repo_name,
                    "from_type": "repository",
                    "to": contract_name,
                    "to_type": "contract",
                    "relationship": "consumes",
                })
        for c in repo_data.get("contracts_produced", []):
            contract_name = c.get("contract", "")
            if contract_name not in contract_ids:
                continue
            key = (repo_name, contract_name, "produces")
            if key not in edge_set:
                edge_set.add(key)
                edges.append({
                    "from": repo_name,
                    "from_type": "repository",
                    "to": contract_name,
                    "to_type": "contract",
                    "relationship": "produces",
                })

    # Layer-to-layer dependency edges between repos
    layer_order = {
        "Layer 1": 1,
        "Layer 2": 2,
        "Layer 3": 3,
        "Layer 4": 4,
        "Layer 5": 5,
    }
    # Pipeline (Layer 4) depends on operational engines (Layer 3)
    # Advisory (Layer 5) depends on pipeline (Layer 4)
    layer_deps: List[tuple] = [
        ("Layer 3", "Layer 2"),  # operational engines governed by governance repo
        ("Layer 4", "Layer 3"),  # pipeline orchestrates engines
        ("Layer 5", "Layer 4"),  # advisory consumes pipeline outputs
        ("Layer 1", "Layer 2"),  # factory governed by governance repo
    ]
    repo_by_layer: Dict[str, List[str]] = {}
    for repo in repositories:
        layer = repo.get("layer", "")
        repo_by_layer.setdefault(layer, []).append(repo.get("repo_name", ""))

    for consumer_layer, provider_layer in layer_deps:
        for consumer_repo in repo_by_layer.get(consumer_layer, []):
            for provider_repo in repo_by_layer.get(provider_layer, []):
                key = (consumer_repo, provider_repo, "layer_depends_on")
                if key not in edge_set:
                    edge_set.add(key)
                    edges.append({
                        "from": consumer_repo,
                        "from_type": "repository",
                        "to": provider_repo,
                        "to_type": "repository",
                        "relationship": "layer_depends_on",
                    })

    return sorted(edges, key=lambda e: (e["from"], e["to"], e["relationship"]))


# ─────────────────────────────────────────────────────────────────────────────
# Output writers
# ─────────────────────────────────────────────────────────────────────────────

def write_graph_json(
    repo_nodes: List[dict],
    contract_nodes: List[dict],
    edges: List[dict],
    generated_at: str,
) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "nodes": {
            "repositories": repo_nodes,
            "contracts": contract_nodes,
        },
        "edges": edges,
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _mermaid_safe(name: str) -> str:
    """Return a Mermaid-safe node ID."""
    return name.replace("-", "_").replace(".", "_")


def write_mermaid(
    repo_nodes: List[dict],
    contract_nodes: List[dict],
    edges: List[dict],
) -> None:
    OUTPUT_MERMAID.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = ["graph LR", ""]

    # Subgraph per architecture layer
    layer_repos: Dict[str, List[dict]] = {}
    for node in repo_nodes:
        layer = node.get("architecture_layer", "Unknown")
        layer_repos.setdefault(layer, []).append(node)

    layer_labels = {
        "Layer 1": "Layer 1 — Factory",
        "Layer 2": "Layer 2 — Governance",
        "Layer 3": "Layer 3 — Operational Engines",
        "Layer 4": "Layer 4 — Pipeline",
        "Layer 5": "Layer 5 — Advisory",
    }

    for layer in ["Layer 2", "Layer 1", "Layer 3", "Layer 4", "Layer 5"]:
        repos = layer_repos.get(layer, [])
        if not repos:
            continue
        label = layer_labels.get(layer, layer)
        lines.append(f"  subgraph {_mermaid_safe(layer)}[\"{label}\"]")
        for repo in repos:
            nid = _mermaid_safe(repo["id"])
            lines.append(f"    {nid}[\"{repo['id']}\"]")
        lines.append("  end")
        lines.append("")

    # Contract subgraph (first 15 to keep diagram readable)
    if contract_nodes:
        lines.append("  subgraph Contracts[\"Governed Contracts\"]")
        for c in contract_nodes[:15]:
            cid = _mermaid_safe(c["id"])
            lines.append(f"    {cid}([\"{c['id']}\"])")
        if len(contract_nodes) > 15:
            lines.append(f"    more_contracts[\"... and {len(contract_nodes) - 15} more\"]")
        lines.append("  end")
        lines.append("")

    # Edges (skip layer_depends_on to keep diagram cleaner; show only consumes/produces)
    contract_ids = {c["id"] for c in contract_nodes}
    shown_contract_ids = {c["id"] for c in contract_nodes[:15]}
    for edge in edges:
        rel = edge["relationship"]
        if rel == "layer_depends_on":
            continue
        if edge["to_type"] == "contract" and edge["to"] not in shown_contract_ids:
            continue
        from_id = _mermaid_safe(edge["from"])
        to_id = _mermaid_safe(edge["to"])
        if rel == "consumes":
            lines.append(f"  {from_id} -->|consumes| {to_id}")
        elif rel == "produces":
            lines.append(f"  {from_id} -.->|produces| {to_id}")

    OUTPUT_MERMAID.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        repositories = load_ecosystem_registry()
        contracts = load_standards_contracts()
        contract_graph = load_contract_graph()
    except Exception as exc:
        print(f"[ecosystem-arch-graph] ERROR loading inputs: {exc}", file=sys.stderr)
        return 1

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    contract_ids: Set[str] = {c["artifact_type"] for c in contracts if c.get("artifact_type")}

    repo_nodes = build_nodes(repositories)
    contract_nodes = build_contract_nodes(contracts)
    edges = build_edges(repositories, contract_graph, contract_ids)

    write_graph_json(repo_nodes, contract_nodes, edges, generated_at)
    write_mermaid(repo_nodes, contract_nodes, edges)

    print(
        f"[ecosystem-arch-graph] Generated graph: "
        f"{len(repo_nodes)} repos, {len(contract_nodes)} contracts, {len(edges)} edges."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
