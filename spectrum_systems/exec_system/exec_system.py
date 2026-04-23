"""EXECSystem: Consolidated execution + planning (Phase 2b).

Absorbs the responsibilities of:
- TPA (Trust Policy Application): trust admission, lineage validation
- PRG (Program Governance): roadmap alignment, priority reporting

Single authority for: execution admissibility + program-level planning.
No orchestration (GOVERN-owned). No execution itself (PQX-owned).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class EXECSystem:
    """Execution Admissibility + Program Planning (merged from TPA + PRG).

    Authority boundaries:
    - Owns: trust admission, lineage completeness, roadmap alignment
    - Does NOT own: orchestration (GOVERN), execution (PQX), closure (CDE)
    """

    def __init__(self, event_log: Optional[Any] = None) -> None:
        self._event_log = event_log

    # ------------------------------------------------------------------
    # From TPA: Trust + admissibility
    # ------------------------------------------------------------------

    def exec_check(
        self,
        artifact: Dict[str, Any],
        required_fields: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Validate execution admissibility.

        Checks: trust envelope, lineage, scope.
        Returns (admitted, reason).
        """
        required = required_fields or ["artifact_type", "trace_id"]
        missing = [f for f in required if not artifact.get(f)]
        if missing:
            return False, f"exec_check BLOCK: missing required fields {missing}"

        if not artifact.get("lineage_complete", True):
            return False, "exec_check BLOCK: lineage_complete=false — cannot admit without full lineage"

        if artifact.get("trust_blocked"):
            return False, "exec_check BLOCK: artifact flagged trust_blocked"

        artifact_type = artifact.get("artifact_type", "")
        trace_id = artifact.get("trace_id", "")

        self._emit_event("admission_gate", artifact, {"decision": "allow", "system": "EXEC"})
        return True, f"exec_check PASS: {artifact_type} (trace={trace_id}) admitted"

    def validate_lineage(
        self,
        artifact_id: str,
        lineage_refs: List[str],
    ) -> Tuple[bool, str]:
        """Validate lineage completeness for an artifact."""
        if not lineage_refs:
            return False, f"lineage BLOCK: {artifact_id} has no lineage references"
        empty = [r for r in lineage_refs if not r or r.strip() == ""]
        if empty:
            return False, f"lineage BLOCK: {artifact_id} has {len(empty)} empty lineage refs"
        return True, f"lineage PASS: {artifact_id} has {len(lineage_refs)} valid lineage refs"

    def trust_scope_check(
        self,
        artifact: Dict[str, Any],
        max_scope_items: int = 50,
    ) -> Tuple[bool, str]:
        """Check execution scope against complexity budget."""
        scope_items = artifact.get("scope_items", 0)
        if isinstance(scope_items, list):
            scope_items = len(scope_items)
        if scope_items > max_scope_items:
            return False, (
                f"trust_scope BLOCK: scope_items={scope_items} exceeds "
                f"budget={max_scope_items}"
            )
        return True, f"trust_scope PASS: scope_items={scope_items} within budget={max_scope_items}"

    # ------------------------------------------------------------------
    # From PRG: Program governance + roadmap
    # ------------------------------------------------------------------

    def roadmap_alignment_check(
        self,
        artifact: Dict[str, Any],
        active_roadmap_items: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Check that artifact work aligns with the active roadmap.

        Returns (aligned, reason).
        """
        roadmap_ref = artifact.get("roadmap_ref", "")
        if not roadmap_ref:
            return False, "roadmap_alignment BLOCK: roadmap_ref missing — cannot confirm alignment"

        if active_roadmap_items is not None:
            if roadmap_ref not in active_roadmap_items:
                return False, (
                    f"roadmap_alignment BLOCK: roadmap_ref={roadmap_ref!r} "
                    "not in active roadmap items"
                )

        return True, f"roadmap_alignment PASS: roadmap_ref={roadmap_ref!r} confirmed"

    def generate_priority_report(
        self,
        health_status: str,
        health_metrics: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Generate roadmap priority report based on system health status."""
        metrics = health_metrics or {}

        if health_status == "critical":
            prioritized = ["fix_drift", "reduce_exceptions", "emergency_review"]
            paused = ["new_features", "optimization", "refactoring"]
        elif health_status == "degraded":
            prioritized = ["stabilize_drift", "monitor_exceptions"]
            paused = ["optimization"]
        else:
            prioritized = []
            paused = []

        recommendation_map = {
            "critical": "HALT NON-CRITICAL WORK. Focus on stabilization.",
            "degraded": "Pause optimization. Maintain focus on stability.",
        }
        recommendation = recommendation_map.get(health_status, "Proceed with roadmap as planned.")

        return {
            "artifact_type": "roadmap_priority_report",
            "artifact_id": f"RPR-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner_system": "EXEC",
            "current_health": health_status,
            "health_metrics": metrics,
            "prioritized_items": prioritized,
            "paused_items": paused,
            "recommendation": recommendation,
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
