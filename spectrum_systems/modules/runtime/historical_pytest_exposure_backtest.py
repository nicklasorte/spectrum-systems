"""Deterministic historical backtest for pytest trust exposure windows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"artifact_not_object:{path}")
    return payload


def scan_historical_preflight_artifacts(scan_roots: list[Path], *, max_items: int = 200) -> list[dict[str, Any]]:
    found: list[Path] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.glob("**/contract_preflight_result_artifact.json"):
            if path.is_file():
                found.append(path)
    deduped = sorted({path.resolve() for path in found}, key=lambda p: str(p))[:max_items]
    records: list[dict[str, Any]] = []
    for path in deduped:
        payload = _read_json(path)
        payload["__artifact_path"] = str(path.as_posix())
        records.append(payload)
    return records


def _is_pr_event(payload: dict[str, Any]) -> bool:
    execution = payload.get("pytest_execution")
    if not isinstance(execution, dict):
        return False
    event_name = str(execution.get("event_name") or "").strip().lower()
    return event_name in {"pull_request", "pull_request_target", "pull_request_review", "pull_request_review_comment"}


def _classification_for(payload: dict[str, Any]) -> tuple[str, list[str], str, list[str]]:
    reasons: list[str] = []
    followup: list[str] = []

    control_signal = payload.get("control_signal")
    decision = str((control_signal or {}).get("strategy_gate_decision") or "").upper()
    trusting = decision in {"ALLOW", "WARN"} or str(payload.get("preflight_status") or "").lower() == "passed"

    execution = payload.get("pytest_execution")
    execution_ref = str(payload.get("pytest_execution_record_ref") or "").strip()
    selection = payload.get("pytest_selection_integrity")
    selection_ref = str(payload.get("pytest_selection_integrity_result_ref") or "").strip()
    linkage = payload.get("pytest_artifact_linkage")

    if not isinstance(execution, dict) or int(execution.get("pytest_execution_count") or 0) < 1:
        reasons.append("MISSING_OR_EMPTY_PYTEST_EXECUTION")

    if not isinstance(selection, dict):
        reasons.append("MISSING_PYTEST_SELECTION_INTEGRITY")
    elif str(selection.get("selection_integrity_decision") or "BLOCK") != "ALLOW":
        reasons.append("SELECTION_INTEGRITY_NOT_ALLOW")

    if _is_pr_event(payload):
        if execution_ref != "outputs/contract_preflight/pytest_execution_record.json":
            reasons.append("MISSING_OR_NONCANONICAL_PYTEST_EXECUTION_REF")
        if selection_ref != "outputs/contract_preflight/pytest_selection_integrity_result.json":
            reasons.append("MISSING_OR_NONCANONICAL_SELECTION_REF")

    if trusting and decision == "WARN" and _is_pr_event(payload):
        reasons.append("WARN_TRUST_EQUIVALENCE")

    if not isinstance(linkage, dict):
        reasons.append("MISSING_ARTIFACT_BOUNDARY_LINKAGE")

    trace = payload.get("trace")
    if not isinstance(trace, dict):
        reasons.append("MISSING_TRACE_CONTEXT")
    elif bool(trace.get("fallback_used")):
        reasons.append("DEGRADED_SELECTION_INTEGRITY_PROVENANCE")

    classification = "trustworthy"
    confidence = "high"

    if reasons:
        if "WARN_TRUST_EQUIVALENCE" in reasons:
            classification = "suspect_warn_pass_equivalence"
            followup.append("Review historical WARN handling and confirm non-pass-equivalence for pull_request trust outcomes.")
        elif any(reason in reasons for reason in ["MISSING_OR_EMPTY_PYTEST_EXECUTION", "MISSING_OR_NONCANONICAL_PYTEST_EXECUTION_REF"]):
            classification = "suspect_missing_pytest_execution"
            followup.append("Retrieve canonical pytest execution record evidence for the item before trust assertions.")
        elif any(reason in reasons for reason in ["MISSING_PYTEST_SELECTION_INTEGRITY", "SELECTION_INTEGRITY_NOT_ALLOW", "MISSING_OR_NONCANONICAL_SELECTION_REF", "DEGRADED_SELECTION_INTEGRITY_PROVENANCE"]):
            classification = "suspect_missing_selection_integrity"
            followup.append("Retrieve/verify canonical pytest selection integrity evidence and selection_integrity_decision=ALLOW.")
        elif "MISSING_ARTIFACT_BOUNDARY_LINKAGE" in reasons:
            classification = "suspect_missing_artifact_boundary_enforcement"
            followup.append("Confirm artifact-boundary linkage exists and points to canonical preflight evidence outputs.")

    if classification == "trustworthy" and trusting and not _is_pr_event(payload):
        classification = "suspect_visibility_only_without_trust"
        reasons.append("NON_PR_CONTEXT_TRUST_SIGNAL")
        confidence = "medium"
        followup.append("Do not treat non-pull_request visibility signals as PR trust-equivalent evidence.")

    if classification == "trustworthy" and (not trusting):
        classification = "insufficient_evidence_to_determine"
        confidence = "low"
        reasons.append("NON_TRUSTING_DECISION_STATE")
        followup.append("Retrieve historical decision context; trust could not be inferred from available artifacts.")

    if classification == "trustworthy" and not reasons:
        followup.append("No immediate operator follow-up required for this item.")

    if classification == "trustworthy" and not isinstance(execution, dict) and not isinstance(selection, dict):
        classification = "insufficient_evidence_to_determine"
        confidence = "low"

    return classification, sorted(set(reasons)), confidence, sorted(set(followup))


def classify_historical_item(payload: dict[str, Any]) -> dict[str, Any]:
    identifier = str(payload.get("run_id") or payload.get("trace_id") or payload.get("artifact_id") or payload.get("__artifact_path") or "unknown")
    evidence_refs = [str(payload.get("__artifact_path") or "unknown")]
    for key in ("pytest_execution_record_ref", "pytest_selection_integrity_result_ref"):
        ref = str(payload.get(key) or "").strip()
        if ref:
            evidence_refs.append(ref)

    classification, reasons, confidence, followup = _classification_for(payload)

    return {
        "identifier": identifier,
        "type": "run",
        "evidence_refs": sorted(set(evidence_refs)),
        "classification": classification,
        "reasons": reasons,
        "confidence": confidence,
        "recommended_followup": followup,
    }


def run_historical_pytest_exposure_backtest(
    *,
    evidence_sources: dict[str, Any],
    evaluated_items: list[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    classifications = sorted((classify_historical_item(item) for item in evaluated_items), key=lambda item: item["identifier"])
    suspect_set = {
        "suspect_missing_pytest_execution",
        "suspect_missing_artifact_boundary_enforcement",
        "suspect_missing_selection_integrity",
        "suspect_warn_pass_equivalence",
        "suspect_visibility_only_without_trust",
        "insufficient_evidence_to_determine",
    }
    suspect_items = [item["identifier"] for item in classifications if item["classification"] in suspect_set]

    summary_counts: dict[str, int] = {}
    for item in classifications:
        key = item["classification"]
        summary_counts[key] = summary_counts.get(key, 0) + 1

    final_decision = "PASS"
    if suspect_items:
        if any(item["classification"] != "insufficient_evidence_to_determine" for item in classifications if item["identifier"] in suspect_items):
            final_decision = "BLOCK"
        else:
            final_decision = "WARN"

    result = {
        "artifact_type": "historical_pytest_exposure_backtest_result",
        "schema_version": "1.0.0",
        "audit_window": evidence_sources.get("audit_window", {}),
        "evidence_sources": evidence_sources,
        "evaluated_items": len(classifications),
        "suspect_items": sorted(suspect_items),
        "classifications": classifications,
        "summary_counts": dict(sorted(summary_counts.items())),
        "final_decision": final_decision,
        "generated_at": generated_at or _utc_now(),
    }
    validate_artifact(result, "historical_pytest_exposure_backtest_result")
    return result


__all__ = [
    "scan_historical_preflight_artifacts",
    "classify_historical_item",
    "run_historical_pytest_exposure_backtest",
]
