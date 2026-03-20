"""Error Budget Tracker (BH–BJ SLO Control Plane).

Maintains a rolling window of SLO run history and derives per-SLI error
budget burn rates.

Design
------
- Rolling window of the last N runs (default 100).
- Per-SLI failure rate = fraction of runs where that SLI was below threshold.
- Burn rate per SLI = failure rate for that SLI.
- Overall burn rate = mean of per-SLI burn rates.

Public API
----------
ErrorBudgetTracker             – stateful rolling-window tracker class
update_error_budget(run_id, slo_status, slis)
compute_burn_rate()            – {sli_name: float, "overall": float}
"""

from __future__ import annotations

import collections
from typing import Any, Deque, Dict, Optional, Tuple

# Default rolling window size
_DEFAULT_WINDOW: int = 100

# SLI failure threshold — a run is counted as a failure for an SLI when its
# value falls below this level.
_FAILURE_THRESHOLD: float = 0.95

_GOVERNED_SLIS = (
    "completeness",
    "timeliness",
    "traceability",
    "traceability_integrity",
)


class ErrorBudgetTracker:
    """Rolling-window error budget tracker.

    Parameters
    ----------
    window_size:
        Maximum number of runs to retain in the rolling window.  Older runs
        are evicted as new ones are added (FIFO).
    failure_threshold:
        SLI value below which a run is counted as a failure for that SLI.
        Defaults to 0.95.
    """

    def __init__(
        self,
        window_size: int = _DEFAULT_WINDOW,
        failure_threshold: float = _FAILURE_THRESHOLD,
    ) -> None:
        self._window_size = max(1, window_size)
        self._failure_threshold = float(failure_threshold)
        # Each entry: (run_id, slo_status, slis_dict)
        self._runs: Deque[Tuple[str, str, Dict[str, float]]] = collections.deque(
            maxlen=self._window_size
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_error_budget(
        self,
        run_id: str,
        slo_status: str,
        slis: Dict[str, float],
    ) -> None:
        """Record a new run result in the rolling window.

        Parameters
        ----------
        run_id:
            Unique identifier for this run (e.g. execution_id from validator engine).
        slo_status:
            ``"healthy"``, ``"degraded"``, or ``"breached"``.
        slis:
            ``{sli_name: float}`` dict for this run.
        """
        self._runs.append((str(run_id), str(slo_status), dict(slis or {})))

    def compute_burn_rate(self) -> Dict[str, float]:
        """Compute per-SLI burn rates over the rolling window.

        Returns
        -------
        dict
            ``{sli_name: burn_rate, ..., "overall": float}``
            All values are in ``[0.0, 1.0]``.  Returns all zeros when no runs
            have been recorded.
        """
        if not self._runs:
            result: Dict[str, float] = {sli: 0.0 for sli in _GOVERNED_SLIS}
            result["overall"] = 0.0
            return result

        n = len(self._runs)
        failure_counts: Dict[str, int] = {sli: 0 for sli in _GOVERNED_SLIS}

        for _run_id, _slo_status, slis in self._runs:
            for sli in _GOVERNED_SLIS:
                value = slis.get(sli, 0.0)
                if value < self._failure_threshold:
                    failure_counts[sli] += 1

        burn_rates: Dict[str, float] = {}
        for sli in _GOVERNED_SLIS:
            burn_rates[sli] = round(failure_counts[sli] / n, 6)

        overall = round(sum(burn_rates.values()) / len(_GOVERNED_SLIS), 6)
        burn_rates["overall"] = overall
        return burn_rates

    def window_size(self) -> int:
        """Return the configured rolling window size."""
        return self._window_size

    def run_count(self) -> int:
        """Return the number of runs currently in the window."""
        return len(self._runs)


# ---------------------------------------------------------------------------
# Module-level singleton helpers (convenience wrappers)
# ---------------------------------------------------------------------------

_default_tracker: ErrorBudgetTracker = ErrorBudgetTracker()


def update_error_budget(
    run_id: str,
    slo_status: str,
    slis: Dict[str, float],
    tracker: Optional[ErrorBudgetTracker] = None,
) -> None:
    """Record a run result using the module-level default tracker (or a
    caller-provided one).

    Parameters
    ----------
    run_id:
        Unique run identifier.
    slo_status:
        SLO health status for this run.
    slis:
        Per-SLI measurements for this run.
    tracker:
        Optional :class:`ErrorBudgetTracker` instance.  Defaults to the
        module-level singleton.
    """
    (tracker or _default_tracker).update_error_budget(run_id, slo_status, slis)


def compute_burn_rate(
    tracker: Optional[ErrorBudgetTracker] = None,
) -> Dict[str, float]:
    """Compute burn rates using the module-level default tracker (or a
    caller-provided one).

    Returns
    -------
    dict
        ``{sli_name: burn_rate, "overall": float}``
    """
    return (tracker or _default_tracker).compute_burn_rate()
