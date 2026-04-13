"""DRX — Drift Response eXecutor."""

from __future__ import annotations

from typing import Any


def detect_drift_signals(*, metrics: dict[str, float], thresholds: dict[str, float]) -> dict[str, Any]:
    triggered = []
    for key, value in metrics.items():
        threshold = float(thresholds.get(key, 1e9))
        if float(value) > threshold:
            triggered.append({"signal": key, "value": float(value), "threshold": threshold})
    return {
        "artifact_type": "drift_signal_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "signals": triggered,
        "drift_detected": len(triggered) > 0,
    }


def build_drift_response_plan(*, signal_record: dict[str, Any], runbook_ref: str) -> dict[str, Any]:
    actions = [f"investigate:{item['signal']}" for item in signal_record.get("signals", [])]
    return {
        "artifact_type": "drift_response_plan",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "runbook_ref": runbook_ref,
        "actions": actions,
        "action_count": len(actions),
    }


def emit_maintain_cycle_record(*, cycle_id: str, signal_record: dict[str, Any], response_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "maintain_cycle_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "cycle_id": cycle_id,
        "drift_detected": signal_record.get("drift_detected", False),
        "signal_count": len(signal_record.get("signals", [])),
        "response_plan_ref": response_plan,
    }


def emit_invariant_gap_record(*, cycle_id: str, gaps: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": "invariant_gap_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "cycle_id": cycle_id,
        "gaps": sorted(set(gaps)),
    }


def emit_eval_expansion_record(*, cycle_id: str, expansion_targets: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": "eval_expansion_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "cycle_id": cycle_id,
        "required_eval_targets": sorted(set(expansion_targets)),
    }
