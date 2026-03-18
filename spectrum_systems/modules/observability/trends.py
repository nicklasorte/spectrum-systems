"""
Trend Tracking — spectrum_systems/modules/observability/trends.py

Run-over-run trend computation for observability records.

Compares a current set of records against a previous set and surfaces
meaningful deltas in scores, error rates, and latency.  Trend history
is persisted under ``data/observability_history/`` as JSON snapshots.

Design principles
-----------------
- Trends are computed from structured records only.
- A snapshot stores the aggregated summary, not raw records.
- All delta values are signed (positive = improvement, negative = regression).

Public API
----------
compare_runs(current_records, previous_records) -> dict
save_snapshot(snapshot, label) -> Path
load_snapshot(label) -> dict | None
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.observability.aggregation import (
    compute_error_distribution,
    compute_grounding_failure_rate,
    compute_human_disagreement,
    compute_latency_stats,
    compute_pass_metrics,
)
from spectrum_systems.modules.observability.metrics import ObservabilityRecord

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DEFAULT_HISTORY_DIR = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "observability_history"
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def compare_runs(
    current_records: List[ObservabilityRecord],
    previous_records: List[ObservabilityRecord],
) -> Dict[str, Any]:
    """Compare a current batch of records to a previous batch.

    Computes signed deltas for key signals:

    - Score deltas (structural, semantic, grounding)
    - Latency delta (mean)
    - Error rate change
    - Grounding failure rate change
    - Human disagreement rate change

    Positive delta = improvement.  Negative delta = regression.

    Parameters
    ----------
    current_records:
        Records from the most recent run.
    previous_records:
        Records from the prior run (baseline).

    Returns
    -------
    dict
        Structured trend report with keys ``current``, ``previous``,
        and ``deltas``.
    """
    current_summary = _summarise(current_records)
    previous_summary = _summarise(previous_records)

    deltas: Dict[str, Optional[float]] = {}

    def _delta(curr_key: str, prev_key: Optional[str] = None) -> Optional[float]:
        pk = prev_key or curr_key
        c = current_summary.get(curr_key)
        p = previous_summary.get(pk)
        if c is None or p is None:
            return None
        return c - p  # positive = improvement

    deltas["structural_score"] = _delta("avg_structural_score")
    deltas["semantic_score"] = _delta("avg_semantic_score")
    deltas["grounding_score"] = _delta("avg_grounding_score")
    # Latency: negate so that positive delta = improvement (less latency is better),
    # matching the convention used for scores where positive delta always means better.
    _lat_curr = current_summary.get("avg_latency_ms")
    _lat_prev = previous_summary.get("avg_latency_ms")
    deltas["latency_ms"] = (
        (_lat_prev - _lat_curr) if _lat_curr is not None and _lat_prev is not None else None
    )
    # For failure and disagreement rates: lower is better, so delta = prev - curr
    # (positive delta = improvement, matching the convention for scores).
    for rate_key in ("failure_rate", "grounding_failure_rate", "human_disagreement_rate"):
        _c = current_summary.get(rate_key)
        _p = previous_summary.get(rate_key)
        deltas[rate_key] = (
            (_p - _c) if _c is not None and _p is not None else None
        )

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "current": current_summary,
        "previous": previous_summary,
        "deltas": deltas,
    }


def save_snapshot(
    records: List[ObservabilityRecord],
    label: str,
    history_dir: Optional[Path] = None,
) -> Path:
    """Persist an aggregated snapshot for later trend comparison.

    Parameters
    ----------
    records:
        Records to summarise and store.
    label:
        Snapshot label (e.g. ``"run_2026_03_01"``).  Used as filename.
    history_dir:
        Directory to write the snapshot.  Defaults to
        ``data/observability_history/``.

    Returns
    -------
    Path
        Path to the written JSON file.
    """
    dest_dir = Path(history_dir) if history_dir else _DEFAULT_HISTORY_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    summary = _summarise(records)
    summary["snapshot_label"] = label
    dest = dest_dir / f"{label}.json"
    dest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return dest


def load_snapshot(
    label: str,
    history_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Load a previously saved snapshot.

    Parameters
    ----------
    label:
        Snapshot label (the filename stem used in ``save_snapshot``).
    history_dir:
        Directory to read from.  Defaults to ``data/observability_history/``.

    Returns
    -------
    dict | None
        The snapshot summary dict, or ``None`` if not found.
    """
    dest_dir = Path(history_dir) if history_dir else _DEFAULT_HISTORY_DIR
    path = dest_dir / f"{label}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _summarise(records: List[ObservabilityRecord]) -> Dict[str, Any]:
    """Build a compact summary dict for a list of records."""
    if not records:
        return {
            "record_count": 0,
            "avg_structural_score": None,
            "avg_semantic_score": None,
            "avg_grounding_score": None,
            "avg_latency_ms": None,
            "failure_rate": None,
            "grounding_failure_rate": None,
            "human_disagreement_rate": None,
            "top_error_type": None,
        }

    pass_m = compute_pass_metrics(records)
    overall = pass_m["overall"]
    grounding_m = compute_grounding_failure_rate(records)
    disagreement_m = compute_human_disagreement(records)
    error_m = compute_error_distribution(records)

    return {
        "record_count": overall["record_count"],
        "avg_structural_score": overall["avg_structural_score"],
        "avg_semantic_score": overall["avg_semantic_score"],
        "avg_grounding_score": overall["avg_grounding_score"],
        "avg_latency_ms": overall["avg_latency_ms"],
        "failure_rate": overall["failure_rate"],
        "grounding_failure_rate": grounding_m["overall_failure_rate"],
        "human_disagreement_rate": disagreement_m["overall_disagreement_rate"],
        "top_error_type": error_m["top_error_type"],
    }
