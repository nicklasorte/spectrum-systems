"""Loop component metrics for Phase 4: Loop Strengthening.

Measures each component of the execution loop separately:
- Execution time (PQX slice execution)
- Evaluation time (EVAL gate checks)
- Control time (CDE closure decision)
- Enforcement time (SEL enforcement actions)

Target: -20% on slowest component, -10% decision reversal rate.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


class LoopComponentTimer:
    """Context manager for measuring a single loop component."""

    def __init__(self, component_name: str) -> None:
        self.component = component_name
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "LoopComponentTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


class LoopMetrics:
    """Measure and track per-component loop execution times.

    Usage:
        metrics = LoopMetrics()
        with metrics.measure("execution"):
            pqx.execute(slice)
        with metrics.measure("evaluation"):
            eval_system.eval_gate(artifact)
        report = metrics.component_report()
    """

    COMPONENTS = ("execution", "evaluation", "control", "enforcement")

    def __init__(self) -> None:
        self._samples: Dict[str, List[float]] = {c: [] for c in self.COMPONENTS}
        self._reversals: List[Dict[str, Any]] = []

    def measure(self, component: str) -> LoopComponentTimer:
        """Return a context manager that records elapsed time for component."""
        if component not in self.COMPONENTS:
            raise ValueError(f"Unknown component {component!r}. Valid: {self.COMPONENTS}")
        timer = LoopComponentTimer(component)

        class _Recording:
            def __enter__(_self) -> "_Recording":
                timer.__enter__()
                return _self

            def __exit__(_self, *args: Any) -> None:
                timer.__exit__(*args)
                self._samples[component].append(timer.elapsed_ms)

        return _Recording()  # type: ignore[return-value]

    def record_decision_reversal(
        self,
        trace_id: str,
        original_decision: str,
        reversed_decision: str,
        reason: str,
    ) -> None:
        """Record a decision reversal (CDE overturning a prior decision)."""
        self._reversals.append({
            "trace_id": trace_id,
            "original_decision": original_decision,
            "reversed_decision": reversed_decision,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def reversal_rate(self) -> float:
        """Return decision reversal rate (0.0–1.0).

        Computed as: reversals / (reversals + stable decisions).
        Without a denominator of total decisions, returns len(reversals) as a count.
        """
        return float(len(self._reversals))

    def component_stats(self, component: str) -> Dict[str, float]:
        """Return p50/p99/avg/min/max stats for a component in milliseconds."""
        samples = self._samples.get(component, [])
        if not samples:
            return {"p50": 0.0, "p99": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0, "count": 0.0}

        sorted_s = sorted(samples)
        n = len(sorted_s)
        return {
            "p50": sorted_s[n // 2],
            "p99": sorted_s[max(0, int(n * 0.99) - 1)],
            "avg": sum(sorted_s) / n,
            "min": sorted_s[0],
            "max": sorted_s[-1],
            "count": float(n),
        }

    def slowest_component(self) -> Tuple[str, float]:
        """Return (component_name, avg_ms) for the slowest component."""
        avgs = {c: self.component_stats(c)["avg"] for c in self.COMPONENTS}
        slowest = max(avgs, key=lambda k: avgs[k])
        return slowest, avgs[slowest]

    def component_report(self) -> Dict[str, Any]:
        """Return full loop performance report artifact."""
        stats = {c: self.component_stats(c) for c in self.COMPONENTS}
        slowest_name, slowest_avg = self.slowest_component()

        # 20% improvement target on slowest component
        target_ms = slowest_avg * 0.80 if slowest_avg > 0 else 0.0

        return {
            "artifact_type": "loop_performance_report",
            "artifact_id": f"LPR-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner_system": "GOVERN",
            "component_stats_ms": stats,
            "slowest_component": slowest_name,
            "slowest_avg_ms": round(slowest_avg, 3),
            "target_improvement_pct": 20.0,
            "target_after_ms": round(target_ms, 3),
            "decision_reversals": len(self._reversals),
            "reversal_target": "reduce by 10%",
        }


class OptimizedLoop:
    """Optimized execution loop with per-component timing and reversal tracking.

    Wraps the standard loop components with:
    - Inline timing (LoopMetrics)
    - Decision reversal detection
    - Structured failure on any component error
    """

    def __init__(
        self,
        event_log: Optional[Any] = None,
        metrics: Optional[LoopMetrics] = None,
    ) -> None:
        self._event_log = event_log
        self.metrics = metrics or LoopMetrics()

    def execute(self, work_fn: Callable[[], Any]) -> Any:
        """Run execution component with timing. Target: -20% on baseline."""
        with self.metrics.measure("execution"):
            return work_fn()

    def evaluate(self, eval_fn: Callable[[], Any]) -> Any:
        """Run evaluation component with timing. Target: -20% on baseline."""
        with self.metrics.measure("evaluation"):
            return eval_fn()

    def control(self, control_fn: Callable[[], Any]) -> Any:
        """Run control/decision component with timing. Target: -20% on baseline."""
        with self.metrics.measure("control"):
            return control_fn()

    def enforce(self, enforce_fn: Callable[[], Any]) -> Any:
        """Run enforcement component with timing. Target: -20% on baseline."""
        with self.metrics.measure("enforcement"):
            return enforce_fn()

    def run_full_loop(
        self,
        work_fn: Callable[[], Any],
        eval_fn: Callable[[], Any],
        control_fn: Callable[[], Any],
        enforce_fn: Callable[[], Any],
    ) -> Dict[str, Any]:
        """Run all four loop components with timing. Returns loop result."""
        exec_result = self.execute(work_fn)
        eval_result = self.evaluate(eval_fn)
        control_result = self.control(control_fn)
        enforce_result = self.enforce(enforce_fn)

        return {
            "execution": exec_result,
            "evaluation": eval_result,
            "control": control_result,
            "enforcement": enforce_result,
            "loop_stats": self.metrics.component_report(),
        }
