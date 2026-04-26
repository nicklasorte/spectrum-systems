from __future__ import annotations


def validate_dependency_graph(batches: list[dict]) -> dict:
    ids = {b["batch_id"] for b in batches}
    reasons: list[str] = []

    for batch in batches:
        deps = batch.get("depends_on")
        if deps is None:
            reasons.append(f"missing_depends_on:{batch['batch_id']}")
            continue
        for dep in deps:
            if dep not in ids:
                reasons.append(f"missing_dependency:{batch['batch_id']}->{dep}")

    visiting: set[str] = set()
    visited: set[str] = set()
    graph = {b["batch_id"]: b.get("depends_on", []) for b in batches}

    def walk(node: str) -> None:
        if node in visiting:
            reasons.append(f"circular_dependency:{node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph:
                walk(dep)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        walk(node)

    return {"ok": not reasons, "reason_codes": sorted(set(reasons))}
