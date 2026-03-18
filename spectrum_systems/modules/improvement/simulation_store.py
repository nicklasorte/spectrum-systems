"""
Simulation Store — spectrum_systems/modules/improvement/simulation_store.py

Persists and retrieves SimulationResult objects from flat JSON files under
``data/simulation_results/{simulation_id}.json``.

Mirrors the flat-JSON storage pattern used by remediation_store.py.

Public API
----------
save_simulation_result(result, store_dir) -> Path
load_simulation_result(simulation_id, store_dir) -> SimulationResult
list_simulation_results(store_dir, filters) -> List[SimulationResult]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.improvement.simulation import SimulationResult

# ---------------------------------------------------------------------------
# Default storage path
# ---------------------------------------------------------------------------

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "simulation_results"
)

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def save_simulation_result(
    result: SimulationResult,
    store_dir: Optional[Path] = None,
) -> Path:
    """Persist a SimulationResult to ``{store_dir}/{simulation_id}.json``.

    Parameters
    ----------
    result:
        The ``SimulationResult`` to save.
    store_dir:
        Directory to save to.  Defaults to ``data/simulation_results/``.

    Returns
    -------
    Path
        Path to the saved file.

    Raises
    ------
    FileExistsError
        If a result with this simulation_id already exists.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    path = target_dir / f"{result.simulation_id}.json"
    if path.exists():
        raise FileExistsError(
            f"Simulation result '{result.simulation_id}' already exists at {path}"
        )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2)
    return path


def load_simulation_result(
    simulation_id: str,
    store_dir: Optional[Path] = None,
) -> SimulationResult:
    """Load a single SimulationResult by simulation_id.

    Parameters
    ----------
    simulation_id:
        The unique identifier of the simulation result to load.
    store_dir:
        Directory to load from.  Defaults to ``data/simulation_results/``.

    Returns
    -------
    SimulationResult

    Raises
    ------
    FileNotFoundError
        If no result with this simulation_id exists in the store.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    path = target_dir / f"{simulation_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No simulation result with id '{simulation_id}' found at {path}"
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return SimulationResult.from_dict(data)


def list_simulation_results(
    store_dir: Optional[Path] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[SimulationResult]:
    """Load all SimulationResult objects from the store directory.

    Parameters
    ----------
    store_dir:
        Directory to load from.  Defaults to ``data/simulation_results/``.
    filters:
        Optional dict of field → value pairs used to filter results.
        Supported keys: ``simulation_status``, ``remediation_id``,
        ``cluster_id``, ``promotion_recommendation``.

    Returns
    -------
    List[SimulationResult]
        All matching results, sorted by ``simulation_id``.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    if not target_dir.exists():
        return []

    results: List[SimulationResult] = []
    for p in sorted(target_dir.glob("*.json")):
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        result = SimulationResult.from_dict(data)
        if _matches_filters(result, filters or {}):
            results.append(result)
    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _matches_filters(result: SimulationResult, filters: Dict[str, Any]) -> bool:
    """Return True if the result matches all provided filter criteria."""
    if "simulation_status" in filters:
        if result.simulation_status != filters["simulation_status"]:
            return False
    if "remediation_id" in filters:
        if result.remediation_id != filters["remediation_id"]:
            return False
    if "cluster_id" in filters:
        if result.cluster_id != filters["cluster_id"]:
            return False
    if "promotion_recommendation" in filters:
        if result.promotion_recommendation != filters["promotion_recommendation"]:
            return False
    return True
