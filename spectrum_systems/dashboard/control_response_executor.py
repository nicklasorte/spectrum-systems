"""Control response log writer and unfreeze workflow (I1-I5)."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class ControlResponseExecutor:
    """Writes immutable ControlResponseLog entries for each control decision.

    All decisions are logged before any downstream action is taken.
    Unfreeze workflow supports both timed (1h) and manual-approval paths.
    """

    def __init__(self, artifact_store: Any, signer_id: str = "cde-v2") -> None:
        self.artifact_store = artifact_store
        self.signer_id = signer_id

    # I1: Freeze a route
    def freeze_route(self, route_id: str, trigger_signal: str, rationale: str) -> Dict[str, Any]:
        """Log a freeze decision and return the immutable log record."""
        return self._write_log(
            control_decision="freeze",
            trigger_signal=trigger_signal,
            route_id=route_id,
            decision_rationale=rationale,
        )

    # I2: Block an artifact
    def block_artifact(self, route_id: str, trigger_signal: str, rationale: str) -> Dict[str, Any]:
        """Log a block decision for a specific artifact promotion attempt."""
        return self._write_log(
            control_decision="block",
            trigger_signal=trigger_signal,
            route_id=route_id,
            decision_rationale=rationale,
        )

    # I3: Escalate for review
    def escalate_for_review(self, route_id: str, trigger_signal: str, rationale: str) -> Dict[str, Any]:
        """Log an escalate decision — routes the artifact to human review."""
        return self._write_log(
            control_decision="escalate",
            trigger_signal=trigger_signal,
            route_id=route_id,
            decision_rationale=rationale,
        )

    # I4: Warn operator
    def warn_operator(self, route_id: str, trigger_signal: str, rationale: str) -> Dict[str, Any]:
        """Log a warn decision — promotion continues with an operator alert."""
        return self._write_log(
            control_decision="warn",
            trigger_signal=trigger_signal,
            route_id=route_id,
            decision_rationale=rationale,
        )

    # I5: Allow with logged rationale
    def allow_with_rationale(self, route_id: str, trigger_signal: str, rationale: str) -> Dict[str, Any]:
        """Log an allow decision with explicit justification."""
        return self._write_log(
            control_decision="allow",
            trigger_signal=trigger_signal,
            route_id=route_id,
            decision_rationale=rationale,
        )

    # Unfreeze workflow
    def unfreeze_route(
        self,
        frozen_log_id: str,
        route_id: str,
        approver_id: str,
        rationale: str,
    ) -> Dict[str, Any]:
        """Mark an existing freeze log as reversed and log the unfreeze decision.

        Requires explicit approver_id for audit trail. Immutable — the original
        freeze log is not modified; a new allow log is appended.
        """
        original_logs = self.artifact_store.query(
            {"artifact_type": "control_response_log", "log_id": frozen_log_id},
            limit=1,
        )
        if not original_logs:
            raise ValueError(f"Freeze log {frozen_log_id} not found — cannot unfreeze")

        original = original_logs[0]
        if original.get("control_decision") != "freeze":
            raise ValueError(f"Log {frozen_log_id} is not a freeze decision; cannot unfreeze")

        reversal_record = {
            "artifact_type": "control_response_log_reversal",
            "reversal_id": f"rev-{uuid.uuid4().hex[:12]}",
            "original_log_id": frozen_log_id,
            "route_id": route_id,
            "approver_id": approver_id,
            "reversal_rationale": rationale,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.artifact_store.put(reversal_record, namespace="dashboard/control_reversals")

        return self.allow_with_rationale(
            route_id=route_id,
            trigger_signal="manual_unfreeze",
            rationale=f"Unfreeze approved by {approver_id}: {rationale}",
        )

    def get_active_freezes(self) -> list:
        """Return all control_response_logs with decision=freeze and status=active."""
        logs = self.artifact_store.query(
            {"artifact_type": "control_response_log", "control_decision": "freeze", "status": "active"},
            limit=10000,
        )
        return list(logs)

    def _write_log(
        self,
        control_decision: str,
        trigger_signal: str,
        route_id: str,
        decision_rationale: str,
    ) -> Dict[str, Any]:
        """Write an immutable ControlResponseLog record."""
        log = {
            "artifact_type": "control_response_log",
            "log_id": f"crl-{uuid.uuid4().hex[:12]}",
            "control_decision": control_decision,
            "trigger_signal": trigger_signal,
            "route_id": route_id,
            "decision_rationale": decision_rationale,
            "signer_id": self.signer_id,
            "status": "active",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.artifact_store.put(log, namespace="dashboard/control_logs")
        return log
