"""Deterministic retroactive audit for PYX-01 pytest execution integrity.

This module backtests historical preflight artifacts to identify runs that may
have been treated as trusted without authoritative pytest execution truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact


class RetroactivePytestIntegrityAuditError(ValueError):
    """Raised when retroactive audit execution invariants are violated."""


KNOWN_PR_EVENTS = {
    "pull_request",
    "pull_request_target",
    "pull_request_review",
    "pull_request_review_comment",
}

TRUSTING_DECISIONS = {"ALLOW", "WARN"}
TRUSTING_STATUSES = {"passed", "warn", "warning"}

REASON_HISTORICAL_ALLOW_WITHOUT_PYTEST = "HISTORICAL_PR_ALLOW_WITHOUT_PYTEST_EXECUTION"
REASON_HISTORICAL_WARN_WITHOUT_PYTEST = "HISTORICAL_WARN_WITHOUT_PYTEST_EXECUTION"
REASON_FIELDS_MISSING = "HISTORICAL_EXECUTION_FIELDS_MISSING"
REASON_NON_AUTHORITATIVE = "HISTORICAL_NON_AUTHORITATIVE_TEST_EVIDENCE"
REASON_PRE_PYX_SHAPE = "HISTORICAL_ARTIFACT_SHAPE_PRE_PYX01"
REASON_CONTEXT_NOT_EVALUABLE = "HISTORICAL_CONTEXT_NOT_EVALUABLE"
REASON_INCOMPLETE_ACCOUNTING = "HISTORICAL_INCOMPLETE_EXECUTION_ACCOUNTING"

REQUIRED_EXECUTION_FIELDS = {
    "event_name",
    "pytest_execution_count",
    "pytest_commands",
    "selected_targets",
    "fallback_targets",
    "fallback_used",
    "targeted_selection_empty",
    "fallback_selection_empty",
    "selection_reason_codes",
}


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RetroactivePytestIntegrityAuditError(f"missing_artifact:{path}") from exc
    except json.JSONDecodeError as exc:
        raise RetroactivePytestIntegrityAuditError(f"invalid_json:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise RetroactivePytestIntegrityAuditError(f"artifact_not_object:{path}")
    return payload


def _derive_event_name(payload: dict[str, Any]) -> str | None:
    pytest_execution = payload.get("pytest_execution")
    if isinstance(pytest_execution, dict):
        event_name = pytest_execution.get("event_name")
        if isinstance(event_name, str) and event_name.strip():
            return event_name.strip()
    changed_path_detection = payload.get("changed_path_detection")
    if isinstance(changed_path_detection, dict):
        ref_context = changed_path_detection.get("ref_context")
        if isinstance(ref_context, dict):
            event_name = ref_context.get("event_name")
            if isinstance(event_name, str) and event_name.strip():
                return event_name.strip()
    return None


def _is_trusting_outcome(payload: dict[str, Any]) -> bool:
    status = str(payload.get("preflight_status") or payload.get("status") or "").strip().lower()
    if status in TRUSTING_STATUSES:
        return True
    control_signal = payload.get("control_signal")
    if isinstance(control_signal, dict):
        decision = str(control_signal.get("strategy_gate_decision") or "").strip().upper()
        if decision in TRUSTING_DECISIONS:
            return True
    return False


def _missing_execution_fields(pytest_execution: dict[str, Any]) -> list[str]:
    return sorted(field for field in REQUIRED_EXECUTION_FIELDS if field not in pytest_execution)


def _has_non_authoritative_evidence(payload: dict[str, Any]) -> bool:
    lower_keys = {str(key).lower() for key in payload.keys()}
    if any("workflow_pytest" in key or "downstream_pytest" in key for key in lower_keys):
        return True
    evidence_refs = payload.get("evidence_refs")
    if isinstance(evidence_refs, list):
        for item in evidence_refs:
            text = str(item).lower()
            if "workflow" in text and "pytest" in text:
                return True
    return False


def classify_historical_preflight_artifact(payload: dict[str, Any], *, artifact_path: str) -> dict[str, Any]:
    """Classify one historical artifact into trusted/suspect/unable state."""
    reasons: list[str] = []

    artifact_type = str(payload.get("artifact_type") or "")
    if artifact_type not in {"contract_preflight_result_artifact", ""}:
        return {
            "artifact_path": artifact_path,
            "classification": "unable_to_evaluate",
            "reason_codes": [REASON_CONTEXT_NOT_EVALUABLE],
            "trusting_outcome": False,
            "context": "unknown",
            "remediation_recommendation": "manual_operator_review_required",
        }

    trusting_outcome = _is_trusting_outcome(payload)
    event_name = _derive_event_name(payload)
    is_pr = event_name in KNOWN_PR_EVENTS
    context = "pr" if is_pr else ("non_pr" if event_name else "unknown")

    pytest_execution = payload.get("pytest_execution")
    if pytest_execution is None:
        reasons.append(REASON_PRE_PYX_SHAPE)
        if trusting_outcome and is_pr:
            decision = str(((payload.get("control_signal") or {}).get("strategy_gate_decision") or "")).upper()
            reasons.append(REASON_HISTORICAL_WARN_WITHOUT_PYTEST if decision == "WARN" else REASON_HISTORICAL_ALLOW_WITHOUT_PYTEST)
    elif not isinstance(pytest_execution, dict):
        reasons.append(REASON_FIELDS_MISSING)
    else:
        missing = _missing_execution_fields(pytest_execution)
        if missing:
            reasons.append(REASON_FIELDS_MISSING)
        if trusting_outcome and is_pr:
            count = pytest_execution.get("pytest_execution_count")
            if not isinstance(count, int) or count < 1:
                reasons.append(REASON_INCOMPLETE_ACCOUNTING)
                decision = str(((payload.get("control_signal") or {}).get("strategy_gate_decision") or "")).upper()
                reasons.append(REASON_HISTORICAL_WARN_WITHOUT_PYTEST if decision == "WARN" else REASON_HISTORICAL_ALLOW_WITHOUT_PYTEST)

    if trusting_outcome and _has_non_authoritative_evidence(payload):
        reasons.append(REASON_NON_AUTHORITATIVE)

    if context == "unknown":
        reasons.append(REASON_CONTEXT_NOT_EVALUABLE)

    deduped_reasons = sorted(set(reasons))
    if any(
        code in deduped_reasons
        for code in {
            REASON_HISTORICAL_ALLOW_WITHOUT_PYTEST,
            REASON_HISTORICAL_WARN_WITHOUT_PYTEST,
            REASON_FIELDS_MISSING,
            REASON_NON_AUTHORITATIVE,
            REASON_INCOMPLETE_ACCOUNTING,
            REASON_PRE_PYX_SHAPE,
        }
    ):
        classification = (
            "unable_to_evaluate"
            if REASON_CONTEXT_NOT_EVALUABLE in deduped_reasons and context == "unknown"
            else (
                "suspect_non_authoritative_pytest"
                if REASON_NON_AUTHORITATIVE in deduped_reasons
                else (
                    "suspect_incomplete_execution_accounting"
                    if REASON_INCOMPLETE_ACCOUNTING in deduped_reasons
                    else "suspect_missing_pytest_execution"
                )
            )
        )
    elif REASON_CONTEXT_NOT_EVALUABLE in deduped_reasons:
        classification = "unable_to_evaluate"
    else:
        classification = "trusted"

    remediation = "none"
    if classification.startswith("suspect"):
        remediation = "manual_operator_review_required"
        if context == "pr":
            remediation = "re_run_governed_preflight_if_commit_pair_reconstructable"

    return {
        "artifact_path": artifact_path,
        "classification": classification,
        "reason_codes": deduped_reasons,
        "trusting_outcome": trusting_outcome,
        "context": context,
        "remediation_recommendation": remediation,
    }


def scan_historical_preflight_artifacts(scan_roots: list[Path]) -> list[dict[str, Any]]:
    """Load historical preflight artifacts under governed repo-known locations."""
    paths: set[Path] = set()
    patterns = ("**/contract_preflight_result_artifact.json", "**/contract_preflight_report.json")
    for root in scan_roots:
        if not root.exists():
            continue
        for pattern in patterns:
            for path in root.glob(pattern):
                if path.is_file():
                    paths.add(path)

    artifacts: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: str(item).lower()):
        payload = _read_json_object(path)
        payload["__artifact_path"] = str(path.as_posix())
        artifacts.append(payload)
    return artifacts


def run_retroactive_pytest_integrity_audit(
    *,
    scanned_artifacts: list[dict[str, Any]],
    audit_scope: dict[str, Any],
    remediation_queue_limit: int = 50,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Produce schema-bound audit result and bounded remediation queue artifacts."""
    if remediation_queue_limit < 1:
        raise RetroactivePytestIntegrityAuditError("remediation_queue_limit must be >= 1")

    classified_runs = [
        classify_historical_preflight_artifact(artifact, artifact_path=str(artifact.get("__artifact_path") or "unknown"))
        for artifact in scanned_artifacts
    ]
    classified_runs = sorted(classified_runs, key=lambda item: item["artifact_path"])

    suspect_runs = [item for item in classified_runs if item["classification"].startswith("suspect")]
    unable_runs = [item for item in classified_runs if item["classification"] == "unable_to_evaluate"]
    trusted_runs = [item for item in classified_runs if item["classification"] == "trusted"]

    remediation_queue = [
        {
            "artifact_path": item["artifact_path"],
            "classification": item["classification"],
            "reason_codes": item["reason_codes"],
            "recommended_action": item["remediation_recommendation"],
            "quarantine_recommendation": "quarantine_from_trusted_baseline_metrics_until_revalidated",
        }
        for item in suspect_runs[:remediation_queue_limit]
    ]

    generated_at = "1970-01-01T00:00:00Z"
    source_timestamps = sorted(
        {
            str(artifact.get("generated_at"))
            for artifact in scanned_artifacts
            if isinstance(artifact.get("generated_at"), str) and artifact.get("generated_at")
        }
    )
    if source_timestamps:
        generated_at = source_timestamps[-1]

    summary_reason_codes = sorted({code for item in classified_runs for code in item.get("reason_codes", [])})

    result = {
        "artifact_type": "retroactive_pytest_integrity_audit_result",
        "schema_version": "1.0.0",
        "audit_scope": audit_scope,
        "scanned_run_count": len(classified_runs),
        "trusted_count": len(trusted_runs),
        "suspect_count": len(suspect_runs),
        "unable_to_evaluate_count": len(unable_runs),
        "suspect_runs": suspect_runs,
        "remediation_queue": remediation_queue,
        "summary_reason_codes": summary_reason_codes,
        "generated_at": generated_at,
        "trace": {
            "producer": "spectrum_systems.modules.runtime.retroactive_pytest_integrity_audit",
            "classification_policy": "pyx01_execution_truth_backtest_v1",
            "remediation_queue_limit": remediation_queue_limit,
            "scan_mode": "repo_local_artifacts_only",
        },
    }

    queue = {
        "artifact_type": "retroactive_pytest_remediation_queue",
        "schema_version": "1.0.0",
        "audit_result_ref": "outputs/retroactive_pytest_integrity_audit/retroactive_pytest_integrity_audit_result.json",
        "queue_size": len(remediation_queue),
        "items": remediation_queue,
        "generated_at": generated_at,
        "trace": {
            "producer": "spectrum_systems.modules.runtime.retroactive_pytest_integrity_audit",
            "queue_policy": "bounded_suspect_only",
            "queue_limit": remediation_queue_limit,
        },
    }

    validate_artifact(result, "retroactive_pytest_integrity_audit_result")
    validate_artifact(queue, "retroactive_pytest_remediation_queue")
    return result, queue


__all__ = [
    "RetroactivePytestIntegrityAuditError",
    "classify_historical_preflight_artifact",
    "run_retroactive_pytest_integrity_audit",
    "scan_historical_preflight_artifacts",
]
