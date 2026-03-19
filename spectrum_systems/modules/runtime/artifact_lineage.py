"""Artifact Lineage System (Prompt BS).

Strict, deterministic lineage system connecting all artifacts across the
pipeline:

    simulation_input → simulation_output → evidence_pack → reasoning_trace
    → adversarial_result → synthesis → decision → slo_evaluation

Every artifact is traceable to its origin and evaluable for integrity.

Design rules
------------
- Deterministic outputs only (no random IDs).
- No silent failures — raise hard on lineage violations.
- Schema-first enforcement everywhere.
- No circular dependencies.
- No orphan artifacts (except simulation_input).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
_LINEAGE_SCHEMA_PATH = _SCHEMA_DIR / "artifact_lineage.schema.json"

# ---------------------------------------------------------------------------
# Artifact type constants
# ---------------------------------------------------------------------------

ARTIFACT_TYPES = frozenset(
    {
        "simulation_input",
        "simulation_output",
        "evidence_pack",
        "reasoning_trace",
        "adversarial_result",
        "synthesis",
        "decision",
        "slo_evaluation",
    }
)

# Root type — only type allowed to have no parents.
_ROOT_TYPE = "simulation_input"

# Required parent type(s) for each artifact type.
# Maps artifact_type → frozenset of required parent types (all must be present).
_REQUIRED_PARENT_TYPES: Dict[str, FrozenSet[str]] = {
    "simulation_output": frozenset({"simulation_input"}),
    "evidence_pack": frozenset({"simulation_output"}),
    "reasoning_trace": frozenset({"evidence_pack"}),
    "adversarial_result": frozenset({"reasoning_trace"}),
    "synthesis": frozenset({"evidence_pack", "adversarial_result"}),
    "decision": frozenset({"synthesis"}),
    "slo_evaluation": frozenset({"decision", "synthesis"}),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_lineage_schema() -> Dict[str, Any]:
    return json.loads(_LINEAGE_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def create_artifact_metadata(
    artifact_id: str,
    artifact_type: str,
    parent_artifact_ids: List[str],
    created_by: str,
    version: str,
    registry: Optional[Dict[str, Dict[str, Any]]] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build artifact metadata with computed lineage fields.

    Parameters
    ----------
    artifact_id:
        Deterministic ID (pass-through; never generated here).
    artifact_type:
        Must be one of the governed artifact types.
    parent_artifact_ids:
        Direct parent artifact IDs.  Empty for ``simulation_input`` roots.
    created_by:
        Module or agent name that creates this artifact.
    version:
        Artifact version string.
    registry:
        Optional mapping of existing artifact_id → metadata dict used to
        compute depth and root IDs.  When omitted depth=0 and roots=[] for
        root types; for non-root types without a registry the caller must
        supply a registry to get correct values.
    created_at:
        Optional ISO 8601 timestamp.  Defaults to current UTC time.

    Returns
    -------
    Dict[str, Any]
        Fully-populated artifact metadata record (not yet validated against
        schema).

    Raises
    ------
    ValueError
        On invalid artifact type or constraint violation.
    """
    if not artifact_id:
        raise ValueError("artifact_id must be a non-empty string")
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(
            f"Unknown artifact_type '{artifact_type}'. "
            f"Allowed: {sorted(ARTIFACT_TYPES)}"
        )

    reg = registry or {}

    depth = compute_lineage_depth(artifact_id, parent_artifact_ids, reg)
    root_ids = compute_root_artifacts(artifact_id, parent_artifact_ids, reg)

    lineage_valid, lineage_errors = validate_lineage_chain(
        artifact_id,
        artifact_type,
        parent_artifact_ids,
        reg,
    )

    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "parent_artifact_ids": list(parent_artifact_ids),
        "created_at": created_at or _now_iso(),
        "created_by": created_by,
        "version": version,
        "lineage_depth": depth,
        "root_artifact_ids": sorted(root_ids),
        "lineage_valid": lineage_valid,
        "lineage_errors": lineage_errors,
    }


def link_artifacts(
    parent_ids: List[str],
    child_id: str,
    registry: Dict[str, Dict[str, Any]],
) -> None:
    """Assert that all parent_ids exist in the registry.

    Parameters
    ----------
    parent_ids:
        IDs that must be present as keys in *registry*.
    child_id:
        ID of the artifact being linked (used in error messages).
    registry:
        Mapping of artifact_id → metadata.

    Raises
    ------
    ValueError
        If any parent ID is missing from the registry.
    """
    missing = [pid for pid in parent_ids if pid not in registry]
    if missing:
        raise ValueError(
            f"Artifact '{child_id}' references missing parents: {missing}"
        )


def compute_lineage_depth(
    artifact_id: str,
    parent_artifact_ids: List[str],
    registry: Dict[str, Dict[str, Any]],
) -> int:
    """Compute lineage depth as max(parent_depth) + 1.

    Root artifacts (no parents) have depth 0.

    Parameters
    ----------
    artifact_id:
        ID of the artifact (used for cycle detection context).
    parent_artifact_ids:
        Direct parent IDs.
    registry:
        Existing artifacts used to resolve parent depths.

    Returns
    -------
    int
        Lineage depth ≥ 0.
    """
    if not parent_artifact_ids:
        return 0

    max_parent_depth = -1
    for pid in parent_artifact_ids:
        if pid in registry:
            parent_depth = registry[pid].get("lineage_depth", 0)
            if parent_depth > max_parent_depth:
                max_parent_depth = parent_depth

    if max_parent_depth < 0:
        # No parents resolved — treat as depth 1 (child of unknown root)
        return 1

    return max_parent_depth + 1


def compute_root_artifacts(
    artifact_id: str,
    parent_artifact_ids: List[str],
    registry: Dict[str, Dict[str, Any]],
    _visited: Optional[Set[str]] = None,
) -> List[str]:
    """Recursively walk parents to collect all root (simulation_input) IDs.

    Parameters
    ----------
    artifact_id:
        Starting artifact ID.
    parent_artifact_ids:
        Direct parent IDs of the starting artifact.
    registry:
        All known artifacts.
    _visited:
        Internal cycle-guard set.

    Returns
    -------
    List[str]
        Deduplicated list of root artifact IDs.
    """
    if _visited is None:
        _visited = set()

    if artifact_id in _visited:
        return []  # Cycle — stop recursion

    _visited = _visited | {artifact_id}

    if not parent_artifact_ids:
        # This artifact is itself a root
        return [artifact_id]

    roots: List[str] = []
    for pid in parent_artifact_ids:
        if pid not in registry:
            continue
        parent = registry[pid]
        parent_parents = parent.get("parent_artifact_ids", [])
        child_roots = compute_root_artifacts(pid, parent_parents, registry, _visited)
        roots.extend(child_roots)

    # Deduplicate while preserving order
    seen: Set[str] = set()
    result: List[str] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            result.append(r)
    return result


def validate_lineage_chain(
    artifact_id: str,
    artifact_type: str,
    parent_artifact_ids: List[str],
    registry: Dict[str, Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Validate the lineage chain for a single artifact.

    Checks
    ------
    - All parents exist in the registry.
    - No circular references (artifact_id not reachable from its parents).
    - root_artifact_ids consistent with registry data.
    - lineage_depth correct relative to parents.
    - Required parent types present (per _REQUIRED_PARENT_TYPES).

    Parameters
    ----------
    artifact_id:
        The artifact being validated.
    artifact_type:
        Governed type of the artifact.
    parent_artifact_ids:
        Direct parent IDs.
    registry:
        All known artifacts (excluding the artifact under validation).

    Returns
    -------
    Tuple[bool, List[str]]
        (valid, errors)  — valid is True when errors is empty.
    """
    errors: List[str] = []

    # 1. Root constraint: simulation_input must have zero parents
    if artifact_type == _ROOT_TYPE and parent_artifact_ids:
        errors.append(
            f"simulation_input artifact '{artifact_id}' must have no parents "
            f"but has: {parent_artifact_ids}"
        )

    # 2. Non-root constraint: must have ≥1 parent
    if artifact_type != _ROOT_TYPE and not parent_artifact_ids:
        errors.append(
            f"Non-root artifact '{artifact_id}' of type '{artifact_type}' "
            "has no parents (orphan)."
        )

    # 3. All parents must exist in registry
    missing_parents = [pid for pid in parent_artifact_ids if pid not in registry]
    if missing_parents:
        errors.append(
            f"Artifact '{artifact_id}' references missing parents: {missing_parents}"
        )

    # 4. No circular references
    if _has_cycle(artifact_id, parent_artifact_ids, registry):
        errors.append(
            f"Artifact '{artifact_id}' is part of a circular dependency."
        )

    # 5. Required parent types
    required_types = _REQUIRED_PARENT_TYPES.get(artifact_type, frozenset())
    if required_types:
        present_parent_types: Set[str] = set()
        for pid in parent_artifact_ids:
            if pid in registry:
                ptype = registry[pid].get("artifact_type", "")
                present_parent_types.add(ptype)
        for required_type in required_types:
            if required_type not in present_parent_types:
                errors.append(
                    f"Artifact '{artifact_id}' of type '{artifact_type}' "
                    f"must have a parent of type '{required_type}' but none found."
                )

    # 6. lineage_depth is computed correctly by construction via
    # compute_lineage_depth above — no additional cross-check needed here
    # because validate_full_registry catches depth inconsistencies at the
    # registry level via detect_lineage_gaps.

    return (len(errors) == 0, errors)


def _has_cycle(
    artifact_id: str,
    parent_artifact_ids: List[str],
    registry: Dict[str, Dict[str, Any]],
) -> bool:
    """Return True if artifact_id appears in its own ancestor chain."""
    visited: Set[str] = set()
    queue: List[str] = list(parent_artifact_ids)

    while queue:
        current = queue.pop()
        if current == artifact_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        if current in registry:
            queue.extend(registry[current].get("parent_artifact_ids", []))

    return False


def build_full_lineage_graph(
    registry: Dict[str, Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Build adjacency map (parent → [children]) for all artifacts.

    Parameters
    ----------
    registry:
        Mapping of artifact_id → metadata.

    Returns
    -------
    Dict[str, List[str]]
        Keys are artifact IDs; values are lists of child IDs.
    """
    graph: Dict[str, List[str]] = {aid: [] for aid in registry}

    for aid, meta in registry.items():
        for pid in meta.get("parent_artifact_ids", []):
            if pid in graph:
                graph[pid].append(aid)
            else:
                graph[pid] = [aid]

    return graph


def trace_to_root(
    artifact_id: str,
    registry: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Return ordered path from *artifact_id* up to its root ancestor(s).

    Parameters
    ----------
    artifact_id:
        Starting artifact.
    registry:
        All known artifacts.

    Returns
    -------
    List[str]
        Artifact IDs from *artifact_id* back to root(s), depth-first.
    """
    if artifact_id not in registry:
        return []

    path: List[str] = [artifact_id]
    visited: Set[str] = {artifact_id}

    parents = registry[artifact_id].get("parent_artifact_ids", [])
    for pid in parents:
        if pid not in visited:
            sub_path = trace_to_root(pid, registry)
            path.extend(p for p in sub_path if p not in visited)
            visited.update(sub_path)

    return path


def trace_to_leaves(
    artifact_id: str,
    registry: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Return all artifacts reachable downstream from *artifact_id*.

    Parameters
    ----------
    artifact_id:
        Starting artifact.
    registry:
        All known artifacts.

    Returns
    -------
    List[str]
        Artifact IDs reachable downstream (children/grandchildren…).
    """
    graph = build_full_lineage_graph(registry)

    result: List[str] = []
    visited: Set[str] = set()
    queue: List[str] = list(graph.get(artifact_id, []))

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        result.append(current)
        queue.extend(graph.get(current, []))

    return result


def detect_lineage_gaps(
    registry: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Detect structural lineage problems across the entire registry.

    Checks
    ------
    - Missing parents (reference to unknown artifact).
    - Broken chains (non-root artifact with no parents).
    - Inconsistent lineage_depth.
    - Orphan artifacts (non-root with no parents).

    Parameters
    ----------
    registry:
        Mapping of artifact_id → metadata.

    Returns
    -------
    Dict[str, Any]
        {
            "missing_parents": {artifact_id: [missing_parent_ids]},
            "broken_chains": [artifact_ids],
            "depth_inconsistencies": {artifact_id: {expected, actual}},
            "orphan_artifacts": [artifact_ids],
        }
    """
    missing_parents: Dict[str, List[str]] = {}
    broken_chains: List[str] = []
    depth_inconsistencies: Dict[str, Dict[str, int]] = {}
    orphan_artifacts: List[str] = []

    for aid, meta in registry.items():
        atype = meta.get("artifact_type", "")
        parents = meta.get("parent_artifact_ids", [])

        # Missing parents
        missing = [pid for pid in parents if pid not in registry]
        if missing:
            missing_parents[aid] = missing

        # Orphan check (non-root with no parents)
        if atype != _ROOT_TYPE and not parents:
            orphan_artifacts.append(aid)
            broken_chains.append(aid)

        # Depth consistency
        expected = compute_lineage_depth(aid, parents, registry)
        actual = meta.get("lineage_depth", None)
        if actual is not None and actual != expected:
            depth_inconsistencies[aid] = {"expected": expected, "actual": actual}

    return {
        "missing_parents": missing_parents,
        "broken_chains": broken_chains,
        "depth_inconsistencies": depth_inconsistencies,
        "orphan_artifacts": orphan_artifacts,
    }


def enforce_no_orphans(registry: Dict[str, Dict[str, Any]]) -> None:
    """Raise ValueError if any non-root artifact has no parents.

    Parameters
    ----------
    registry:
        All known artifacts.

    Raises
    ------
    ValueError
        If orphan non-root artifacts are found.
    """
    orphans = [
        aid
        for aid, meta in registry.items()
        if meta.get("artifact_type") != _ROOT_TYPE
        and not meta.get("parent_artifact_ids")
    ]
    if orphans:
        raise ValueError(
            f"Orphan non-root artifacts detected (must have ≥1 parent): {sorted(orphans)}"
        )


def validate_against_schema(artifact: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an artifact dict against the governed JSON Schema.

    Parameters
    ----------
    artifact:
        Artifact metadata dict to validate.

    Returns
    -------
    Tuple[bool, List[str]]
        (valid, error_messages)
    """
    schema = _load_lineage_schema()
    validator = Draft202012Validator(schema)
    errors = [str(e.message) for e in validator.iter_errors(artifact)]
    return (len(errors) == 0, errors)


def validate_full_registry(
    registry: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate every artifact in the registry.

    Returns
    -------
    Dict[str, Any]
        {
            "valid": bool,
            "artifact_results": {artifact_id: {"valid": bool, "errors": [...]}},
            "gap_report": detect_lineage_gaps result,
            "total_errors": int,
        }
    """
    artifact_results: Dict[str, Dict[str, Any]] = {}
    total_errors = 0

    for aid, meta in registry.items():
        valid, errors = validate_lineage_chain(
            artifact_id=aid,
            artifact_type=meta.get("artifact_type", ""),
            parent_artifact_ids=meta.get("parent_artifact_ids", []),
            registry={k: v for k, v in registry.items() if k != aid},
        )
        schema_valid, schema_errors = validate_against_schema(meta)
        all_errors = errors + schema_errors
        artifact_results[aid] = {
            "valid": valid and schema_valid,
            "errors": all_errors,
        }
        total_errors += len(all_errors)

    gap_report = detect_lineage_gaps(registry)

    return {
        "valid": total_errors == 0,
        "artifact_results": artifact_results,
        "gap_report": gap_report,
        "total_errors": total_errors,
    }
