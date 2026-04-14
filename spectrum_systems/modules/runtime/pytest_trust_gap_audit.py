"""Deterministic read-only backtest for pytest trust gaps in local preflight artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact

TRUSTING_DECISIONS = {"ALLOW", "WARN"}
KNOWN_PR_EVENTS = {"pull_request", "pull_request_target", "pull_request_review", "pull_request_review_comment"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"artifact_not_object:{path}")
    return payload


def scan_preflight_artifacts(scan_roots: list[Path], *, max_artifacts: int = 100) -> list[dict[str, Any]]:
    paths: list[Path] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.glob("**/contract_preflight_result_artifact.json"):
            if path.is_file():
                paths.append(path)
    deduped = sorted({path.resolve() for path in paths}, key=lambda p: str(p))[:max_artifacts]
    artifacts: list[dict[str, Any]] = []
    for path in deduped:
        payload = _read_json(path)
        payload["__artifact_path"] = str(path.as_posix())
        artifacts.append(payload)
    return artifacts


def _event_name(payload: dict[str, Any]) -> str:
    execution = payload.get("pytest_execution")
    if isinstance(execution, dict) and isinstance(execution.get("event_name"), str):
        return str(execution.get("event_name"))
    return ""


def _is_trusting(payload: dict[str, Any]) -> bool:
    signal = payload.get("control_signal")
    if isinstance(signal, dict):
        decision = str(signal.get("strategy_gate_decision") or "").upper()
        if decision in TRUSTING_DECISIONS:
            return True
    return str(payload.get("preflight_status") or "").lower() == "passed"


def _run_identifier(payload: dict[str, Any], artifact_path: str) -> str:
    for key in ("run_id", "trace_id", "artifact_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return artifact_path


def classify_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    artifact_path = str(payload.get("__artifact_path") or "unknown")
    run_identifier = _run_identifier(payload, artifact_path)
    reasons: list[str] = []
    evidence_refs = [artifact_path]
    recommended_follow_up: list[str] = []

    trusting = _is_trusting(payload)
    event_name = _event_name(payload)
    context = "pr" if event_name in KNOWN_PR_EVENTS else ("non_pr" if event_name else "unknown")

    execution = payload.get("pytest_execution")
    record_ref = str(payload.get("pytest_execution_record_ref") or "").strip()
    if record_ref:
        evidence_refs.append(record_ref)
    if not isinstance(execution, dict):
        reasons.append("MISSING_PYTEST_EXECUTION_ARTIFACT")
    else:
        if int(execution.get("pytest_execution_count") or 0) < 1:
            reasons.append("PYTEST_EXECUTION_COUNT_TOO_SMALL")
        selected = execution.get("selected_targets") or []
        if not isinstance(selected, list) or not selected:
            reasons.append("PYTEST_SELECTED_TARGETS_EMPTY")

    selection = payload.get("pytest_selection_integrity")
    selection_ref = str(payload.get("pytest_selection_integrity_result_ref") or "").strip()
    if selection_ref:
        evidence_refs.append(selection_ref)
    if not isinstance(selection, dict):
        reasons.append("MISSING_PYTEST_SELECTION_INTEGRITY_ARTIFACT")
    else:
        decision = str(selection.get("selection_integrity_decision") or "BLOCK")
        if decision != "ALLOW":
            reasons.append("PYTEST_SELECTION_INTEGRITY_NOT_ALLOW")

    if context == "pr":
        if not record_ref:
            reasons.append("MISSING_PYTEST_EXECUTION_RECORD_REF")
        elif record_ref != "outputs/contract_preflight/pytest_execution_record.json":
            reasons.append("NONCANONICAL_PYTEST_EXECUTION_RECORD_REF")
        if not selection_ref:
            reasons.append("MISSING_PYTEST_SELECTION_INTEGRITY_RESULT_REF")
        elif selection_ref != "outputs/contract_preflight/pytest_selection_integrity_result.json":
            reasons.append("NONCANONICAL_PYTEST_SELECTION_INTEGRITY_RESULT_REF")

    classification = "trustworthy"
    confidence = "high"

    if context == "unknown" and not reasons:
        classification = "insufficient_evidence_to_determine"
        confidence = "low"
        recommended_follow_up.append("Retrieve event_name and canonical preflight refs to classify run trustworthiness.")
    if reasons:
        if any(reason in reasons for reason in ["MISSING_PYTEST_EXECUTION_ARTIFACT", "MISSING_PYTEST_EXECUTION_RECORD_REF", "PYTEST_EXECUTION_COUNT_TOO_SMALL", "PYTEST_SELECTED_TARGETS_EMPTY"]):
            classification = "suspect_missing_pytest_execution_evidence"
            recommended_follow_up.append("Retrieve canonical pytest_execution_record and verify preflight-owned pytest execution count/targets.")
        if any(reason in reasons for reason in ["MISSING_PYTEST_SELECTION_INTEGRITY_ARTIFACT", "MISSING_PYTEST_SELECTION_INTEGRITY_RESULT_REF", "PYTEST_SELECTION_INTEGRITY_NOT_ALLOW"]):
            classification = "suspect_missing_selection_integrity_evidence"
            recommended_follow_up.append("Retrieve canonical pytest_selection_integrity_result and verify selection_integrity_decision=ALLOW.")
        if any(reason in reasons for reason in ["NONCANONICAL_PYTEST_EXECUTION_RECORD_REF", "NONCANONICAL_PYTEST_SELECTION_INTEGRITY_RESULT_REF"]):
            classification = "suspect_noncanonical_ref_acceptance"
            recommended_follow_up.append("Validate that only canonical outputs/contract_preflight refs are accepted in PR trust decisions.")

        if trusting and str((payload.get("control_signal") or {}).get("strategy_gate_decision") or "").upper() == "WARN" and context == "pr":
            reasons.append("WARN_TRUST_EQUIVALENCE")
            classification = "suspect_warn_pass_equivalence"
            recommended_follow_up.append("Review preflight decision handling to ensure WARN is not pass-equivalent for pull_request events.")

        if context == "unknown":
            classification = "insufficient_evidence_to_determine"
            confidence = "low"
            recommended_follow_up.append("Retrieve event_name and canonical preflight refs to classify run trustworthiness.")
        elif classification == "trustworthy":
            classification = "suspect_degraded_ref_resolution"
            recommended_follow_up.append("Inspect ref normalization and changed-path resolution artifacts for degraded provenance.")

    if classification == "trustworthy":
        recommended_follow_up.append("No immediate action required.")

    return {
        "run_identifier": run_identifier,
        "evidence_refs_used": sorted(set(evidence_refs)),
        "classification": classification,
        "reasons": sorted(set(reasons)),
        "confidence_level": confidence,
        "recommended_follow_up": sorted(set(recommended_follow_up)),
    }


def run_pytest_trust_gap_audit(*, scanned_artifacts: list[dict[str, Any]], audit_scope: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    classified = [classify_artifact(item) for item in scanned_artifacts]
    classified = sorted(classified, key=lambda item: item["run_identifier"])
    suspect_classes = {
        "suspect_missing_pytest_execution_evidence",
        "suspect_missing_selection_integrity_evidence",
        "suspect_noncanonical_ref_acceptance",
        "suspect_warn_pass_equivalence",
        "suspect_degraded_ref_resolution",
        "insufficient_evidence_to_determine",
    }
    suspects = [item for item in classified if item["classification"] in suspect_classes]

    summary_counts: dict[str, int] = {}
    for item in classified:
        key = item["classification"]
        summary_counts[key] = summary_counts.get(key, 0) + 1

    if not suspects:
        final_decision = "PASS"
    elif any(item["classification"] != "insufficient_evidence_to_determine" for item in suspects):
        final_decision = "BLOCK"
    else:
        final_decision = "WARN"

    result = {
        "artifact_type": "pytest_trust_gap_backtest_result",
        "schema_version": "1.0.0",
        "audit_window": audit_scope,
        "evaluated_runs": len(classified),
        "suspect_runs": len(suspects),
        "run_classifications": classified,
        "summary_counts": dict(sorted(summary_counts.items())),
        "final_decision": final_decision,
        "generated_at": generated_at or _utc_now(),
    }
    validate_artifact(result, "pytest_trust_gap_backtest_result")
    return result


__all__ = ["scan_preflight_artifacts", "classify_artifact", "run_pytest_trust_gap_audit"]
