"""DRT: Drift-to-remediation enforcement.

When drift signals are emitted, a remediation plan must appear within
MAX_REMEDIATION_HOURS or MAX_REMEDIATION_EXECUTIONS. Otherwise the
system is frozen.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

MAX_REMEDIATION_HOURS = 24
MAX_REMEDIATION_EXECUTIONS = 3


class DriftRemediationEnforcer:
    """Enforces remediation deadlines for active drift signals."""

    def __init__(self) -> None:
        self._drift_signals: List[Dict] = []
        self._remediations: Dict[str, Dict] = {}  # drift_id → remediation
        self._execution_counts: Dict[str, int] = {}  # drift_id → count

    # ── write ─────────────────────────────────────────────────────────────

    def register_drift_signal(self, drift_id: str, description: str) -> Dict:
        signal = {
            "drift_id": drift_id,
            "description": description,
            "created_at": time.time(),
            "created_at_iso": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        self._drift_signals.append(signal)
        self._execution_counts[drift_id] = 0
        return signal

    def register_remediation(self, drift_id: str, plan: Dict) -> None:
        self._remediations[drift_id] = plan

    def increment_execution(self, drift_id: str) -> int:
        self._execution_counts[drift_id] = self._execution_counts.get(drift_id, 0) + 1
        return self._execution_counts[drift_id]

    # ── enforcement ───────────────────────────────────────────────────────

    def check_remediation_deadlines(self) -> Tuple[str, Dict]:
        """Check if any drift signals have exceeded their remediation deadline.

        Returns (action, report) where action ∈ {PROCEED, FREEZE, ESCALATE}.
        """
        now = time.time()
        report: Dict = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "drifts": [],
        }

        for signal in self._drift_signals:
            if signal["status"] != "active":
                continue

            drift_id = signal["drift_id"]
            has_remediation = drift_id in self._remediations
            age_hours = (now - signal["created_at"]) / 3600
            exec_count = self._execution_counts.get(drift_id, 0)

            if not has_remediation and (
                age_hours > MAX_REMEDIATION_HOURS
                or exec_count >= MAX_REMEDIATION_EXECUTIONS
            ):
                entry = {
                    "drift_id": drift_id,
                    "status": "overdue",
                    "age_hours": round(age_hours, 2),
                    "execution_count": exec_count,
                    "action": "FREEZE",
                }
                report["drifts"].append(entry)
                return "FREEZE", report

            report["drifts"].append({
                "drift_id": drift_id,
                "has_remediation": has_remediation,
                "age_hours": round(age_hours, 2),
                "execution_count": exec_count,
                "status": "on_track",
            })

        return "PROCEED", report
