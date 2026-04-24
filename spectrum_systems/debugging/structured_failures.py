"""Structured failure messages for debuggability (Phase 5).

Replaces cryptic stack traces and ValueError messages with structured,
actionable failure records that include:
- WHAT failed (system + gate)
- WHY it failed (specific check + observed value)
- NEXT steps (runbook reference)
- CONTEXT (trace_id, artifact_id, sequence number)

Target: -20% RCA time from baseline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Runbook index: gate → runbook path
RUNBOOK_INDEX: Dict[str, str] = {
    "admission_gate": "docs/runbooks/admission_gate_failures.md",
    "eval_gate": "docs/runbooks/eval_gate_failures.md",
    "promotion_gate": "docs/runbooks/promotion_gate_failures.md",
    "GATE-F": "docs/runbooks/gate_f_failures.md",
    "GATE-C": "docs/runbooks/gate_c_failures.md",
    "GATE-J": "docs/runbooks/gate_j_failures.md",
    "GATE-O": "docs/runbooks/gate_o_failures.md",
    "GATE-R": "docs/runbooks/gate_r_failures.md",
    "GATE-I": "docs/runbooks/gate_i_failures.md",
    "policy_check": "docs/runbooks/govern_policy_failures.md",
    "lifecycle_check": "docs/runbooks/govern_lifecycle_failures.md",
    "exec_check": "docs/runbooks/exec_admission_failures.md",
    "batch_constraint_check": "docs/runbooks/eval_constraint_failures.md",
    "umbrella_constraint_check": "docs/runbooks/eval_constraint_failures.md",
    "provenance_check": "docs/runbooks/eval_provenance_failures.md",
    "rge_justification_gate": "docs/runbooks/rge_justification_gate_failures.md",
    "rge_loop_contribution": "docs/runbooks/rge_loop_contribution_failures.md",
    "rge_debuggability_gate": "docs/runbooks/rge_debuggability_gate_failures.md",
    "default": "docs/runbooks/system_debug_guide.md",
}


class ClearFailureMessage:
    """Build structured, actionable failure messages.

    Instead of:
        ValueError: missing field 'trace_id' at line 42

    Produces:
        FAILURE: EXEC/exec_check
        WHAT: Artifact failed execution admission check
        WHY: Required field 'trace_id' missing (artifact_type=gate_decision)
        NEXT: See runbook: docs/runbooks/exec_admission_failures.md
        CONTEXT: trace_id=UNKNOWN, artifact_id=GD-ABC123, seq=7
    """

    def __init__(
        self,
        gate_id: str,
        system: str,
        check_name: str,
        observed_value: Any,
        expected_value: Any,
        trace_id: str = "UNKNOWN",
        artifact_id: str = "UNKNOWN",
        seq: Optional[int] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.gate_id = gate_id
        self.system = system
        self.check_name = check_name
        self.observed_value = observed_value
        self.expected_value = expected_value
        self.trace_id = trace_id
        self.artifact_id = artifact_id
        self.seq = seq
        self.extra_context = extra_context or {}

    def format(self) -> str:
        """Return human-readable failure message with RCA context."""
        runbook = RUNBOOK_INDEX.get(self.gate_id, RUNBOOK_INDEX["default"])
        seq_line = f", seq={self.seq}" if self.seq is not None else ""

        lines = [
            f"",
            f"FAILURE: {self.system}/{self.gate_id}",
            f"",
            f"  WHAT: Artifact failed {self.check_name} check",
            f"  WHY:  Observed {self.observed_value!r}, expected {self.expected_value!r}",
            f"  NEXT: See runbook: {runbook}",
            f"  CONTEXT: trace_id={self.trace_id}, artifact_id={self.artifact_id}{seq_line}",
        ]

        if self.extra_context:
            for key, val in self.extra_context.items():
                lines.append(f"          {key}={val!r}")

        return "\n".join(lines)

    def to_artifact(self) -> Dict[str, Any]:
        """Return structured failure artifact for the event log and FRE."""
        return {
            "artifact_type": "structured_failure",
            "artifact_id": f"SF-{uuid.uuid4().hex[:10].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gate_id": self.gate_id,
            "system": self.system,
            "check_name": self.check_name,
            "observed_value": str(self.observed_value),
            "expected_value": str(self.expected_value),
            "trace_id": self.trace_id,
            "artifact_id_ref": self.artifact_id,
            "seq": self.seq,
            "runbook": RUNBOOK_INDEX.get(self.gate_id, RUNBOOK_INDEX["default"]),
            "extra_context": self.extra_context,
            "human_message": self.format(),
        }


def format_gate_failure(
    gate_decision: Dict[str, Any],
    system: str = "UNKNOWN",
) -> str:
    """Format a gate_decision artifact as a clear failure message.

    Suitable for logging and operator display.
    """
    gate_id = gate_decision.get("gate_id", "unknown_gate")
    trace_id = gate_decision.get("trace_id", "UNKNOWN")
    artifact_id = gate_decision.get("artifact_id", "UNKNOWN")
    blocking = gate_decision.get("blocking_checks", [])
    reasons = gate_decision.get("reasons", {})

    if gate_decision.get("decision") == "allow":
        return f"PASS: {system}/{gate_id} (trace={trace_id})"

    lines = [
        f"",
        f"FAILURE: {system}/{gate_id}",
        f"",
        f"  WHAT: Gate blocked — {len(blocking)} check(s) failed",
    ]

    for check in blocking:
        reason = reasons.get(check, "no reason provided")
        lines.append(f"  WHY ({check}): {reason}")

    runbook = RUNBOOK_INDEX.get(gate_id, RUNBOOK_INDEX["default"])
    lines.append(f"  NEXT: See runbook: {runbook}")
    lines.append(f"  CONTEXT: trace_id={trace_id}, artifact_id={artifact_id}")

    return "\n".join(lines)


def format_system_error(
    system: str,
    operation: str,
    error: Exception,
    trace_id: str = "UNKNOWN",
    artifact_id: str = "UNKNOWN",
) -> str:
    """Format a system-level error as a structured failure message."""
    error_type = type(error).__name__
    runbook = RUNBOOK_INDEX.get(operation, RUNBOOK_INDEX["default"])

    return (
        f"\n"
        f"FAILURE: {system}/{operation}\n"
        f"\n"
        f"  WHAT: {error_type} during {operation}\n"
        f"  WHY:  {str(error)}\n"
        f"  NEXT: See runbook: {runbook}\n"
        f"  CONTEXT: trace_id={trace_id}, artifact_id={artifact_id}"
    )
