"""EVALSystem: Consolidated evaluation + checking (Phase 2b).

Absorbs the responsibilities of:
- WPG (Working Paper Generator): provenance, working-paper artifacts
- CHK (Checkpoint and Resume Governance): batch/umbrella constraint validation

Single authority for: evaluation provenance + execution constraint checking.
No execution (PQX-owned). No orchestration (GOVERN-owned).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class EVALSystem:
    """Evaluation Provenance + Constraint Checking (merged from WPG + CHK).

    Authority boundaries:
    - Owns: working-paper generation, batch/umbrella constraint validation
    - Does NOT own: execution (PQX), orchestration (GOVERN), admission (EXEC)
    """

    def __init__(self, event_log: Optional[Any] = None) -> None:
        self._event_log = event_log

    # ------------------------------------------------------------------
    # From WPG: Provenance / working-paper
    # ------------------------------------------------------------------

    def generate_working_paper(
        self,
        execution_artifact: Dict[str, Any],
        execution_output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate working-paper artifact for an execution slice.

        Every execution slice must have a working paper for auditability.
        """
        trace_id = execution_artifact.get("trace_id", "UNKNOWN")
        artifact_id = execution_artifact.get("artifact_id", "UNKNOWN")
        artifact_type = execution_artifact.get("artifact_type", "unknown")

        paper = {
            "artifact_type": "working_paper",
            "artifact_id": f"WP-{uuid.uuid4().hex[:10].upper()}",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner_system": "EVAL",
            "source_artifact_id": artifact_id,
            "source_artifact_type": artifact_type,
            "execution_output_ref": (execution_output or {}).get("artifact_id", ""),
            "provenance_complete": True,
        }

        self._emit_event("eval_start", execution_artifact, {
            "phase": "working_paper_generated",
            "paper_id": paper["artifact_id"],
        })
        return paper

    def validate_provenance(
        self,
        artifact: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Validate that artifact has complete provenance chain."""
        artifact_id = artifact.get("artifact_id", "UNKNOWN")

        if not artifact.get("trace_id"):
            return False, f"provenance BLOCK: {artifact_id} missing trace_id"

        if artifact.get("execution_without_provenance"):
            return False, f"provenance BLOCK: {artifact_id} flagged execution_without_provenance"

        return True, f"provenance PASS: {artifact_id} has complete provenance"

    # ------------------------------------------------------------------
    # From CHK: Constraint checking
    # ------------------------------------------------------------------

    def batch_constraint_check(
        self,
        batch_artifact: Dict[str, Any],
        max_slices_per_batch: int = 10,
    ) -> Tuple[bool, str]:
        """Validate batch-level execution constraints.

        Returns (passed, reason). Blocks on violation.
        """
        batch_id = batch_artifact.get("batch_id", "UNKNOWN")
        slices = batch_artifact.get("slices", [])
        slice_count = len(slices) if isinstance(slices, list) else batch_artifact.get("slice_count", 0)

        if slice_count > max_slices_per_batch:
            return False, (
                f"batch_constraint BLOCK: {batch_id} has {slice_count} slices, "
                f"exceeds max={max_slices_per_batch}"
            )

        if batch_artifact.get("constraint_violated"):
            return False, f"batch_constraint BLOCK: {batch_id} constraint_violated=true"

        return True, f"batch_constraint PASS: {batch_id} ({slice_count} slices, max={max_slices_per_batch})"

    def umbrella_constraint_check(
        self,
        umbrella_artifact: Dict[str, Any],
        max_batches_per_umbrella: int = 5,
    ) -> Tuple[bool, str]:
        """Validate umbrella-level execution constraints."""
        umbrella_id = umbrella_artifact.get("umbrella_id", "UNKNOWN")
        batches = umbrella_artifact.get("batches", [])
        batch_count = len(batches) if isinstance(batches, list) else umbrella_artifact.get("batch_count", 0)

        if batch_count > max_batches_per_umbrella:
            return False, (
                f"umbrella_constraint BLOCK: {umbrella_id} has {batch_count} batches, "
                f"exceeds max={max_batches_per_umbrella}"
            )

        if umbrella_artifact.get("umbrella_constraint_violated"):
            return False, f"umbrella_constraint BLOCK: {umbrella_id} umbrella_constraint_violated=true"

        return True, f"umbrella_constraint PASS: {umbrella_id} ({batch_count} batches, max={max_batches_per_umbrella})"

    def checkpoint_resume_check(
        self,
        checkpoint_artifact: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Validate checkpoint/resume state for phase transitions."""
        checkpoint_id = checkpoint_artifact.get("checkpoint_id", "UNKNOWN")
        checkpoint_state = checkpoint_artifact.get("checkpoint_state", "")

        valid_states = {"ready", "resumable", "complete"}
        if checkpoint_state not in valid_states:
            return False, (
                f"checkpoint BLOCK: {checkpoint_id} state={checkpoint_state!r} "
                f"not in valid states {valid_states}"
            )

        return True, f"checkpoint PASS: {checkpoint_id} state={checkpoint_state!r}"

    # ------------------------------------------------------------------
    # Unified eval gate (replaces separate WPG + CHK gates)
    # ------------------------------------------------------------------

    def eval_gate(
        self,
        artifact: Dict[str, Any],
        eval_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Unified evaluation gate: provenance + constraints + pass rate.

        Returns gate_decision artifact.
        """
        trace_id = artifact.get("trace_id", "UNKNOWN")
        checks: Dict[str, Tuple[bool, str]] = {}

        checks["provenance_complete"] = self.validate_provenance(artifact)

        if "batch_id" in artifact:
            checks["batch_constraint"] = self.batch_constraint_check(artifact)

        if eval_results:
            passed = eval_results.get("passed", 0)
            total = eval_results.get("total", 0)
            rate = (passed / total) if total > 0 else 0.0
            threshold = eval_results.get("threshold", 0.95)
            if rate >= threshold:
                checks["eval_pass_rate"] = (True, f"pass_rate={rate:.3f} >= threshold={threshold:.3f}")
            else:
                checks["eval_pass_rate"] = (False, f"pass_rate={rate:.3f} < threshold={threshold:.3f} — blocked")

        failed = [name for name, (passed_flag, _) in checks.items() if not passed_flag]
        decision = "allow" if not failed else "block"

        self._emit_event("eval_gate", artifact, {"decision": decision, "failed_checks": failed})

        return {
            "artifact_type": "gate_decision",
            "artifact_id": f"EV-{uuid.uuid4().hex[:10].upper()}",
            "gate_id": "eval_gate",
            "decision": decision,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner_system": "EVAL",
            "checks": {name: passed_flag for name, (passed_flag, _) in checks.items()},
            "reasons": {name: reason for name, (_, reason) in checks.items()},
            "blocking_checks": failed,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_event(
        self,
        event_type: str,
        artifact: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._event_log is None:
            return
        trace_id = artifact.get("trace_id", "UNKNOWN")
        self._event_log.log_event(
            trace_id=trace_id,
            event_type=event_type,
            data=data or {},
        )
