"""Deterministic judgment-learning artifact runners (label ingestion, calibration, drift)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from spectrum_systems.contracts import validate_artifact


class JudgmentLearningError(ValueError):
    """Raised when judgment-learning inputs are incomplete or invalid."""


_DEFAULT_LEARNING_THRESHOLDS = {
    "error_budget_warning_consumption_ratio": 0.8,
    "drift_warning_approval_rate_delta": 0.1,
    "drift_warning_block_rate_delta": 0.1,
    "drift_warning_error_rate_delta": 0.05,
    "drift_warning_calibration_ece_delta": 0.05,
    "drift_critical_approval_rate_delta": 0.2,
    "drift_critical_block_rate_delta": 0.2,
    "drift_critical_error_rate_delta": 0.1,
    "drift_critical_calibration_ece_delta": 0.1,
}


def _resolve_learning_thresholds(policy: dict[str, Any]) -> dict[str, float]:
    config = ((policy.get("learning_control_policy") or {}).get("thresholds") or {})
    resolved = dict(_DEFAULT_LEARNING_THRESHOLDS)
    for key, value in config.items():
        if key in resolved and isinstance(value, (int, float)):
            resolved[key] = float(value)
    return resolved


def build_judgment_outcome_label(
    *,
    artifact_id: str,
    judgment_id: str,
    observed_outcome: str,
    expected_outcome: str,
    correctness: bool,
    source: str,
    timestamp: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "artifact_type": "judgment_outcome_label",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.94",
        "judgment_id": judgment_id,
        "observed_outcome": observed_outcome,
        "expected_outcome": expected_outcome,
        "correctness": correctness,
        "source": source,
        "timestamp": timestamp,
        "notes": [n for n in (notes or []) if isinstance(n, str) and n],
    }
    try:
        validate_artifact(payload, "judgment_outcome_label")
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        raise JudgmentLearningError(f"invalid judgment_outcome_label artifact: {exc}") from exc
    return payload


def _deterministic_confidence(judgment_record: dict[str, Any], label: dict[str, Any]) -> float:
    explicit = judgment_record.get("confidence_score")
    if isinstance(explicit, (int, float)):
        return round(min(1.0, max(0.0, float(explicit))), 6)

    mapping = {
        "approve": 0.9,
        "block": 0.9,
        "revise": 0.6,
        "escalate": 0.7,
        "needs_more_evidence": 0.4,
    }
    observed = label.get("observed_outcome")
    if isinstance(observed, str) and observed in mapping:
        return mapping[observed]
    return 0.5


def _ece(labels_with_confidence: list[tuple[bool, float]]) -> tuple[float, list[dict[str, Any]]]:
    bins: dict[str, list[tuple[bool, float]]] = defaultdict(list)
    for correct, confidence in labels_with_confidence:
        index = min(int(confidence * 10), 9)
        bin_key = f"{index / 10:.1f}-{(index + 1) / 10:.1f}"
        bins[bin_key].append((correct, confidence))

    total = len(labels_with_confidence)
    ece = 0.0
    breakdown: list[dict[str, Any]] = []
    for key in sorted(bins):
        items = bins[key]
        count = len(items)
        mean_confidence = round(sum(conf for _, conf in items) / count, 6)
        mean_accuracy = round(sum(1.0 if c else 0.0 for c, _ in items) / count, 6)
        gap = round(abs(mean_confidence - mean_accuracy), 6)
        weight = count / total
        ece += weight * gap
        breakdown.append(
            {
                "bin": key,
                "count": count,
                "mean_confidence": mean_confidence,
                "mean_accuracy": mean_accuracy,
                "absolute_gap": gap,
            }
        )
    return round(ece, 6), breakdown


def run_judgment_calibration(
    *,
    artifact_id: str,
    labels: Iterable[dict[str, Any]],
    judgment_records_by_id: dict[str, dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    label_list = [dict(item) for item in labels if isinstance(item, dict)]
    if not label_list:
        raise JudgmentLearningError("calibration requires at least one judgment_outcome_label")

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for label in sorted(label_list, key=lambda item: (item.get("judgment_id", ""), item.get("timestamp", ""), item.get("artifact_id", ""))):
        try:
            validate_artifact(label, "judgment_outcome_label")
        except Exception as exc:
            raise JudgmentLearningError(f"invalid label in calibration input: {exc}") from exc

        judgment_id = label["judgment_id"]
        record = judgment_records_by_id.get(judgment_id)
        if not isinstance(record, dict):
            raise JudgmentLearningError(f"missing judgment record for label judgment_id={judgment_id}")

        judgment_type = str(record.get("judgment_type") or "")
        policy_version = str(record.get("artifact_version") or "")
        environment = str(record.get("environment") or record.get("context_fingerprint", {}).get("environment") or "unknown")
        if not judgment_type or not policy_version:
            raise JudgmentLearningError(f"judgment record missing grouping fields for judgment_id={judgment_id}")

        enriched = {
            "correctness": bool(label["correctness"]),
            "confidence": _deterministic_confidence(record, label),
            "observed_outcome": label["observed_outcome"],
        }
        grouped[(judgment_type, policy_version, environment)].append(enriched)

    group_metrics: list[dict[str, Any]] = []
    for (judgment_type, policy_version, environment), entries in sorted(grouped.items()):
        total = len(entries)
        correct = sum(1 for item in entries if item["correctness"])
        accuracy = round(correct / total, 6)
        pairs = [(item["correctness"], item["confidence"]) for item in entries]
        ece_value, ece_bins = _ece(pairs)
        mean_confidence = round(sum(item["confidence"] for item in entries) / total, 6)
        delta = round(mean_confidence - accuracy, 6)
        signal = "well_calibrated"
        if delta > 0.05:
            signal = "overconfident"
        elif delta < -0.05:
            signal = "underconfident"

        group_metrics.append(
            {
                "judgment_type": judgment_type,
                "policy_version": policy_version,
                "environment": environment,
                "sample_size": total,
                "accuracy": accuracy,
                "mean_confidence": mean_confidence,
                "expected_calibration_error": ece_value,
                "calibration_delta": delta,
                "confidence_signal": signal,
                "ece_bins": ece_bins,
                "outcome_distribution": {
                    outcome: count
                    for outcome, count in sorted(
                        ((outcome, sum(1 for item in entries if item["observed_outcome"] == outcome)) for outcome in {item["observed_outcome"] for item in entries}),
                        key=lambda item: item[0],
                    )
                },
                "error_rate": round(1.0 - accuracy, 6),
            }
        )

    payload = {
        "artifact_type": "judgment_calibration_result",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.94",
        "grouping_keys": ["judgment_type", "policy_version", "environment"],
        "group_metrics": group_metrics,
        "formulas": {
            "accuracy": "correct_count / sample_size",
            "expected_calibration_error": "sum_over_bins((bin_count / total_count) * abs(bin_accuracy - bin_mean_confidence))",
            "calibration_delta": "mean_confidence - accuracy",
        },
        "created_at": created_at,
    }
    try:
        validate_artifact(payload, "judgment_calibration_result")
    except Exception as exc:  # pragma: no cover
        raise JudgmentLearningError(f"invalid judgment_calibration_result artifact: {exc}") from exc
    return payload


def run_judgment_drift_signal(
    *,
    artifact_id: str,
    baseline: dict[str, Any],
    current: dict[str, Any],
    created_at: str,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    for name, payload in (("baseline", baseline), ("current", current)):
        try:
            validate_artifact(payload, "judgment_calibration_result")
        except Exception as exc:
            raise JudgmentLearningError(f"{name} calibration artifact invalid: {exc}") from exc

    baseline_map = {
        (item["judgment_type"], item["policy_version"], item["environment"]): item
        for item in baseline["group_metrics"]
    }
    current_map = {
        (item["judgment_type"], item["policy_version"], item["environment"]): item
        for item in current["group_metrics"]
    }

    missing = sorted(set(current_map) - set(baseline_map))
    if missing:
        raise JudgmentLearningError(f"baseline missing groups required for drift comparison: {missing}")

    limits = {
        "approval_rate_delta": 0.1,
        "block_rate_delta": 0.1,
        "error_rate_delta": 0.05,
        "calibration_ece_delta": 0.05,
    }
    for key, value in (thresholds or {}).items():
        if key in limits and isinstance(value, (int, float)):
            limits[key] = float(value)

    group_signals: list[dict[str, Any]] = []
    for key in sorted(current_map):
        b = baseline_map[key]
        c = current_map[key]

        b_dist = b.get("outcome_distribution", {})
        c_dist = c.get("outcome_distribution", {})
        b_total = float(max(1, b.get("sample_size", 0)))
        c_total = float(max(1, c.get("sample_size", 0)))
        approval_delta = round((c_dist.get("approve", 0) / c_total) - (b_dist.get("approve", 0) / b_total), 6)
        block_delta = round((c_dist.get("block", 0) / c_total) - (b_dist.get("block", 0) / b_total), 6)
        error_delta = round(float(c.get("error_rate", 0.0)) - float(b.get("error_rate", 0.0)), 6)
        ece_delta = round(float(c.get("expected_calibration_error", 0.0)) - float(b.get("expected_calibration_error", 0.0)), 6)

        triggered = {
            "approval_rate_shift": abs(approval_delta) >= limits["approval_rate_delta"],
            "block_rate_shift": abs(block_delta) >= limits["block_rate_delta"],
            "error_rate_increase": error_delta >= limits["error_rate_delta"],
            "calibration_degradation": ece_delta >= limits["calibration_ece_delta"],
        }
        drift_detected = any(triggered.values())

        group_signals.append(
            {
                "judgment_type": key[0],
                "policy_version": key[1],
                "environment": key[2],
                "baseline_ref": baseline["artifact_id"],
                "current_ref": current["artifact_id"],
                "deltas": {
                    "approval_rate_delta": approval_delta,
                    "block_rate_delta": block_delta,
                    "error_rate_delta": error_delta,
                    "calibration_ece_delta": ece_delta,
                },
                "thresholds": limits,
                "triggered_signals": triggered,
                "drift_detected": drift_detected,
            }
        )

    payload = {
        "artifact_type": "judgment_drift_signal",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.94",
        "group_signals": group_signals,
        "created_at": created_at,
    }
    try:
        validate_artifact(payload, "judgment_drift_signal")
    except Exception as exc:  # pragma: no cover
        raise JudgmentLearningError(f"invalid judgment_drift_signal artifact: {exc}") from exc
    return payload


def run_judgment_error_budget_status(
    *,
    artifact_id: str,
    labels: Iterable[dict[str, Any]],
    judgment_records_by_id: dict[str, dict[str, Any]],
    judgment_eval_results: Iterable[dict[str, Any]],
    policy: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    label_list = [dict(item) for item in labels if isinstance(item, dict)]
    eval_list = [dict(item) for item in judgment_eval_results if isinstance(item, dict)]
    if not label_list:
        raise JudgmentLearningError("error budget requires at least one judgment_outcome_label")
    if not eval_list:
        raise JudgmentLearningError("error budget requires at least one judgment_eval_result")

    limits = ((policy.get("learning_control_policy") or {}).get("error_budget_limits") or {})
    warning_ratio = _resolve_learning_thresholds(policy)["error_budget_warning_consumption_ratio"]

    grouped_labels: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for label in sorted(label_list, key=lambda item: (item.get("judgment_id", ""), item.get("timestamp", ""), item.get("artifact_id", ""))):
        try:
            validate_artifact(label, "judgment_outcome_label")
        except Exception as exc:
            raise JudgmentLearningError(f"invalid label in error budget input: {exc}") from exc
        record = judgment_records_by_id.get(label["judgment_id"])
        if not isinstance(record, dict):
            raise JudgmentLearningError(f"missing judgment record for label judgment_id={label['judgment_id']}")
        judgment_type = str(record.get("judgment_type") or "")
        policy_version = str(record.get("artifact_version") or "")
        environment = str(record.get("environment") or record.get("context_fingerprint", {}).get("environment") or "unknown")
        if not judgment_type or not policy_version:
            raise JudgmentLearningError(f"judgment record missing grouping fields for judgment_id={label['judgment_id']}")
        grouped_labels[(judgment_type, policy_version, environment)].append(label)

    eval_group_counts: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"total": 0, "overrides": 0})
    for eval_artifact in sorted(eval_list, key=lambda item: (item.get("artifact_id", ""), item.get("created_at", ""))):
        try:
            validate_artifact(eval_artifact, "judgment_eval_result")
        except Exception as exc:
            raise JudgmentLearningError(f"invalid judgment_eval_result in error budget input: {exc}") from exc
        summary = eval_artifact.get("summary", {})
        judgment_type = str(summary.get("judgment_type") or eval_artifact.get("judgment_type") or "")
        policy_version = str(
            summary.get("policy_version")
            or eval_artifact.get("artifact_version")
            or ""
        )
        environment = str(summary.get("environment") or eval_artifact.get("environment") or "unknown")
        key = (judgment_type, policy_version, environment)
        if key not in grouped_labels:
            candidates = [
                candidate
                for candidate in grouped_labels
                if candidate[0] == judgment_type and candidate[2] == environment
            ]
            if not candidates:
                candidates = [candidate for candidate in grouped_labels if candidate[0] == judgment_type]
            if len(candidates) == 1:
                key = candidates[0]
        eval_group_counts[key]["total"] += 1
        if str(summary.get("application_outcome") or "") != str(summary.get("judgment_outcome") or ""):
            eval_group_counts[key]["overrides"] += 1

    group_statuses: list[dict[str, Any]] = []
    overall_status = "healthy"
    for key in sorted(grouped_labels):
        rows = grouped_labels[key]
        total = len(rows)
        wrong_allow = sum(1 for row in rows if row["correctness"] is False and row.get("observed_outcome") == "approve")
        wrong_block = sum(1 for row in rows if row["correctness"] is False and row.get("observed_outcome") == "block")
        eval_meta = eval_group_counts.get(key, {"total": 0, "overrides": 0})
        if eval_meta["total"] <= 0:
            raise JudgmentLearningError(
                f"error budget missing judgment_eval_result coverage for group={key}"
            )
        wrong_allow_rate = round(wrong_allow / total, 6)
        wrong_block_rate = round(wrong_block / total, 6)
        override_rate = round(eval_meta["overrides"] / eval_meta["total"], 6)

        budget_caps = {
            "wrong_allow_rate": float(limits.get("max_wrong_allow_rate", 0.1)),
            "wrong_block_rate": float(limits.get("max_wrong_block_rate", 0.1)),
            "override_rate": float(limits.get("max_override_rate", 0.2)),
        }
        observed = {
            "wrong_allow_rate": wrong_allow_rate,
            "wrong_block_rate": wrong_block_rate,
            "override_rate": override_rate,
        }
        remaining = {
            metric: round(max(0.0, cap - observed[metric]), 6) for metric, cap in budget_caps.items()
        }
        burn_rate = {
            metric: round((observed[metric] / cap) if cap > 0 else (1.0 if observed[metric] > 0 else 0.0), 6)
            for metric, cap in budget_caps.items()
        }
        group_status = "healthy"
        if any(value >= 1.0 for value in burn_rate.values()):
            group_status = "exhausted"
        elif any(value >= warning_ratio for value in burn_rate.values()):
            group_status = "warning"
        if group_status == "exhausted":
            overall_status = "exhausted"
        elif group_status == "warning" and overall_status == "healthy":
            overall_status = "warning"

        group_statuses.append(
            {
                "judgment_type": key[0],
                "policy_version": key[1],
                "environment": key[2],
                "window_size": total,
                "counts": {
                    "wrong_allow_count": wrong_allow,
                    "wrong_block_count": wrong_block,
                    "override_count": eval_meta["overrides"],
                    "label_count": total,
                    "eval_count": eval_meta["total"],
                },
                "rates": observed,
                "budget_caps": budget_caps,
                "budget_remaining": remaining,
                "burn_rate": burn_rate,
                "budget_status": group_status,
            }
        )

    payload = {
        "artifact_type": "judgment_error_budget_status",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.95",
        "grouping_keys": ["judgment_type", "policy_version", "environment"],
        "status": overall_status,
        "policy_ref": str(policy.get("artifact_id") or ""),
        "warning_consumption_ratio": warning_ratio,
        "group_statuses": group_statuses,
        "created_at": created_at,
    }
    try:
        validate_artifact(payload, "judgment_error_budget_status")
    except Exception as exc:  # pragma: no cover
        raise JudgmentLearningError(f"invalid judgment_error_budget_status artifact: {exc}") from exc
    return payload


def evaluate_judgment_drift_threshold_policy(
    *,
    artifact_id: str,
    drift_signal: dict[str, Any],
    policy: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    try:
        validate_artifact(drift_signal, "judgment_drift_signal")
    except Exception as exc:
        raise JudgmentLearningError(f"invalid judgment_drift_signal input: {exc}") from exc

    limits = _resolve_learning_thresholds(policy)
    group_results: list[dict[str, Any]] = []
    overall_status = "no_drift"
    for item in drift_signal.get("group_signals", []):
        deltas = item["deltas"]
        warning_hit = (
            abs(float(deltas["approval_rate_delta"])) >= limits["drift_warning_approval_rate_delta"]
            or abs(float(deltas["block_rate_delta"])) >= limits["drift_warning_block_rate_delta"]
            or float(deltas["error_rate_delta"]) >= limits["drift_warning_error_rate_delta"]
            or float(deltas["calibration_ece_delta"]) >= limits["drift_warning_calibration_ece_delta"]
        )
        critical_hit = (
            abs(float(deltas["approval_rate_delta"])) >= limits["drift_critical_approval_rate_delta"]
            or abs(float(deltas["block_rate_delta"])) >= limits["drift_critical_block_rate_delta"]
            or float(deltas["error_rate_delta"]) >= limits["drift_critical_error_rate_delta"]
            or float(deltas["calibration_ece_delta"]) >= limits["drift_critical_calibration_ece_delta"]
        )
        status = "no_drift"
        if critical_hit:
            status = "critical_drift"
        elif warning_hit:
            status = "warning_drift"
        if status == "critical_drift":
            overall_status = "critical_drift"
        elif status == "warning_drift" and overall_status == "no_drift":
            overall_status = "warning_drift"
        group_results.append(
            {
                "judgment_type": item["judgment_type"],
                "policy_version": item["policy_version"],
                "environment": item["environment"],
                "status": status,
                "deltas": deltas,
            }
        )

    return {
        "artifact_type": "judgment_drift_threshold_evaluation",
        "artifact_id": artifact_id,
        "policy_ref": str(policy.get("artifact_id") or ""),
        "status": overall_status,
        "thresholds": {
            key: value for key, value in limits.items() if key.startswith("drift_")
        },
        "group_results": group_results,
        "created_at": created_at,
    }
