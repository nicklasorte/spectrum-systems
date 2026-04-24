"""RGE Analysis Engine - Wave 0 repo audit.

Scans the repository to build a snapshot of its current state. The snapshot
drives Principle 1 (where is complexity?) and Principle 2 (where is drift?)
decisions downstream in the roadmap generator.

Emits: rge_analysis_record

Measured signals:
  - context_maturity_level: 0-10 based on presence of key runtime modules
  - active_drift_legs: from roadmap_signal_steering.get_active_drift_legs
  - complexity_budget_by_module: per-module burn rate
  - mg_slice_health: which meta-governance slices are present
  - fragile_points: modules currently flagged as fragile
  - bottlenecks: loop legs with saturation >= 6 contributors
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_signal_steering import (
    get_active_drift_legs,
)

CANONICAL_LOOP_LEGS = (
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "OBS", "SLO",
)

_KEY_MODULES = (
    ("aex", "spectrum_systems/aex"),
    ("pqx", "spectrum_systems/exec_system"),
    ("evl", "spectrum_systems/eval_system"),
    ("tpa", "spectrum_systems/modules/runtime/tpa_complexity_governance.py"),
    ("cde", "spectrum_systems/govern"),
    ("sel", "spectrum_systems/security"),
    ("rep", "spectrum_systems/tracing"),
    ("lin", "spectrum_systems/artifact_store"),
    ("obs", "spectrum_systems/observability"),
    ("slo", "spectrum_systems/modules/runtime/autonomy_guardrails.py"),
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"RAR-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def _measure_context_maturity(repo_root: Path) -> tuple[int, list[str]]:
    present: list[str] = []
    for label, rel_path in _KEY_MODULES:
        if (repo_root / rel_path).exists():
            present.append(label)
    return len(present), present


def _default_leg_counts(repo_root: Path) -> dict[str, int]:
    """Best-effort per-leg contributor count from the filesystem.

    We count non-dunder `.py` files in the relevant module directory. This is
    a signal, not a source of truth; the caller can override.
    """
    counts: dict[str, int] = {leg: 0 for leg in CANONICAL_LOOP_LEGS}
    dir_map = {
        "AEX": "spectrum_systems/aex",
        "PQX": "spectrum_systems/exec_system",
        "EVL": "spectrum_systems/eval_system",
        "TPA": "spectrum_systems/modules/runtime",
        "CDE": "spectrum_systems/govern",
        "SEL": "spectrum_systems/security",
        "REP": "spectrum_systems/tracing",
        "LIN": "spectrum_systems/artifact_store",
        "OBS": "spectrum_systems/observability",
        "SLO": "spectrum_systems/modules/runtime",
    }
    for leg, rel in dir_map.items():
        path = repo_root / rel
        if not path.exists() or not path.is_dir():
            continue
        counts[leg] = sum(
            1
            for p in path.glob("*.py")
            if not p.name.startswith("_")
        )
    return counts


def analyze_repository(
    *,
    repo_root: str | Path,
    run_id: str,
    trace_id: str,
    roadmap_signal_bundle: dict[str, Any] | None = None,
    complexity_budgets: list[dict[str, Any]] | None = None,
    fragile_points: list[str] | None = None,
    mg_slices_present: list[str] | None = None,
) -> dict[str, Any]:
    """Produce an rge_analysis_record for the given repo state.

    Args:
        repo_root: path to the repo root
        run_id, trace_id: lineage identifiers
        roadmap_signal_bundle: optional steering bundle; drift extracted from it
        complexity_budgets: optional list of complexity_budget artifacts
        fragile_points: optional list of module paths flagged as fragile
        mg_slices_present: optional list of MG-## slice IDs currently wired

    Returns:
        schema-validated rge_analysis_record
    """
    root = Path(repo_root).resolve()

    maturity, present = _measure_context_maturity(root)
    drift_legs = get_active_drift_legs(roadmap_signal_bundle) if roadmap_signal_bundle else []
    leg_counts = _default_leg_counts(root)

    budgets_by_module: dict[str, dict[str, Any]] = {}
    for budget in complexity_budgets or []:
        module = str(budget.get("module_or_path", "unknown"))
        budgets_by_module[module] = {
            "budget_status": budget.get("budget_status"),
            "burn_rate": budget.get("burn_rate"),
            "current_complexity": budget.get("current_complexity"),
            "baseline_complexity": budget.get("baseline_complexity"),
        }

    bottlenecks = sorted(
        leg for leg, count in leg_counts.items() if count >= 6
    )

    record = {
        "artifact_type": "rge_analysis_record",
        "schema_version": "1.0.0",
        "record_id": _stable_id({"run_id": run_id, "trace_id": trace_id}),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "repo_root": str(root),
        "context_maturity_level": maturity,
        "context_maturity_max": len(_KEY_MODULES),
        "modules_present": sorted(present),
        "active_drift_legs": sorted(drift_legs),
        "complexity_budget_by_module": budgets_by_module,
        "mg_slice_health": {
            "present": sorted(set(mg_slices_present or [])),
            "missing": [],
        },
        "fragile_points": sorted(set(fragile_points or [])),
        "bottlenecks": bottlenecks,
        "leg_saturation": leg_counts,
    }

    validate_artifact(record, "rge_analysis_record")
    return record
