"""PromotionGate: final gate before artifact promotion.

Checks: lineage_complete, replay_deterministic, all_prior_gates_passed,
security_approved, slo_compliant. All must pass. Any failure blocks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class PromotionGate:
    """Fail-closed promotion gate.

    All five checks must pass. A single failure blocks promotion.
    """

    def __init__(self, event_log: Optional[Any] = None) -> None:
        self._event_log = event_log

    def check(self, promotion_request: Dict[str, Any]) -> Dict[str, Any]:
        """Run all promotion checks. Returns gate_decision artifact."""
        trace_id = promotion_request.get("trace_id", "UNKNOWN")
        checks = {
            "lineage_complete": self._check_lineage(promotion_request),
            "replay_deterministic": self._check_replay(promotion_request),
            "all_prior_gates_passed": self._check_prior_gates(promotion_request),
            "security_approved": self._check_security(promotion_request),
            "slo_compliant": self._check_slo(promotion_request),
        }

        failed = [name for name, (passed, _) in checks.items() if not passed]
        decision = "allow" if not failed else "block"
        reasons = {name: msg for name, (_, msg) in checks.items()}

        artifact = {
            "artifact_type": "gate_decision",
            "artifact_id": f"PG-{uuid.uuid4().hex[:12].upper()}",
            "gate_id": "promotion_gate",
            "decision": decision,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {name: passed for name, (passed, _) in checks.items()},
            "reasons": reasons,
            "blocking_checks": failed,
        }

        if self._event_log is not None:
            self._event_log.log_event(
                trace_id=trace_id,
                event_type="promotion_gate",
                data={"decision": decision, "failed_checks": failed},
            )

        return artifact

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_lineage(self, req: Dict[str, Any]) -> Tuple[bool, str]:
        if not req.get("lineage_complete", False):
            return False, "lineage_complete=false — cannot promote without full lineage"
        return True, "lineage_complete"

    def _check_replay(self, req: Dict[str, Any]) -> Tuple[bool, str]:
        if not req.get("replay_deterministic", False):
            return False, "replay_deterministic=false — non-deterministic output blocked"
        return True, "replay_deterministic"

    def _check_prior_gates(self, req: Dict[str, Any]) -> Tuple[bool, str]:
        gates = req.get("prior_gates_passed", None)
        if gates is None or gates is False:
            return False, "prior_gates_passed not confirmed"
        if isinstance(gates, list) and not all(gates):
            return False, f"Some prior gates failed: {gates}"
        return True, "all_prior_gates_passed"

    def _check_security(self, req: Dict[str, Any]) -> Tuple[bool, str]:
        if not req.get("security_approved", False):
            return False, "security_approved=false — security sign-off required for promotion"
        return True, "security_approved"

    def _check_slo(self, req: Dict[str, Any]) -> Tuple[bool, str]:
        budget = req.get("budget_used", 0)
        budget_limit = req.get("budget_limit", None)
        if budget_limit is not None and budget > budget_limit:
            return False, f"budget_used={budget} exceeds budget_limit={budget_limit} — SLO violation"
        if not req.get("slo_compliant", True):
            return False, "slo_compliant=false — SLO requirements not met"
        return True, "slo_compliant"
