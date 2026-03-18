"""
Validated Cluster Store — spectrum_systems/modules/error_taxonomy/validated_cluster_store.py

Persists and retrieves ValidatedCluster objects from flat JSON files under
``data/validated_clusters/{cluster_id}.json``.

Design principles
-----------------
- Mirrors the flat-JSON storage pattern used by ErrorCluster and
  ErrorClassificationRecord.
- All I/O is explicit; no hidden singletons.

Public API
----------
save_validated_cluster(validated_cluster, store_dir) -> Path
load_validated_clusters(store_dir) -> List[ValidatedCluster]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from spectrum_systems.modules.error_taxonomy.cluster_validation import ValidatedCluster

# ---------------------------------------------------------------------------
# Default storage path
# ---------------------------------------------------------------------------

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "validated_clusters"
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def save_validated_cluster(
    validated_cluster: ValidatedCluster,
    store_dir: Optional[Path] = None,
) -> Path:
    """Persist a ValidatedCluster to ``{store_dir}/{cluster_id}.json``.

    Parameters
    ----------
    validated_cluster:
        The ``ValidatedCluster`` to save.
    store_dir:
        Directory to save to.  Defaults to ``data/validated_clusters/``.

    Returns
    -------
    Path
        Path to the saved file.

    Raises
    ------
    FileExistsError
        If a validated cluster with this ID already exists.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    path = target_dir / f"{validated_cluster.cluster_id}.json"
    if path.exists():
        raise FileExistsError(
            f"Validated cluster '{validated_cluster.cluster_id}' already exists at {path}"
        )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(validated_cluster.to_dict(), fh, indent=2)
    return path


def load_validated_clusters(
    store_dir: Optional[Path] = None,
) -> List[ValidatedCluster]:
    """Load all validated clusters from the store directory.

    Parameters
    ----------
    store_dir:
        Directory to load from.  Defaults to ``data/validated_clusters/``.

    Returns
    -------
    List[ValidatedCluster]
        All validated clusters found in the directory, sorted by cluster_id.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    if not target_dir.exists():
        return []

    results: List[ValidatedCluster] = []
    for p in sorted(target_dir.glob("*.json")):
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        results.append(ValidatedCluster.from_dict(data))
    return results
