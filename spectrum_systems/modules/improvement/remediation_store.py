"""
Remediation Store — spectrum_systems/modules/improvement/remediation_store.py

Persists and retrieves RemediationPlan objects from flat JSON files under
``data/remediation_plans/{remediation_id}.json``.

Mirrors the flat-JSON storage pattern used by ValidatedCluster and
ErrorClassificationRecord stores.

Public API
----------
save_remediation_plan(plan, store_dir) -> Path
load_remediation_plan(remediation_id, store_dir) -> RemediationPlan
list_remediation_plans(store_dir, filters) -> List[RemediationPlan]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.improvement.remediation_mapping import RemediationPlan

# ---------------------------------------------------------------------------
# Default storage path
# ---------------------------------------------------------------------------

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "remediation_plans"
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def save_remediation_plan(
    plan: RemediationPlan,
    store_dir: Optional[Path] = None,
) -> Path:
    """Persist a RemediationPlan to ``{store_dir}/{remediation_id}.json``.

    Parameters
    ----------
    plan:
        The ``RemediationPlan`` to save.
    store_dir:
        Directory to save to.  Defaults to ``data/remediation_plans/``.

    Returns
    -------
    Path
        Path to the saved file.

    Raises
    ------
    FileExistsError
        If a plan with this ID already exists.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    path = target_dir / f"{plan.remediation_id}.json"
    if path.exists():
        raise FileExistsError(
            f"Remediation plan '{plan.remediation_id}' already exists at {path}"
        )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(plan.to_dict(), fh, indent=2)
    return path


def load_remediation_plan(
    remediation_id: str,
    store_dir: Optional[Path] = None,
) -> RemediationPlan:
    """Load a single RemediationPlan by ID.

    Parameters
    ----------
    remediation_id:
        The unique identifier of the plan to load.
    store_dir:
        Directory to load from.  Defaults to ``data/remediation_plans/``.

    Returns
    -------
    RemediationPlan

    Raises
    ------
    FileNotFoundError
        If no plan with this ID exists in the store.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    path = target_dir / f"{remediation_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No remediation plan with id '{remediation_id}' found at {path}"
        )
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return RemediationPlan.from_dict(data)


def list_remediation_plans(
    store_dir: Optional[Path] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[RemediationPlan]:
    """Load all RemediationPlan objects from the store directory.

    Parameters
    ----------
    store_dir:
        Directory to load from.  Defaults to ``data/remediation_plans/``.
    filters:
        Optional dict of field → value pairs used to filter results.
        Supported keys: ``mapping_status``, ``cluster_id``.

    Returns
    -------
    List[RemediationPlan]
        All matching plans, sorted by ``remediation_id``.
    """
    target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
    if not target_dir.exists():
        return []

    results: List[RemediationPlan] = []
    for p in sorted(target_dir.glob("*.json")):
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        plan = RemediationPlan.from_dict(data)
        if _matches_filters(plan, filters or {}):
            results.append(plan)
    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _matches_filters(plan: RemediationPlan, filters: Dict[str, Any]) -> bool:
    """Return True if the plan matches all provided filter criteria."""
    if "mapping_status" in filters:
        if plan.mapping_status != filters["mapping_status"]:
            return False
    if "cluster_id" in filters:
        if plan.cluster_id != filters["cluster_id"]:
            return False
    return True
