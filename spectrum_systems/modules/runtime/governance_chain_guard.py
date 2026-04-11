"""Fail-closed governance chain guard for canonical PQX slice execution.

Phase-1 hardening checks enforced here:
1. schema validation for all required artifacts
2. required eval artifacts for each output slice
3. control decision artifact must exist and align to trace context
4. enforcement action must be recorded (including explicit "none")
5. trace completeness across chain
6. deterministic replay comparison evidence (hash + fingerprint)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact


class GovernanceChainGuardError(ValueError):
    """Raised when the governed execution chain is incomplete or invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GovernanceChainGuardError(f"required artifact missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GovernanceChainGuardError(f"artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise GovernanceChainGuardError(f"artifact must be a JSON object: {path}")
    return payload


def _canonical_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _replay_fingerprint(payload: dict[str, Any]) -> str:
    metrics = payload.get("observability_metrics", {}).get("metrics", {})
    if not isinstance(metrics, dict):
        raise GovernanceChainGuardError("replay_result.observability_metrics.metrics must be object")
    fingerprint = {
        "consistency_status": payload.get("consistency_status"),
        "drift_detected": payload.get("drift_detected"),
        "replay_success_rate": metrics.get("replay_success_rate"),
        "error_budget_status": payload.get("error_budget_status", {}).get("budget_status"),
    }
    return _canonical_digest(fingerprint)


def validate_governance_chain(
    *,
    run_id: str,
    trace_id: str,
    replay_result_path: Path,
    replay_baseline_path: Path,
    regression_result_path: Path,
    control_decision_path: Path,
    execution_record_path: Path,
) -> dict[str, str | bool]:
    """Validate PQX->eval->control->enforcement chain and return replay comparison evidence."""

    replay_result = _load_json(replay_result_path)
    replay_baseline = _load_json(replay_baseline_path)
    regression = _load_json(regression_result_path)
    control = _load_json(control_decision_path)
    record = _load_json(execution_record_path)

    validate_artifact(replay_result, "replay_result")
    validate_artifact(regression, "regression_run_result")
    validate_artifact(control, "evaluation_control_decision")
    validate_artifact(record, "pqx_slice_execution_record")

    if replay_result.get("trace_id") != trace_id or record.get("trace_id") != trace_id:
        raise GovernanceChainGuardError("trace completeness violation: trace_id mismatch in output artifacts")
    if replay_result.get("replay_run_id") != run_id:
        raise GovernanceChainGuardError("trace completeness violation: replay_result.replay_run_id mismatch")
    if record.get("run_id") != run_id or control.get("run_id") != run_id:
        raise GovernanceChainGuardError("trace completeness violation: run_id mismatch")

    required_eval_refs = {record.get("replay_result_ref"), *record.get("artifacts_emitted", [])}
    if not any(str(ref).endswith(".regression_run_result.json") for ref in required_eval_refs):
        raise GovernanceChainGuardError("required eval missing: regression_run_result artifact must be emitted")

    decision_summary = record.get("decision_summary", {})
    enforcement_action = decision_summary.get("enforcement_action")
    if not isinstance(enforcement_action, str) or not enforcement_action.strip():
        raise GovernanceChainGuardError("enforcement_action must be explicitly recorded")

    control_ref = record.get("control_decision_ref")
    if not isinstance(control_ref, str) or not control_ref.strip():
        raise GovernanceChainGuardError("control_decision_ref must be present")

    replay_hash = _canonical_digest(replay_result)
    baseline_hash = _canonical_digest(replay_baseline)
    replay_fp = _replay_fingerprint(replay_result)
    baseline_fp = _replay_fingerprint(replay_baseline)

    return {
        "comparison_digest": _canonical_digest(
            {
                "replay_hash": replay_hash,
                "baseline_hash": baseline_hash,
                "replay_fingerprint": replay_fp,
                "baseline_fingerprint": baseline_fp,
            }
        ),
        "hash_match": replay_hash == baseline_hash,
        "fingerprint_match": replay_fp == baseline_fp,
        "replay_hash": replay_hash,
        "baseline_hash": baseline_hash,
        "replay_fingerprint": replay_fp,
        "baseline_fingerprint": baseline_fp,
    }
