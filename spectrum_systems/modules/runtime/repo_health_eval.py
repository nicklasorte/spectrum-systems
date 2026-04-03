"""Deterministic repo-review health evaluation and control-loop adapter."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision
from spectrum_systems.modules.runtime.repo_review_snapshot_store import (
    RepoReviewSnapshotStoreError,
    validate_repo_review_snapshot,
)
from spectrum_systems.utils.deterministic_id import deterministic_id


class RepoHealthEvalError(ValueError):
    """Raised when repo health evaluation/control inputs are invalid."""


def _trace_uuid(snapshot: Dict[str, Any]) -> str:
    trace_id = str((snapshot.get("trace_linkage") or {}).get("trace_id") or "").strip()
    if not trace_id:
        raise RepoHealthEvalError("repo_review_snapshot.trace_linkage.trace_id is required")
    try:
        return str(uuid.UUID(trace_id))
    except ValueError as exc:
        raise RepoHealthEvalError("repo_review_snapshot.trace_linkage.trace_id must be a valid UUID") from exc


def _ratio(value: int, total: int) -> float:
    return min(1.0, float(value) / float(max(1, total)))


def compute_repo_health_metrics(snapshot: Dict[str, Any]) -> Dict[str, float]:
    try:
        validate_repo_review_snapshot(snapshot)
    except RepoReviewSnapshotStoreError as exc:
        raise RepoHealthEvalError(str(exc)) from exc

    findings = dict(snapshot["findings_summary"])
    inspected_count = len(snapshot["inspected_files"])

    redundancy_density = _ratio(int(findings["redundancy_findings"]), inspected_count)
    drift_risk = _ratio(int(findings["drift_findings"]), inspected_count)
    eval_coverage_gap_rate = _ratio(int(findings["eval_coverage_gaps"]), inspected_count)
    control_bypass_risk = 1.0 if int(findings["control_bypass_findings"]) > 0 else 0.0

    promotion_readiness = max(
        0.0,
        min(
            1.0,
            1.0
            - (0.40 * drift_risk)
            - (0.30 * eval_coverage_gap_rate)
            - (0.20 * redundancy_density)
            - (0.10 * control_bypass_risk),
        ),
    )

    return {
        "redundancy_density": redundancy_density,
        "drift_risk": drift_risk,
        "promotion_readiness": promotion_readiness,
        "eval_coverage_gap_rate": eval_coverage_gap_rate,
        "control_bypass_risk": control_bypass_risk,
    }


def build_repo_health_eval_result(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    metrics = compute_repo_health_metrics(snapshot)
    trace_id = _trace_uuid(snapshot)

    failure_modes: list[str] = []
    if metrics["redundancy_density"] > 0.15:
        failure_modes.append("repo_redundancy_density_high")
    if metrics["drift_risk"] > 0.20:
        failure_modes.append("repo_drift_risk_high")
    if metrics["eval_coverage_gap_rate"] > 0.20:
        failure_modes.append("repo_eval_coverage_gap_high")
    if metrics["control_bypass_risk"] > 0.0:
        failure_modes.append("repo_control_bypass_risk_high")

    result_status = "pass" if not failure_modes else "fail"
    if metrics["eval_coverage_gap_rate"] > 0.0 and metrics["control_bypass_risk"] == 0.0 and metrics["drift_risk"] <= 0.20:
        result_status = "indeterminate"

    payload_seed = {
        "snapshot_id": snapshot["snapshot_id"],
        "review_id": snapshot["review_id"],
        "metrics": metrics,
        "result_status": result_status,
    }
    eval_result = {
        "artifact_type": "eval_result",
        "schema_version": "1.0.0",
        "eval_case_id": deterministic_id(prefix="ec", namespace="repo_health_eval_case", payload=payload_seed),
        "run_id": deterministic_id(prefix="run", namespace="repo_health_eval_run", payload=payload_seed),
        "trace_id": trace_id,
        "result_status": result_status,
        "score": metrics["promotion_readiness"],
        "failure_modes": sorted(failure_modes),
        "provenance_refs": [
            f"repo_review_snapshot:{snapshot['snapshot_id']}",
            f"review:{snapshot['review_id']}",
            f"commit:{snapshot['commit_hash']}",
            f"branch:{snapshot['branch']}",
        ],
    }
    validate_artifact(eval_result, "eval_result")
    return eval_result


def build_repo_health_eval_summary(snapshot: Dict[str, Any], eval_result: Dict[str, Any]) -> Dict[str, Any]:
    validate_artifact(eval_result, "eval_result")
    metrics = compute_repo_health_metrics(snapshot)

    system_status = "healthy"
    if eval_result["result_status"] == "fail":
        system_status = "failing"
    elif eval_result["result_status"] == "indeterminate":
        system_status = "degraded"

    summary = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": _trace_uuid(snapshot),
        "eval_run_id": deterministic_id(
            prefix="ers",
            namespace="repo_health_eval_summary",
            payload={"snapshot_id": snapshot["snapshot_id"], "run_id": eval_result["run_id"]},
        ),
        "pass_rate": 1.0 if eval_result["result_status"] == "pass" else 0.0,
        "failure_rate": 0.0 if eval_result["result_status"] == "pass" else 1.0,
        "drift_rate": max(metrics["drift_risk"], metrics["eval_coverage_gap_rate"]),
        "reproducibility_score": 1.0 - metrics["control_bypass_risk"],
        "system_status": system_status,
    }
    validate_artifact(summary, "eval_summary")
    return summary


def build_repo_health_eval(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    eval_result = build_repo_health_eval_result(snapshot)
    eval_summary = build_repo_health_eval_summary(snapshot, eval_result)
    return {"eval_result": eval_result, "eval_summary": eval_summary}


def _as_replay_result(snapshot: Dict[str, Any], eval_summary: Dict[str, Any]) -> Dict[str, Any]:
    validate_artifact(eval_summary, "eval_summary")
    metrics = compute_repo_health_metrics(snapshot)

    replay = copy.deepcopy(load_example("replay_result"))
    run_id = str(eval_summary["eval_run_id"])
    trace_id = str(eval_summary["trace_id"])
    replay_id = deterministic_id(
        prefix="RPL",
        namespace="repo_health_replay",
        payload={"snapshot_id": snapshot["snapshot_id"], "eval_run_id": run_id},
        digest_length=12,
    ).upper()

    replay["replay_id"] = replay_id
    replay["original_run_id"] = run_id
    replay["replay_run_id"] = run_id
    replay["timestamp"] = snapshot["timestamp"]
    replay["trace_id"] = trace_id
    replay["input_artifact_reference"] = f"eval_summary:{run_id}"
    replay["provenance"] = {
        "source_artifact_type": "repo_review_snapshot",
        "source_artifact_id": snapshot["snapshot_id"],
        "trace_id": trace_id,
    }

    if metrics["control_bypass_risk"] > 0.0:
        replay["consistency_status"] = "mismatch"
        replay["drift_detected"] = True
    else:
        replay["consistency_status"] = "match"
        replay["drift_detected"] = False
    replay["failure_reason"] = None

    replay["observability_metrics"]["timestamp"] = snapshot["timestamp"]
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["observability_metrics"]["run_ids"] = [run_id]
    replay["observability_metrics"]["source_artifact_ids"] = [replay_id]
    replay["observability_metrics"]["metrics"]["total_runs"] = 1
    replay["observability_metrics"]["metrics"]["replay_success_rate"] = metrics["promotion_readiness"]
    replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = max(
        metrics["drift_risk"],
        metrics["eval_coverage_gap_rate"],
    )

    budget_status = "healthy"
    if metrics["control_bypass_risk"] > 0.0:
        budget_status = "invalid"
    elif metrics["drift_risk"] > 0.20 or metrics["eval_coverage_gap_rate"] > 0.20:
        budget_status = "exhausted"
    elif metrics["redundancy_density"] > 0.15 or metrics["promotion_readiness"] < 0.85:
        budget_status = "warning"

    replay["error_budget_status"]["timestamp"] = snapshot["timestamp"]
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["observability_metrics_id"] = replay["observability_metrics"]["artifact_id"]
    replay["error_budget_status"]["budget_status"] = budget_status
    replay["error_budget_status"]["highest_severity"] = budget_status
    replay["error_budget_status"]["objectives"][0]["observed_value"] = metrics["promotion_readiness"]
    replay["error_budget_status"]["objectives"][0]["consumed_error"] = max(0.0, 1.0 - metrics["promotion_readiness"])
    replay["error_budget_status"]["objectives"][0]["remaining_error"] = max(0.0, 0.01 - replay["error_budget_status"]["objectives"][0]["consumed_error"])
    replay["error_budget_status"]["objectives"][0]["consumption_ratio"] = min(
        1.0, replay["error_budget_status"]["objectives"][0]["consumed_error"] / 0.01
    )
    replay["error_budget_status"]["objectives"][0]["status"] = budget_status
    replay["error_budget_status"]["objectives"][1]["observed_value"] = replay["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"]
    replay["error_budget_status"]["objectives"][1]["consumed_error"] = replay["error_budget_status"]["objectives"][1]["observed_value"]
    replay["error_budget_status"]["objectives"][1]["remaining_error"] = max(0.0, 0.05 - replay["error_budget_status"]["objectives"][1]["consumed_error"])
    replay["error_budget_status"]["objectives"][1]["consumption_ratio"] = min(
        1.0, replay["error_budget_status"]["objectives"][1]["consumed_error"] / 0.05
    )
    replay["error_budget_status"]["objectives"][1]["status"] = budget_status

    if budget_status == "healthy":
        replay["error_budget_status"]["triggered_conditions"] = []
        replay["error_budget_status"]["reasons"] = []
    else:
        replay["error_budget_status"]["triggered_conditions"] = [
            {
                "metric_name": "replay_success_rate",
                "status": budget_status,
                "consumption_ratio": replay["error_budget_status"]["objectives"][0]["consumption_ratio"],
            }
        ]
        replay["error_budget_status"]["reasons"] = [f"repo_health_budget_{budget_status}"]

    validate_artifact(replay, "replay_result")
    return replay


def build_repo_health_control_decision(
    *,
    snapshot: Dict[str, Any] | None,
    eval_summary: Dict[str, Any] | None,
    review_signal_required: bool = False,
) -> Dict[str, Any]:
    if snapshot is None:
        raise RepoHealthEvalError("missing review artifact: repo_review_snapshot is required")
    if eval_summary is None:
        raise RepoHealthEvalError("missing required eval: eval_summary is required")

    replay_result = _as_replay_result(snapshot, eval_summary)
    return build_evaluation_control_decision(
        replay_result,
        review_signal_required=review_signal_required,
    )


__all__ = [
    "RepoHealthEvalError",
    "build_repo_health_control_decision",
    "build_repo_health_eval",
    "build_repo_health_eval_result",
    "build_repo_health_eval_summary",
    "compute_repo_health_metrics",
]
