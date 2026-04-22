"""Control effectiveness tracker: metrics J1-J5."""

import uuid
from datetime import datetime
from typing import Any, Dict, List


class EffectivenessTracker:
    """Computes and stores ControlEffectivenessMetric artifacts for each measurement type."""

    def __init__(self, artifact_store: Any) -> None:
        self.artifact_store = artifact_store

    # J1: Frozen-route recovery time
    def measure_frozen_route_recovery_time(self, period: str = "daily") -> Dict[str, Any]:
        """Compute mean time from freeze to reversal for routes unfrozen in the measurement window."""
        days_map = {"hourly": 1, "daily": 1, "weekly": 7}
        days = days_map.get(period, 1)

        reversals = self.artifact_store.query(
            {"artifact_type": "control_response_log_reversal", "recency_days": days},
            limit=10000,
        )
        if not reversals:
            return self._write_metric("frozen_route_recovery_time", 0.0, period)

        # Recovery time from reversal timestamp minus original freeze timestamp
        recovery_times: List[float] = []
        for reversal in reversals:
            orig_log_id = reversal.get("original_log_id")
            reversal_ts = reversal.get("timestamp")
            if not orig_log_id or not reversal_ts:
                continue
            original = self.artifact_store.query(
                {"artifact_type": "control_response_log", "log_id": orig_log_id},
                limit=1,
            )
            if original and original[0].get("timestamp"):
                freeze_ts = original[0]["timestamp"]
                try:
                    t_freeze = datetime.fromisoformat(freeze_ts.replace("Z", "+00:00"))
                    t_reversal = datetime.fromisoformat(reversal_ts.replace("Z", "+00:00"))
                    recovery_times.append((t_reversal - t_freeze).total_seconds() / 60)
                except ValueError:
                    pass

        mean_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 0.0
        return self._write_metric("frozen_route_recovery_time", mean_recovery, period)

    # J2: False positive rate
    def measure_false_positive_rate(self, period: str = "daily") -> Dict[str, Any]:
        """Compute rate of control decisions later reversed (false positives)."""
        days_map = {"hourly": 1, "daily": 1, "weekly": 7}
        days = days_map.get(period, 1)

        logs = self.artifact_store.query(
            {"artifact_type": "control_response_log", "recency_days": days},
            limit=10000,
        )
        total = len(logs)
        reversed_count = sum(1 for log in logs if log.get("status") == "reversed")
        fpr = reversed_count / total if total > 0 else 0.0
        return self._write_metric("false_positive_rate", fpr, period)

    # J3: Incidents prevented
    def measure_incidents_prevented(self, period: str = "daily") -> Dict[str, Any]:
        """Count block decisions that had no associated postmortem (successful prevention)."""
        days_map = {"hourly": 1, "daily": 1, "weekly": 7}
        days = days_map.get(period, 1)

        blocks = self.artifact_store.query(
            {"artifact_type": "control_response_log", "control_decision": "block", "recency_days": days},
            limit=10000,
        )
        postmortems = self.artifact_store.query(
            {"artifact_type": "postmortem_artifact", "recency_days": days},
            limit=10000,
        )
        postmortem_routes = {p.get("route_id") for p in postmortems if p.get("route_id")}
        prevented = sum(1 for block in blocks if block.get("route_id") not in postmortem_routes)
        return self._write_metric("incident_prevented", float(prevented), period)

    # J4: Escalation resolution time
    def measure_escalation_resolution_time(self, period: str = "daily") -> Dict[str, Any]:
        """Compute mean time from escalate decision to resolution (allow or block follow-up)."""
        days_map = {"hourly": 1, "daily": 1, "weekly": 7}
        days = days_map.get(period, 1)

        escalations = self.artifact_store.query(
            {"artifact_type": "control_response_log", "control_decision": "escalate", "recency_days": days},
            limit=10000,
        )
        if not escalations:
            return self._write_metric("escalation_resolution_time", 0.0, period)

        resolution_times: List[float] = []
        for esc in escalations:
            route_id = esc.get("route_id")
            esc_ts = esc.get("timestamp")
            if not route_id or not esc_ts:
                continue
            follow_ups = self.artifact_store.query(
                {
                    "artifact_type": "control_response_log",
                    "route_id": route_id,
                    "control_decision_in": ["allow", "block"],
                },
                limit=1,
            )
            if follow_ups and follow_ups[0].get("timestamp"):
                try:
                    t_esc = datetime.fromisoformat(esc_ts.replace("Z", "+00:00"))
                    t_res = datetime.fromisoformat(follow_ups[0]["timestamp"].replace("Z", "+00:00"))
                    resolution_times.append((t_res - t_esc).total_seconds() / 60)
                except ValueError:
                    pass

        mean_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
        return self._write_metric("escalation_resolution_time", mean_resolution, period)

    # J5: Override effectiveness
    def measure_override_effectiveness(self, period: str = "weekly") -> Dict[str, Any]:
        """Fraction of manual overrides that were followed by a promotion without postmortem."""
        days_map = {"hourly": 1, "daily": 1, "weekly": 7}
        days = days_map.get(period, 7)

        overrides = self.artifact_store.query(
            {"artifact_type": "control_response_log", "trigger_signal": "manual_unfreeze", "recency_days": days},
            limit=10000,
        )
        if not overrides:
            return self._write_metric("override_effectiveness", 0.0, period)

        postmortems = self.artifact_store.query(
            {"artifact_type": "postmortem_artifact", "recency_days": days},
            limit=10000,
        )
        postmortem_routes = {p.get("route_id") for p in postmortems if p.get("route_id")}
        effective = sum(1 for ov in overrides if ov.get("route_id") not in postmortem_routes)
        effectiveness = effective / len(overrides) if overrides else 0.0
        return self._write_metric("override_effectiveness", effectiveness, period)

    def _write_metric(self, metric_type: str, value: float, period: str) -> Dict[str, Any]:
        """Write an immutable ControlEffectivenessMetric artifact."""
        metric = {
            "artifact_type": "control_effectiveness_metric",
            "metric_id": f"cem-{metric_type}-{uuid.uuid4().hex[:8]}",
            "metric_type": metric_type,
            "metric_value": value,
            "measurement_period": period,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.artifact_store.put(metric, namespace="dashboard/effectiveness")
        return metric

    def measure_all(self, period: str = "daily") -> List[Dict[str, Any]]:
        """Run all 5 effectiveness measurements and return results."""
        return [
            self.measure_frozen_route_recovery_time(period),
            self.measure_false_positive_rate(period),
            self.measure_incidents_prevented(period),
            self.measure_escalation_resolution_time(period),
            self.measure_override_effectiveness(period),
        ]
