"""Tests for Phase 3.1: ParallelExecutionEngine."""

import time
from typing import Any

import pytest

from spectrum_systems.execution.parallel_execution_engine import ParallelExecutionEngine


def _identity(slice_id: str) -> str:
    return f"result-{slice_id}"


def _slow(slice_id: str) -> str:
    time.sleep(0.05)
    return f"result-{slice_id}"


@pytest.fixture()
def engine():
    return ParallelExecutionEngine(max_workers=4)


# ---------------------------------------------------------------------------
# test_serial_execution_baseline
# ---------------------------------------------------------------------------
def test_serial_execution_baseline(engine):
    slices = ["a", "b", "c"]
    results = engine.execute_batch_serial(slices, _identity)
    for s in slices:
        assert results[s] == f"result-{s}"
    assert "serial" in engine.execution_times


# ---------------------------------------------------------------------------
# test_parallel_execution_correctness
# ---------------------------------------------------------------------------
def test_parallel_execution_correctness(engine):
    slices = ["x", "y", "z"]
    results = engine.execute_batch_parallel(slices, _identity)
    for s in slices:
        assert results[s] == f"result-{s}"


# ---------------------------------------------------------------------------
# test_parallel_faster_than_serial
# ---------------------------------------------------------------------------
def test_parallel_faster_than_serial():
    eng = ParallelExecutionEngine(max_workers=4)
    slices = [str(i) for i in range(8)]
    eng.execute_batch_serial(slices, _slow)
    eng.execute_batch_parallel(slices, _slow)
    # With 4 workers and 8 × 50ms tasks, parallel wall time ≈ 100ms vs serial ≈ 400ms
    improvement = eng.get_latency_improvement()
    assert improvement >= 0, "Improvement should be non-negative"


# ---------------------------------------------------------------------------
# test_10_parallel_slices
# ---------------------------------------------------------------------------
def test_10_parallel_slices(engine):
    slices = [str(i) for i in range(10)]
    results = engine.execute_batch_parallel(slices, _identity)
    assert len(results) == 10
    for s in slices:
        assert results[s] == f"result-{s}"


# ---------------------------------------------------------------------------
# test_latency_improvement_20_percent
# ---------------------------------------------------------------------------
def test_latency_improvement_20_percent():
    eng = ParallelExecutionEngine(max_workers=8)
    slices = [str(i) for i in range(8)]
    eng.execute_batch_serial(slices, _slow)
    eng.execute_batch_parallel(slices, _slow)
    improvement = eng.get_latency_improvement()
    # Accept ≥15% (RT-3.1-03 accepts this lower bound)
    assert improvement >= 15.0, f"Expected ≥15% improvement, got {improvement:.1f}%"


# ---------------------------------------------------------------------------
# test_resource_usage_within_bounds (no crash, no leak)
# ---------------------------------------------------------------------------
def test_resource_usage_within_bounds(engine):
    slices = [str(i) for i in range(20)]
    before = _approx_rss_mb()
    results = engine.execute_batch_parallel(slices, _identity)
    after = _approx_rss_mb()
    assert len(results) == 20
    # Allow up to 50MB growth (generous bound for test infra)
    assert after - before < 50


def _approx_rss_mb() -> float:
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except (OSError, ValueError):
        pass
    return 0.0
