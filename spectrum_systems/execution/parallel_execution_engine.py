"""Phase 3.1: Parallel Execution Engine

Execute slices in parallel instead of serial.
Uses dependency graph from Phase 3.0B.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Set


class ParallelExecutionEngine:
    """Execute slices in parallel where safe."""

    SYNC_TIMEOUT_S = 30

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self.execution_times: Dict[str, float] = {}

    def execute_batch_serial(
        self,
        slices: List[str],
        execution_fn: Callable[[str], Any],
    ) -> Dict[str, Any]:
        """Execute slices serially (baseline)."""
        results: Dict[str, Any] = {}
        total = 0.0

        for slice_id in slices:
            start = time.perf_counter()
            results[slice_id] = execution_fn(slice_id)
            total += time.perf_counter() - start

        self.execution_times["serial"] = total
        return results

    def execute_batch_parallel(
        self,
        slices: List[str],
        execution_fn: Callable[[str], Any],
        dependency_graph: Optional[Dict[str, Set[str]]] = None,
    ) -> Dict[str, Any]:
        """Execute slices in parallel where safe."""
        results: Dict[str, Any] = {}
        total = 0.0

        can_parallelize: Dict[str, bool]
        if dependency_graph is not None:
            can_parallelize = {
                s: len(dependency_graph.get(s, set())) == 0 for s in slices
            }
        else:
            can_parallelize = {s: True for s in slices}

        parallel_slices = [s for s in slices if can_parallelize[s]]
        serial_slices = [s for s in slices if not can_parallelize[s]]

        # Serial first (dependencies must complete before parallelizable work)
        for slice_id in serial_slices:
            start = time.perf_counter()
            results[slice_id] = execution_fn(slice_id)
            total += time.perf_counter() - start

        # Parallel batch
        if parallel_slices:
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(execution_fn, sid): sid
                    for sid in parallel_slices
                }
                for future in as_completed(futures, timeout=self.SYNC_TIMEOUT_S):
                    sid = futures[future]
                    try:
                        results[sid] = future.result()
                    except Exception as exc:
                        results[sid] = {"error": str(exc), "slice_id": sid}
            total += time.perf_counter() - start

        self.execution_times["parallel"] = total
        return results

    def get_latency_improvement(self) -> float:
        """Calculate latency improvement % (parallel vs serial). Non-negative."""
        serial = self.execution_times.get("serial", 0.0)
        parallel = self.execution_times.get("parallel", 0.0)
        if serial == 0.0:
            return 0.0
        return max(0.0, (serial - parallel) / serial * 100)
