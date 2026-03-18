"""
Cluster Store — spectrum_systems/modules/error_taxonomy/cluster_store.py

Persists and retrieves ErrorCluster objects from flat JSON files under
``data/error_clusters/{cluster_id}.json``.

Design principles
-----------------
- Mirrors the flat-JSON storage pattern used by ErrorClassificationRecord.
- All I/O is explicit; no hidden singletons.
- Filters are applied in-memory after loading, keeping the interface simple.

Public API
----------
save_cluster(cluster, store_dir) -> Path
load_cluster(cluster_id, store_dir) -> ErrorCluster
list_clusters(filters, store_dir) -> List[ErrorCluster]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.error_taxonomy.clustering import ErrorCluster

# ---------------------------------------------------------------------------
# Default storage path
# ---------------------------------------------------------------------------

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "error_clusters"
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def save_cluster(
    cluster: ErrorCluster,
    store_dir: Optional[Path] = None,
) -> Path:
    """Persist an ErrorCluster to ``{store_dir}/{cluster_id}.json``.

    Parameters
    ----------
    cluster:
        The ``ErrorCluster`` to save.
    store_dir:
        Directory to save to.  Defaults to ``data/error_clusters/``.

    Returns
    -------
    Path
        Path to the saved file.

    Raises
    ------
    FileExistsError
        If a cluster with this ID already exists.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    path = target_dir / f"{cluster.cluster_id}.json"
    if path.exists():
        raise FileExistsError(
            f"Cluster '{cluster.cluster_id}' already exists at {path}"
        )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cluster.to_dict(), fh, indent=2)
    return path


def load_cluster(
    cluster_id: str,
    store_dir: Optional[Path] = None,
) -> ErrorCluster:
    """Load an ErrorCluster by ID.

    Parameters
    ----------
    cluster_id:
        The unique cluster identifier.
    store_dir:
        Directory to load from.  Defaults to ``data/error_clusters/``.

    Returns
    -------
    ErrorCluster

    Raises
    ------
    FileNotFoundError
        If no cluster with this ID exists.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    path = target_dir / f"{cluster_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Cluster '{cluster_id}' not found at {path}")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return ErrorCluster.from_dict(data)


def list_clusters(
    filters: Optional[Dict[str, Any]] = None,
    store_dir: Optional[Path] = None,
) -> List[ErrorCluster]:
    """Load all clusters, optionally filtering by attribute values.

    Supported filter keys
    ---------------------
    ``taxonomy_version``
        Only return clusters with this taxonomy version.
    ``primary_error_code``
        Only return clusters whose signature primary code matches.
    ``dominant_family``
        Only return clusters whose dominant family matches.
    ``min_record_count``
        Only return clusters with at least this many records.

    Parameters
    ----------
    filters:
        Optional dict of filter criteria.
    store_dir:
        Directory to load from.  Defaults to ``data/error_clusters/``.

    Returns
    -------
    List[ErrorCluster]
        Clusters matching all filter criteria.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    if not target_dir.exists():
        return []

    clusters: List[ErrorCluster] = []
    for p in sorted(target_dir.glob("*.json")):
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        clusters.append(ErrorCluster.from_dict(data))

    if not filters:
        return clusters

    result = []
    for c in clusters:
        if "taxonomy_version" in filters and c.taxonomy_version != filters["taxonomy_version"]:
            continue
        if "primary_error_code" in filters and c.cluster_signature["primary_error_code"] != filters["primary_error_code"]:
            continue
        if "dominant_family" in filters and c.cluster_signature["dominant_family"] != filters["dominant_family"]:
            continue
        if "min_record_count" in filters and c.metrics["record_count"] < filters["min_record_count"]:
            continue
        result.append(c)
    return result
