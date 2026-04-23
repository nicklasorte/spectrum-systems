"""GOVERNSystem: Consolidated governance evidence packaging + orchestration (Phase 2a).

Absorbs the responsibilities of:
- GOV (Governance Evidence Packaging): records policy-check outcomes and drift evidence
- TLC (Top Level Conductor): lifecycle_check, artifact routing

Single runtime surface for: governance evidence packaging + orchestration routing.
TPA remains canonical policy system. PQX executes work. CDE handles closure decisions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class GOVERNSystem:
    """Governance evidence packaging + orchestration (merged from GOV + TLC)."""

    def __init__(self, event_log: Optional[Any] = None) -> None:
        self._event_log = event_log
        self._routing_manifest: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # From GOV: policy evidence recording (TPA remains policy system)
    # ------------------------------------------------------------------

    def policy_check(
        self,
        artifact: Dict[str, Any],
        policy_ref: Optional[str] = None,
        drift_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Check artifact against referenced policy result for governance evidence packaging.

        Returns (passed, reason). Blocks on policy violation OR critical drift.

        If drift_state is provided and contains critical signals, admission is
        paused to prevent amplification during recovery.
        """
        # Drift check first — most constraining condition
        if drift_state is not None:
            drift_check = self._check_drift_state(drift_state)
            if not drift_check[0]:
                return drift_check

        artifact_type = artifact.get("artifact_type", "")
        if not artifact_type:
            return False, "policy_check BLOCK: artifact_type missing — cannot determine policy scope"

        if artifact.get("policy_blocked"):
            return False, f"policy_check BLOCK: artifact explicitly policy_blocked"

        auth_level = artifact.get("authorization_level", "")
        if auth_level == "unauthorized":
            return False, "policy_check BLOCK: authorization_level=unauthorized"

        reason = f"policy_check PASS: {artifact_type} admitted"
        if policy_ref:
            reason += f" (policy_ref={policy_ref})"

        self._emit_event("lifecycle_transition", artifact, {"phase": "policy_check", "passed": True})
        return True, reason

    def _check_drift_state(self, drift_state: Dict[str, Any]) -> Tuple[bool, str]:
        """Return (allowed, reason) based on current drift signal severities.

        Critical signals block admission entirely; warning signals allow but log.
        """
        signals = drift_state.get("signals", [])

        critical_signals = [s for s in signals if s.get("severity") == "critical"]
        if critical_signals:
            signal_names = ", ".join(s.get("signal_type", "unknown") for s in critical_signals)
            return False, (
                f"policy_check BLOCK: drift critical ({signal_names}) — "
                f"admission paused during recovery"
            )

        warning_signals = [s for s in signals if s.get("severity") == "warning"]
        if warning_signals:
            signal_names = ", ".join(s.get("signal_type", "unknown") for s in warning_signals)
            self._emit_event(
                "drift_warning_admission_allowed",
                {"signals": signal_names},
                {},
            )

        return True, "drift_state PASS: no critical signals"

    def detect_policy_drift(
        self,
        declared_policy: Dict[str, Any],
        observed_behavior: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare declared policy vs observed behavior and return a governance drift report."""
        drift_fields = []
        for key, declared_val in declared_policy.items():
            observed_val = observed_behavior.get(key)
            if observed_val is not None and observed_val != declared_val:
                drift_fields.append({
                    "field": key,
                    "declared": declared_val,
                    "observed": observed_val,
                })

        has_drift = len(drift_fields) > 0
        return {
            "artifact_type": "policy_drift_report",
            "artifact_id": f"PDR-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner_system": "GOVERN",
            "has_drift": has_drift,
            "drift_fields": drift_fields,
            "status": "DRIFT_DETECTED" if has_drift else "NO_DRIFT",
        }

    # ------------------------------------------------------------------
    # From TLC: Orchestration / routing authority
    # ------------------------------------------------------------------

    def lifecycle_check(
        self,
        artifact: Dict[str, Any],
        target_state: str,
    ) -> Tuple[bool, str]:
        """Validate artifact lifecycle transition.

        Returns (allowed, reason). Blocks invalid transitions.
        """
        current_state = artifact.get("lifecycle_state", "")
        artifact_id = artifact.get("artifact_id", "UNKNOWN")

        valid_transitions = {
            "admitted": {"executing_slice_1"},
            "executing_slice_1": {"executing_slice_2"},
            "executing_slice_2": {"executing_slice_3"},
            "executing_slice_3": {"review_pending"},
            "review_pending": {"remediation_pending", "certification_pending"},
            "remediation_pending": {"certification_pending"},
            "certification_pending": {"promoted"},
        }

        allowed_next = valid_transitions.get(current_state, set())
        if target_state not in allowed_next:
            return False, (
                f"lifecycle_check BLOCK: {artifact_id} cannot transition "
                f"{current_state!r} → {target_state!r} (allowed: {sorted(allowed_next)})"
            )

        self._emit_event(
            "lifecycle_transition",
            artifact,
            {"from_state": current_state, "to_state": target_state},
        )
        return True, f"lifecycle_check PASS: {artifact_id} {current_state!r} → {target_state!r}"

    def route_artifact(
        self,
        artifact: Dict[str, Any],
        owner_registry: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """Route artifact to its canonical owner system.

        Returns (owner_system, reason).
        """
        artifact_type = artifact.get("artifact_type", "")
        artifact_id = artifact.get("artifact_id", "UNKNOWN")

        registry = owner_registry or {
            "gate_decision": "EXEC",
            "eval_result": "EVAL",
            "promotion_request": "CDE",
            "failure_artifact": "FRE",
            "policy_drift_report": "GOVERN",
            "roadmap_priority_report": "EXEC",
        }

        owner = registry.get(artifact_type, "UNKNOWN")
        if owner == "UNKNOWN":
            return "UNKNOWN", f"route WARN: no canonical owner for artifact_type={artifact_type!r}"

        self._routing_manifest[artifact_id] = owner
        return owner, f"route PASS: {artifact_id} ({artifact_type}) → {owner}"

    def get_routing_manifest(self) -> Dict[str, str]:
        """Return current routing manifest (artifact_id → owner_system)."""
        return dict(self._routing_manifest)

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
