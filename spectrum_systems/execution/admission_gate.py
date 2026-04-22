"""AdmissionGate: validates inputs before execution begins.

Checks: input_schema_valid, context_integrity, security_admission,
resource_availability. Blocks if any check fails. Emits gate_decision events.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


GateCheck = Callable[[Dict[str, Any]], Tuple[bool, str]]


class AdmissionGate:
    """Fail-closed admission gate.

    All four checks must pass for admission. Any failure blocks execution.
    """

    REQUIRED_INPUT_FIELDS = ["artifact_type", "trace_id"]

    def __init__(
        self,
        resource_limit: int = 1000,
        event_log: Optional[Any] = None,
    ) -> None:
        self.resource_limit = resource_limit
        self._event_log = event_log

    def check(self, input_artifact: Dict[str, Any]) -> Dict[str, Any]:
        """Run all admission checks. Returns a gate_decision artifact."""
        checks = {
            "input_schema_valid": self._check_input_schema(input_artifact),
            "context_integrity": self._check_context_integrity(input_artifact),
            "security_admission": self._check_security(input_artifact),
            "resource_availability": self._check_resources(input_artifact),
        }

        failed = [name for name, (passed, _) in checks.items() if not passed]
        decision = "allow" if not failed else "block"
        reasons = {name: msg for name, (_, msg) in checks.items()}

        artifact = self._build_gate_decision(
            gate_id="admission_gate",
            decision=decision,
            checks=checks,
            reasons=reasons,
            trace_id=input_artifact.get("trace_id", "UNKNOWN"),
        )

        if self._event_log is not None:
            self._event_log.log_event(
                trace_id=input_artifact.get("trace_id", "UNKNOWN"),
                event_type="admission_gate",
                data={"decision": decision, "failed_checks": failed},
            )

        return artifact

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_input_schema(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        missing = [f for f in self.REQUIRED_INPUT_FIELDS if not artifact.get(f)]
        if missing:
            return False, f"Missing required fields: {missing}"
        if not isinstance(artifact.get("artifact_type"), str):
            return False, "artifact_type must be a non-empty string"
        return True, "schema_valid"

    def _check_context_integrity(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        if artifact.get("_corrupted"):
            return False, "Input artifact flagged as corrupted"
        trace_id = artifact.get("trace_id", "")
        if trace_id and len(trace_id) < 3:
            return False, f"trace_id too short to be valid: '{trace_id}'"
        return True, "context_integrity_ok"

    def _check_security(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        if artifact.get("security_blocked"):
            return False, "Input flagged by security policy"
        risk = artifact.get("security_risk_level", "")
        if risk == "CRITICAL":
            return False, "CRITICAL security risk — admission denied"
        return True, "security_admitted"

    def _check_resources(self, artifact: Dict[str, Any]) -> Tuple[bool, str]:
        requested = artifact.get("resource_units", 0)
        if requested > self.resource_limit:
            return False, f"Resource request {requested} exceeds limit {self.resource_limit}"
        return True, "resources_available"

    # ------------------------------------------------------------------
    # Artifact builder
    # ------------------------------------------------------------------

    def _build_gate_decision(
        self,
        gate_id: str,
        decision: str,
        checks: Dict[str, Tuple[bool, str]],
        reasons: Dict[str, str],
        trace_id: str,
    ) -> Dict[str, Any]:
        return {
            "artifact_type": "gate_decision",
            "artifact_id": f"GD-{uuid.uuid4().hex[:12].upper()}",
            "gate_id": gate_id,
            "decision": decision,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {name: passed for name, (passed, _) in checks.items()},
            "reasons": reasons,
            "blocking_checks": [name for name, (passed, _) in checks.items() if not passed],
        }
