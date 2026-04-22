"""Phase 3.0: Baseline Metrics Collection

Measure performance before any optimization:
- Execution → eval → promotion cycle time
- Signal latency (p50, p99)
- Throughput (slices/second)
- Resource usage (CPU, memory)
"""

from __future__ import annotations

import time
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class BaselineMetricsCollector:
    """Collect baseline metrics before optimization."""

    def __init__(self, artifact_store: str = "/tmp/artifacts") -> None:
        self.store = Path(artifact_store)
        self.store.mkdir(exist_ok=True, parents=True)
        self.metrics: Dict[str, Any] = {}

    def measure_execution_cycle_time(
        self, execution_fn: Callable[[], Any], num_runs: int = 10
    ) -> Dict[str, float]:
        """Measure execution → eval → promotion cycle time."""
        times = []
        for _ in range(num_runs):
            start = time.perf_counter()
            execution_fn()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        sorted_times = sorted(times)
        return {
            "p50": sorted_times[len(sorted_times) // 2],
            "p99": sorted_times[int(len(sorted_times) * 0.99)],
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }

    def measure_signal_latency(
        self,
        signal_publish_fn: Callable[[], Any],
        subscriber_fn: Callable[[], Any],
        num_runs: int = 100,
    ) -> Dict[str, float]:
        """Measure signal publish → receive latency."""
        latencies = []
        for _ in range(num_runs):
            start = time.perf_counter()
            signal_publish_fn()
            subscriber_fn()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        sorted_lat = sorted(latencies)
        return {
            "p50_ms": sorted_lat[len(sorted_lat) // 2],
            "p99_ms": sorted_lat[int(len(sorted_lat) * 0.99)],
            "avg_ms": sum(latencies) / len(latencies),
        }

    def measure_throughput(
        self, execution_fn: Callable[[], Any], duration_seconds: int = 10
    ) -> float:
        """Measure slices executed per second."""
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < duration_seconds:
            execution_fn()
            count += 1
        return count / duration_seconds

    def measure_resource_usage(
        self, execution_fn: Callable[[], Any], num_runs: int = 5
    ) -> Dict[str, float]:
        """Measure memory delta during execution."""
        memory_deltas: list[float] = []

        for _ in range(num_runs):
            mem_before = self._rss_mb()
            execution_fn()
            mem_after = self._rss_mb()
            memory_deltas.append(mem_after - mem_before)

        return {
            "avg_memory_delta_mb": sum(memory_deltas) / len(memory_deltas),
            "max_memory_delta_mb": max(memory_deltas),
        }

    def collect_all_baseline_metrics(
        self,
        execution_fn: Callable[[], Any],
        signal_fn: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Collect all baseline metrics and store immutably."""
        baseline: Dict[str, Any] = {
            "artifact_type": "baseline_metrics_artifact",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_cycle_time_seconds": self.measure_execution_cycle_time(execution_fn),
            "resource_usage": self.measure_resource_usage(execution_fn),
        }

        if signal_fn is not None:
            baseline["signal_latency_ms"] = self.measure_signal_latency(
                signal_fn, lambda: None
            )

        artifact_file = self.store / "baseline_metrics.json"
        with open(artifact_file, "w") as f:
            json.dump(baseline, f, indent=2)

        self.metrics = baseline
        return baseline

    # ------------------------------------------------------------------
    @staticmethod
    def _rss_mb() -> float:
        """Return RSS in MB using /proc/self/status (Linux) or 0.0 fallback."""
        try:
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024.0
        except (OSError, ValueError):
            pass
        return 0.0
