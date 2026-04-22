"""Tests for Phase 3.0: BaselineMetricsCollector."""

import json
import time
from pathlib import Path

import pytest

from spectrum_systems.observability.baseline_metrics import BaselineMetricsCollector


def _noop() -> int:
    return 1


def _slow() -> None:
    time.sleep(0.001)


@pytest.fixture()
def collector(tmp_path):
    return BaselineMetricsCollector(artifact_store=str(tmp_path))


# ---------------------------------------------------------------------------
# test_execution_cycle_time_measured
# ---------------------------------------------------------------------------
def test_execution_cycle_time_measured(collector):
    result = collector.measure_execution_cycle_time(_noop, num_runs=5)
    assert set(result.keys()) == {"p50", "p99", "avg", "min", "max"}
    assert result["min"] >= 0
    assert result["max"] >= result["min"]
    assert result["avg"] >= result["min"]


# ---------------------------------------------------------------------------
# test_signal_latency_measured
# ---------------------------------------------------------------------------
def test_signal_latency_measured(collector):
    result = collector.measure_signal_latency(_noop, lambda: None, num_runs=20)
    assert set(result.keys()) == {"p50_ms", "p99_ms", "avg_ms"}
    assert result["p50_ms"] >= 0
    assert result["p99_ms"] >= result["p50_ms"]


# ---------------------------------------------------------------------------
# test_throughput_measured
# ---------------------------------------------------------------------------
def test_throughput_measured(collector):
    # Use 1-second window to keep test fast
    rate = collector.measure_throughput(_noop, duration_seconds=1)
    assert rate > 0, "Throughput should be positive"


# ---------------------------------------------------------------------------
# test_resource_usage_measured
# ---------------------------------------------------------------------------
def test_resource_usage_measured(collector):
    result = collector.measure_resource_usage(_noop, num_runs=3)
    assert "avg_memory_delta_mb" in result
    assert "max_memory_delta_mb" in result
    # delta can be negative (GC) but must be a number
    assert isinstance(result["avg_memory_delta_mb"], float)


# ---------------------------------------------------------------------------
# test_collect_all_stores_artifact
# ---------------------------------------------------------------------------
def test_collect_all_stores_artifact(collector, tmp_path):
    baseline = collector.collect_all_baseline_metrics(_noop)
    assert baseline["artifact_type"] == "baseline_metrics_artifact"
    assert "execution_cycle_time_seconds" in baseline

    stored = json.loads((tmp_path / "baseline_metrics.json").read_text())
    assert stored["artifact_type"] == "baseline_metrics_artifact"
