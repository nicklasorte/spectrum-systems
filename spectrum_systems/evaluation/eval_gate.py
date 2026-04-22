"""EvalGate: quality gate on evaluation pass rate.

Blocks promotion if eval pass rate falls below the required threshold (default 95%).
Emits gate_decision events to the event log.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class EvalGate:
    """Fail-closed evaluation quality gate.

    The pass_rate threshold defaults to 95%. A rate below threshold
    produces a 'block' decision.
    """

    DEFAULT_THRESHOLD = 0.95

    def __init__(
        self,
        pass_rate_threshold: float = DEFAULT_THRESHOLD,
        event_log: Optional[Any] = None,
    ) -> None:
        if not 0.0 <= pass_rate_threshold <= 1.0:
            raise ValueError(f"pass_rate_threshold must be in [0, 1], got {pass_rate_threshold}")
        self.pass_rate_threshold = pass_rate_threshold
        self._event_log = event_log

    def check(self, eval_results: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate pass rate. Returns gate_decision artifact."""
        passed = eval_results.get("passed", 0)
        total = eval_results.get("total", 0)
        trace_id = eval_results.get("trace_id", "UNKNOWN")

        rate, rate_msg = self._compute_pass_rate(passed, total)
        decision = "allow" if rate >= self.pass_rate_threshold else "block"
        reason = (
            f"pass_rate={rate:.3f} >= threshold={self.pass_rate_threshold:.3f}"
            if decision == "allow"
            else f"pass_rate={rate:.3f} < threshold={self.pass_rate_threshold:.3f} — blocked"
        )

        artifact = {
            "artifact_type": "gate_decision",
            "artifact_id": f"EG-{uuid.uuid4().hex[:12].upper()}",
            "gate_id": "eval_gate",
            "decision": decision,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pass_rate": rate,
            "threshold": self.pass_rate_threshold,
            "passed_count": passed,
            "total_count": total,
            "reason": reason,
            "checks": {"eval_pass_rate_met": decision == "allow"},
            "blocking_checks": [] if decision == "allow" else ["eval_pass_rate_met"],
        }

        if self._event_log is not None:
            self._event_log.log_event(
                trace_id=trace_id,
                event_type="eval_gate",
                data={"decision": decision, "pass_rate": rate},
            )

        return artifact

    def _compute_pass_rate(self, passed: int, total: int) -> Tuple[float, str]:
        if total == 0:
            return 0.0, "no_evals_run"
        return passed / total, "computed"
