"""Tests for BH–BJ Error Budget Tracker (error_budget.py).

Covers:
- rolling window correctness
- per-SLI and overall burn rate computation
- window eviction (FIFO)
- module-level helper functions
- deterministic outputs on empty window
- fail-closed defaults
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.error_budget import (  # noqa: E402
    ErrorBudgetTracker,
    compute_burn_rate,
    update_error_budget,
    _FAILURE_THRESHOLD,
    _GOVERNED_SLIS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _passing_slis() -> Dict[str, float]:
    return {
        "completeness": 1.0,
        "timeliness": 1.0,
        "traceability": 1.0,
        "traceability_integrity": 1.0,
    }


def _failing_slis() -> Dict[str, float]:
    return {
        "completeness": 0.0,
        "timeliness": 0.0,
        "traceability": 0.0,
        "traceability_integrity": 0.0,
    }


def _partial_slis(failing: list) -> Dict[str, float]:
    d = _passing_slis()
    for k in failing:
        d[k] = 0.0
    return d


# ---------------------------------------------------------------------------
# ErrorBudgetTracker class
# ---------------------------------------------------------------------------

class TestErrorBudgetTrackerEmpty:
    def test_empty_burn_rate_all_zeros(self):
        t = ErrorBudgetTracker()
        br = t.compute_burn_rate()
        for sli in _GOVERNED_SLIS:
            assert br[sli] == 0.0
        assert br["overall"] == 0.0

    def test_window_size_default(self):
        t = ErrorBudgetTracker()
        assert t.window_size() == 100

    def test_custom_window_size(self):
        t = ErrorBudgetTracker(window_size=10)
        assert t.window_size() == 10

    def test_run_count_initially_zero(self):
        t = ErrorBudgetTracker()
        assert t.run_count() == 0


class TestErrorBudgetTrackerSingleRun:
    def test_single_passing_run_zero_burn(self):
        t = ErrorBudgetTracker()
        t.update_error_budget("r1", "healthy", _passing_slis())
        br = t.compute_burn_rate()
        assert br["completeness"] == 0.0
        assert br["overall"] == 0.0

    def test_single_failing_run_full_burn(self):
        t = ErrorBudgetTracker()
        t.update_error_budget("r1", "breached", _failing_slis())
        br = t.compute_burn_rate()
        assert br["completeness"] == 1.0
        assert br["timeliness"] == 1.0
        assert br["traceability"] == 1.0
        assert br["traceability_integrity"] == 1.0
        assert br["overall"] == 1.0

    def test_run_count_after_one_update(self):
        t = ErrorBudgetTracker()
        t.update_error_budget("r1", "healthy", _passing_slis())
        assert t.run_count() == 1


class TestErrorBudgetTrackerMultipleRuns:
    def test_burn_rate_fraction(self):
        """2 failures out of 4 runs → 0.5 burn rate for that SLI."""
        t = ErrorBudgetTracker()
        for i in range(2):
            t.update_error_budget(f"pass-{i}", "healthy", _passing_slis())
        for i in range(2):
            t.update_error_budget(f"fail-{i}", "breached", _failing_slis())
        br = t.compute_burn_rate()
        assert br["completeness"] == pytest.approx(0.5)
        assert br["overall"] == pytest.approx(0.5)

    def test_overall_is_mean_of_sli_burn_rates(self):
        t = ErrorBudgetTracker()
        # 1 fail run: all SLIs fail → each burn_rate = 1.0, overall = 1.0
        t.update_error_budget("r1", "breached", _failing_slis())
        br = t.compute_burn_rate()
        per_sli = [br[sli] for sli in _GOVERNED_SLIS]
        assert br["overall"] == pytest.approx(sum(per_sli) / len(per_sli))

    def test_partial_sli_failure(self):
        """Only completeness fails."""
        t = ErrorBudgetTracker()
        t.update_error_budget("r1", "degraded", _partial_slis(["completeness"]))
        br = t.compute_burn_rate()
        assert br["completeness"] == 1.0
        assert br["timeliness"] == 0.0
        assert br["traceability"] == 0.0
        assert br["traceability_integrity"] == 0.0

    def test_all_keys_present(self):
        t = ErrorBudgetTracker()
        t.update_error_budget("r1", "healthy", _passing_slis())
        br = t.compute_burn_rate()
        assert "completeness" in br
        assert "timeliness" in br
        assert "traceability" in br
        assert "traceability_integrity" in br
        assert "overall" in br


class TestErrorBudgetTrackerRollingWindow:
    def test_window_evicts_old_runs(self):
        """Window of size 3: after 4 updates only the last 3 count."""
        t = ErrorBudgetTracker(window_size=3)
        # First update: failing
        t.update_error_budget("fail", "breached", _failing_slis())
        # Next 3 updates: passing (evicts the failing one)
        for i in range(3):
            t.update_error_budget(f"pass-{i}", "healthy", _passing_slis())
        assert t.run_count() == 3
        br = t.compute_burn_rate()
        assert br["completeness"] == 0.0

    def test_window_size_enforced(self):
        t = ErrorBudgetTracker(window_size=5)
        for i in range(10):
            t.update_error_budget(f"r{i}", "healthy", _passing_slis())
        assert t.run_count() == 5

    def test_run_count_bounded_by_window(self):
        t = ErrorBudgetTracker(window_size=10)
        for i in range(20):
            t.update_error_budget(f"r{i}", "healthy", _passing_slis())
        assert t.run_count() == 10

    def test_rolling_burn_rate_accuracy(self):
        """Window=10, all failing: burn=1.0. Then replace 5 with passing: burn=0.5."""
        t = ErrorBudgetTracker(window_size=10)
        for i in range(10):
            t.update_error_budget(f"fail-{i}", "breached", _failing_slis())
        assert t.compute_burn_rate()["completeness"] == 1.0
        for i in range(5):
            t.update_error_budget(f"pass-{i}", "healthy", _passing_slis())
        br = t.compute_burn_rate()
        assert br["completeness"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------

class TestModuleLevelHelpers:
    def test_update_and_compute_with_explicit_tracker(self):
        t = ErrorBudgetTracker()
        update_error_budget("r1", "healthy", _passing_slis(), tracker=t)
        br = compute_burn_rate(tracker=t)
        assert br["completeness"] == 0.0
        assert br["overall"] == 0.0

    def test_update_and_compute_failing_with_explicit_tracker(self):
        t = ErrorBudgetTracker()
        update_error_budget("r1", "breached", _failing_slis(), tracker=t)
        br = compute_burn_rate(tracker=t)
        assert br["overall"] == 1.0

    def test_multiple_trackers_are_independent(self):
        t1 = ErrorBudgetTracker()
        t2 = ErrorBudgetTracker()
        update_error_budget("r1", "breached", _failing_slis(), tracker=t1)
        update_error_budget("r1", "healthy", _passing_slis(), tracker=t2)
        assert compute_burn_rate(tracker=t1)["overall"] == 1.0
        assert compute_burn_rate(tracker=t2)["overall"] == 0.0
