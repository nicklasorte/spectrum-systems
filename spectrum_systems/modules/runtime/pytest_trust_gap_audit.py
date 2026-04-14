"""Deterministic read-only audit for pytest trust gaps in recent preflight artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact

TRUSTING_DECISIONS = {"ALLOW", "WARN"}
KNOWN_PR_EVENTS = {"pull_request", "pull_request_target", "pull_request_review", "pull_request_review_comment"}


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


def classify_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    path = str(payload.get("__artifact_path") or "unknown")
    reasons: list[str] = []
    trusting = _is_trusting(payload)
    event_name = _event_name(payload)
    context = "pr" if event_name in KNOWN_PR_EVENTS else ("non_pr" if event_name else "unknown")

    execution = payload.get("pytest_execution")
    if not isinstance(execution, dict):
        reasons.append("MISSING_PYTEST_EXECUTION_ARTIFACT")
    else:
        if int(execution.get("pytest_execution_count") or 0) < 1:
            reasons.append("PYTEST_EXECUTION_COUNT_TOO_SMALL")
        selected = execution.get("selected_targets") or []
        if not isinstance(selected, list) or not selected:
            reasons.append("PYTEST_SELECTED_TARGETS_EMPTY")

    selection = payload.get("pytest_selection_integrity")
    if not isinstance(selection, dict):
        reasons.append("MISSING_PYTEST_SELECTION_INTEGRITY_ARTIFACT")
    else:
        if str(selection.get("selection_integrity_decision") or "BLOCK") != "ALLOW":
            reasons.append("PYTEST_SELECTION_INTEGRITY_NOT_ALLOW")

    classification = "clean_evidence"
    if reasons:
        classification = "weak_evidence" if context != "unknown" else "missing_evidence"
    if context == "unknown" and reasons:
        classification = "unable_to_evaluate"

    if trusting and reasons:
        reasons.append("TRUSTED_OUTCOME_WITH_GAP")

    return {
        "artifact_path": path,
        "classification": classification,
        "context": context,
        "trusting_outcome": trusting,
        "reason_codes": sorted(set(reasons)),
    }


def run_pytest_trust_gap_audit(*, scanned_artifacts: list[dict[str, Any]], audit_scope: dict[str, Any]) -> dict[str, Any]:
    classified = [classify_artifact(item) for item in scanned_artifacts]
    classified = sorted(classified, key=lambda item: item["artifact_path"])
    suspects = [item for item in classified if item["classification"] in {"weak_evidence", "missing_evidence", "unable_to_evaluate"}]

    generated_at = "1970-01-01T00:00:00Z"
    timestamps = sorted({str(item.get("generated_at")) for item in scanned_artifacts if isinstance(item.get("generated_at"), str)})
    if timestamps:
        generated_at = timestamps[-1]

    result = {
        "artifact_type": "pytest_trust_gap_audit_result",
        "schema_version": "1.0.0",
        "audit_scope": audit_scope,
        "scanned_artifact_count": len(classified),
        "suspect_count": len(suspects),
        "suspect_runs": suspects,
        "summary_reason_codes": sorted({code for item in suspects for code in item.get("reason_codes", [])}),
        "generated_at": generated_at,
        "trace": {
            "producer": "spectrum_systems.modules.runtime.pytest_trust_gap_audit",
            "classification_policy": "tsi-01-trust-gap-v1",
            "scan_mode": "repo_local_artifacts_only",
            "read_only": True
        }
    }
    validate_artifact(result, "pytest_trust_gap_audit_result")
    return result


__all__ = ["scan_preflight_artifacts", "classify_artifact", "run_pytest_trust_gap_audit"]
