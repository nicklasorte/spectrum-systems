"""DAG dependency governance runtime."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from spectrum_systems.contracts import validate_artifact


class DAGRuntimeError(ValueError):
    pass


def build_dependency_graph(*, nodes: list[str], edges: list[dict[str, str]], created_at: str, artifact_id: str = "dag-graph-001") -> dict[str, Any]:
    node_set = set(nodes)
    for edge in edges:
        if edge["from"] not in node_set or edge["to"] not in node_set:
            raise DAGRuntimeError("invalid_edge_node_reference")
    rec = {
        "artifact_type": "dag_dependency_graph_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "nodes": nodes,
        "edges": edges,
        "status": "pass",
    }
    validate_artifact(rec, "dag_dependency_graph_record")
    return rec


def detect_cycles(*, graph_record: dict[str, Any]) -> dict[str, Any]:
    indeg = defaultdict(int)
    adj = defaultdict(list)
    for n in graph_record["nodes"]:
        indeg[n] = 0
    for e in graph_record["edges"]:
        adj[e["from"]].append(e["to"])
        indeg[e["to"]] += 1
    q = deque([n for n, d in indeg.items() if d == 0])
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    has_cycle = seen != len(graph_record["nodes"])
    deadlocks = sorted([n for n, d in indeg.items() if d > 0])
    rec = {
        "artifact_type": "dag_cycle_deadlock_report",
        "artifact_id": f"dag-cycle-{graph_record['artifact_id']}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": graph_record["created_at"],
        "graph_ref": f"dag_dependency_graph_record:{graph_record['artifact_id']}",
        "has_cycle": has_cycle,
        "deadlock_nodes": deadlocks,
        "status": "fail" if has_cycle else "pass",
    }
    validate_artifact(rec, "dag_cycle_deadlock_report")
    return rec
