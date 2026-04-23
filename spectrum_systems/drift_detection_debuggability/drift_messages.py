"""
DriftMessageGenerator: Produces structured What/Why/How messages for drift failures.
Replaces raw event dicts with operator-readable diagnostics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DriftMessage:
    """Structured drift failure message in What/Why/How format."""
    what_failed: str
    why_happened: str
    how_to_fix: str
    context: Dict
    next_steps: str
    confidence: float       # 0-1
    severity: str           # CRITICAL, HIGH, MEDIUM, LOW
    similar_cases: List[str] = field(default_factory=list)


# Maps signal_type to human-readable Why and How templates.
_WHY_TEMPLATES: Dict[str, str] = {
    "decision_divergence": (
        "The same context_class is producing different outcomes across requests. "
        "This indicates the decision policy or model state has shifted from baseline."
    ),
    "exception_rate": (
        "Exception artifacts are accumulating faster than the baseline rate. "
        "A rising exception rate signals upstream instability or unhandled edge cases."
    ),
    "eval_pass_drop": (
        "Eval pass rate dropped below the warning threshold. "
        "Recent prompt, policy, or model changes likely degraded output quality."
    ),
    "trace_gap": (
        "A growing fraction of artifacts are missing trace linkage. "
        "Trace propagation has broken somewhere in the pipeline."
    ),
    "silent_drift": (
        "Downstream degradation is present but no drift signal was emitted. "
        "Detection threshold is too high or a monitoring node went offline."
    ),
    "false_positive": (
        "The alert fired on a transient metric spike rather than sustained drift. "
        "The baseline aggregation window captured noise."
    ),
    "distributed_disagreement": (
        "Detection nodes disagree on drift status for the same time window. "
        "Clock skew or inconsistent metric sources are the most likely cause."
    ),
}

_HOW_TEMPLATES: Dict[str, str] = {
    "decision_divergence": (
        "1. Review control_decision artifacts from the last 2 hours for context_class inconsistency. "
        "2. Check for recent policy or prompt template changes. "
        "3. Re-calibrate decision thresholds if context definitions have drifted."
    ),
    "exception_rate": (
        "1. Pull the latest exception_artifacts and group by error_class. "
        "2. Identify the top error_class and trace to source artifact. "
        "3. Apply exception_conversion_rules or escalate to CDE for policy update."
    ),
    "eval_pass_drop": (
        "1. Identify which eval_cases are failing via the eval dashboard. "
        "2. Check for model version rollout or prompt template change in last 24h. "
        "3. Roll back the change or file an improvement artifact."
    ),
    "trace_gap": (
        "1. Query artifact_store for artifacts missing trace_id in the last 1h. "
        "2. Identify the code path that created them and verify trace propagation. "
        "3. Patch the instrumentation gap and re-run affected flows."
    ),
    "silent_drift": (
        "1. Lower detection threshold by 20% and re-run detection on the affected window. "
        "2. Confirm all detection nodes are online and reporting. "
        "3. File a threshold_calibration artifact to prevent recurrence."
    ),
    "false_positive": (
        "1. Expand baseline aggregation window from 5m to 15m to absorb spikes. "
        "2. Verify no real degradation exists in the affected metric. "
        "3. Mark this alert as false_positive and update sensitivity config."
    ),
    "distributed_disagreement": (
        "1. Compare metric timestamps across nodes—look for clock skew > 30s. "
        "2. Verify all nodes pull from the same metric source. "
        "3. Synchronize node clocks and rerun consensus check."
    ),
}


class DriftMessageGenerator:
    """Generate structured What/Why/How messages from raw drift events."""

    def generate_message(self, drift_event: Dict) -> DriftMessage:
        """
        Convert a raw drift detection event to a structured DriftMessage.

        Expected drift_event keys:
            signal_type, signal, metric, region, service,
            baseline_value, current_value, threshold,
            detection_nodes, agreement, severity, confidence,
            similar_cases (optional)
        """
        signal_type = drift_event.get("signal_type", "unknown")
        signal = drift_event.get("signal", signal_type)
        metric = drift_event.get("metric", "unknown")
        region = drift_event.get("region", "unknown")
        service = drift_event.get("service", "unknown")
        baseline = drift_event.get("baseline_value", 0.0)
        current = drift_event.get("current_value", 0.0)
        threshold = drift_event.get("threshold", 0.0)
        severity = drift_event.get("severity", "MEDIUM")
        confidence = float(drift_event.get("confidence", 0.8))
        similar_cases = drift_event.get("similar_cases", [])

        change_pct = self._change_percent(baseline, current)

        what = (
            f"{signal} drifted on {metric} in {service} ({region}). "
            f"Value moved from {baseline} → {current} ({change_pct:+.1f}%), "
            f"crossing threshold {threshold}."
        )

        why = _WHY_TEMPLATES.get(signal_type, "The metric exceeded its configured threshold.")
        how = _HOW_TEMPLATES.get(signal_type, "Investigate the affected metric and apply standard remediation.")

        next_steps = (
            f"Open the drift trace for {metric} and run the RCA guide decision tree. "
            f"Target resolution: <10 minutes. Escalate if not resolved in 15 minutes."
        )

        return DriftMessage(
            what_failed=what,
            why_happened=why,
            how_to_fix=how,
            context=drift_event,
            next_steps=next_steps,
            confidence=confidence,
            severity=severity,
            similar_cases=similar_cases,
        )

    def format_for_display(self, message: DriftMessage) -> str:
        """Format a DriftMessage for human display."""
        lines = [
            f"DRIFT DETECTED [{message.severity}] (confidence: {message.confidence:.0%})",
            "",
            f"WHAT FAILED:    {message.what_failed}",
            "",
            f"WHY IT HAPPENED: {message.why_happened}",
            "",
            f"HOW TO FIX:     {message.how_to_fix}",
            "",
            f"NEXT STEPS:     {message.next_steps}",
        ]
        if message.similar_cases:
            lines += ["", f"SIMILAR CASES:  {', '.join(message.similar_cases)}"]
        return "\n".join(lines)

    @staticmethod
    def _change_percent(baseline: float, current: float) -> float:
        if baseline == 0:
            return 0.0
        return ((current - baseline) / abs(baseline)) * 100
