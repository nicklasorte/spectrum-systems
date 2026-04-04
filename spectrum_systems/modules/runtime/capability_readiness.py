"""Deterministic capability-readiness posture evaluation (BATCH-A2)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


_STATE_RANK = {"unsafe": 0, "constrained": 1, "supervised": 2, "autonomous": 3}


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _normalize_outcome(item: Any) -> str:
    if not isinstance(item, dict):
        return "indeterminate"
    raw = str(item.get("result_status") or item.get("status") or "indeterminate").strip().lower()
    if raw in {"pass", "passed", "success", "allow"}:
        return "pass"
    if raw in {"fail", "failed", "block", "error"}:
        return "fail"
    return "indeterminate"


def evaluate_capability_readiness(
    *,
    roadmap_id: str,
    trace_id: str,
    created_at: str,
    batch_delivery_reports: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    autonomy_decisions: list[dict[str, Any]],
    exception_routing_outputs: list[dict[str, Any]],
    drift_signals: list[dict[str, Any]],
    replay_metrics: list[dict[str, Any]],
    unresolved_risks: list[str],
    recent_batches_considered: int = 5,
    prior_readiness_state: str | None = None,
) -> dict[str, Any]:
    """Compute deterministic governed readiness posture from recent runtime signals."""
    window = max(1, int(recent_batches_considered))
    delivery_window = [item for item in batch_delivery_reports if isinstance(item, dict)][-window:]
    eval_window = [item for item in eval_results if isinstance(item, dict)][-window:]
    autonomy_window = [item for item in autonomy_decisions if isinstance(item, dict)][-window:]
    exception_window = [item for item in exception_routing_outputs if isinstance(item, dict)][-window:]
    drift_window = [item for item in drift_signals if isinstance(item, dict)][-window:]
    replay_window = [item for item in replay_metrics if isinstance(item, dict)][-window:]

    missing_required_signals = sorted(
        signal
        for signal, values in {
            "batch_delivery_reports": delivery_window,
            "eval_results": eval_window,
            "autonomy_decisions": autonomy_window,
            "exception_routing_outputs": exception_window,
            "drift_signals": drift_window,
            "replay_metrics": replay_window,
        }.items()
        if not values or not any(isinstance(item, dict) and item for item in values)
    )

    outcomes = [_normalize_outcome(item) for item in eval_window]
    eval_pass_rate = _rate(sum(1 for item in outcomes if item == "pass"), len(outcomes))
    eval_fail_rate = _rate(sum(1 for item in outcomes if item == "fail"), len(outcomes))
    eval_indeterminate_rate = _rate(sum(1 for item in outcomes if item == "indeterminate"), len(outcomes))

    replay_success_rate = _rate(
        sum(
            1
            for item in replay_window
            if str(item.get("status") or item.get("replay_consistency") or "").lower()
            in {"match", "ready", "ready_for_replay", "replayable", "success"}
        ),
        len(replay_window),
    )
    drift_signal_rate = _rate(
        sum(1 for item in drift_window if str(item.get("drift_level") or "").lower() in {"high", "critical", "medium"}),
        len(drift_window),
    )
    override_rate = _rate(
        sum(1 for item in exception_window if str(item.get("action_type") or "").lower() in {"escalate", "stop_without_auto_action"}),
        len(exception_window),
    )
    autonomy_block_rate = _rate(
        sum(1 for item in autonomy_window if str(item.get("decision") or "").lower() in {"stop", "require_human_review", "escalate"}),
        len(autonomy_window),
    )
    failure_recurrence_rate = _rate(
        sum(1 for item in delivery_window if str(item.get("status") or "").lower() in {"blocked", "failed", "completed_with_risk"}),
        len(delivery_window),
    )
    unresolved_risk_count = len([item for item in unresolved_risks if str(item).strip()])

    reason_codes: list[str] = []
    if missing_required_signals:
        reason_codes.extend([f"missing_required_signal:{signal}" for signal in missing_required_signals])

    if replay_success_rate < 0.8:
        reason_codes.append("replay_consistency_low")
    if eval_fail_rate >= 0.3:
        reason_codes.append("eval_fail_rate_high")
    if drift_signal_rate >= 0.4:
        reason_codes.append("drift_frequency_high")
    if failure_recurrence_rate >= 0.5:
        reason_codes.append("failure_recurrence_high")
    if autonomy_block_rate >= 0.4:
        reason_codes.append("autonomy_block_rate_high")
    if unresolved_risk_count > 0:
        reason_codes.append("unresolved_risks_present")

    readiness_state = "supervised"
    if reason_codes:
        readiness_state = "unsafe"
    elif (
        eval_pass_rate >= 0.95
        and eval_fail_rate <= 0.05
        and eval_indeterminate_rate <= 0.05
        and replay_success_rate >= 0.99
        and drift_signal_rate <= 0.05
        and override_rate <= 0.05
        and autonomy_block_rate <= 0.05
        and failure_recurrence_rate <= 0.10
        and unresolved_risk_count == 0
    ):
        readiness_state = "autonomous"
    elif (
        eval_pass_rate < 0.85
        or eval_fail_rate >= 0.15
        or drift_signal_rate >= 0.2
        or replay_success_rate < 0.95
        or override_rate >= 0.2
        or autonomy_block_rate >= 0.2
        or failure_recurrence_rate >= 0.25
    ):
        readiness_state = "constrained"

    if prior_readiness_state in _STATE_RANK and _STATE_RANK[readiness_state] > _STATE_RANK[prior_readiness_state]:
        if len(delivery_window) < 3 or eval_pass_rate < 0.98 or replay_success_rate < 1.0:
            readiness_state = prior_readiness_state
            reason_codes.append("readiness_upgrade_withheld_insufficient_evidence")

    if not reason_codes:
        reason_codes = [f"readiness_state:{readiness_state}"]

    supporting_signals = [
        f"eval_pass_rate={eval_pass_rate:.6f}",
        f"eval_fail_rate={eval_fail_rate:.6f}",
        f"eval_indeterminate_rate={eval_indeterminate_rate:.6f}",
        f"replay_success_rate={replay_success_rate:.6f}",
        f"drift_signal_rate={drift_signal_rate:.6f}",
        f"override_rate={override_rate:.6f}",
        f"autonomy_block_rate={autonomy_block_rate:.6f}",
        f"failure_recurrence_rate={failure_recurrence_rate:.6f}",
        f"unresolved_risk_count={unresolved_risk_count}",
    ]

    seed = {
        "roadmap_id": roadmap_id,
        "trace_id": trace_id,
        "recent_batches_considered": window,
        "reason_codes": sorted(set(reason_codes)),
        "supporting_signals": sorted(set(supporting_signals)),
        "created_at": created_at,
    }
    readiness_id = f"CRD-{_canonical_hash(seed)[:12].upper()}"

    return {
        "readiness_id": readiness_id,
        "schema_version": "1.0.0",
        "roadmap_id": roadmap_id,
        "recent_batches_considered": window,
        "eval_pass_rate": eval_pass_rate,
        "eval_fail_rate": eval_fail_rate,
        "eval_indeterminate_rate": eval_indeterminate_rate,
        "replay_success_rate": replay_success_rate,
        "drift_signal_rate": drift_signal_rate,
        "override_rate": override_rate,
        "unresolved_risk_count": unresolved_risk_count,
        "autonomy_block_rate": autonomy_block_rate,
        "failure_recurrence_rate": failure_recurrence_rate,
        "readiness_state": readiness_state,
        "reason_codes": sorted(set(reason_codes)),
        "supporting_signals": sorted(set(supporting_signals)),
        "created_at": created_at,
        "trace_id": trace_id,
    }


__all__ = ["evaluate_capability_readiness"]
