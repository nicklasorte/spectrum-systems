"""Deterministic baseline gate decisioning for governed drift artifacts."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_GENERATED_BY_VERSION = "baseline_gating.py@1.0.0"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_POLICY_PATH = _REPO_ROOT / "data" / "policy" / "baseline_gate_policy.json"


class BaselineGatingError(Exception):
    """Raised when baseline gating cannot produce a safe deterministic decision."""


def _validate_or_raise(instance: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise BaselineGatingError(f"{context} failed validation: {details}")


def _stable_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_baseline_gate_policy(policy_path: Path | None = None) -> Dict[str, Any]:
    """Load canonical baseline gate policy from governed policy directory."""
    path = policy_path or _DEFAULT_POLICY_PATH
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BaselineGatingError(f"baseline gate policy not found: {path}") from exc
    except OSError as exc:
        raise BaselineGatingError(f"failed reading baseline gate policy: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineGatingError(f"baseline gate policy is not valid JSON: {exc}") from exc

    _validate_or_raise(policy, "baseline_gate_policy", context="baseline_gate_policy")
    return policy


def build_baseline_gate_decision(
    drift_result: Dict[str, Any],
    policy: Dict[str, Any],
    *,
    trace_id: str | None = None,
    run_id: str | None = None,
) -> Dict[str, Any]:
    """Build deterministic baseline gate decision from drift result + policy."""
    if not isinstance(drift_result, dict) or not isinstance(policy, dict):
        raise BaselineGatingError("drift_result and policy must be objects")

    drift_input = deepcopy(drift_result)
    _validate_or_raise(drift_input, "drift_detection_result", context="drift_detection_result")
    _validate_or_raise(policy, "baseline_gate_policy", context="baseline_gate_policy")

    drift_status = drift_input.get("drift_status")
    triggered_thresholds = list(drift_input.get("triggered_thresholds") or [])
    warn_present = any(item.get("severity") == "warn" for item in triggered_thresholds)

    if drift_status in {"invalid_comparison", "exceeds_threshold"}:
        status = "block"
        enforcement_action = "block_promotion"
        reasons = [f"drift status {drift_status} requires fail-closed block"]
    elif drift_status == "within_threshold" and bool(policy.get("warn_on_within_threshold", True)) and warn_present:
        status = "warn"
        enforcement_action = "flag"
        reasons = ["drift status within_threshold with warn-level thresholds"]
    elif drift_status == "no_drift":
        status = "pass"
        enforcement_action = "allow"
        reasons = ["drift status no_drift"]
    else:
        status = "block"
        enforcement_action = "block_promotion"
        reasons = ["unexpected drift status mapping; fail-closed block"]

    resolved_trace_id = trace_id or (drift_input.get("trace_refs") or {}).get("trace_id")
    resolved_run_id = run_id or drift_input.get("run_id")
    timestamp = drift_input.get("timestamp")

    preimage = {
        "timestamp": timestamp,
        "trace_id": resolved_trace_id,
        "run_id": resolved_run_id,
        "drift_result_id": drift_input.get("artifact_id"),
        "policy_id": policy.get("policy_id"),
        "baseline_id": drift_input.get("baseline_id"),
        "status": status,
    }
    result = {
        "decision_id": _stable_id(preimage),
        "timestamp": timestamp,
        "trace_id": resolved_trace_id,
        "run_id": resolved_run_id,
        "drift_result_id": drift_input.get("artifact_id"),
        "policy_id": policy.get("policy_id"),
        "baseline_id": drift_input.get("baseline_id"),
        "status": status,
        "enforcement_action": enforcement_action,
        "triggered_thresholds": triggered_thresholds,
        "reasons": reasons,
        "generated_by_version": _GENERATED_BY_VERSION,
    }
    _validate_or_raise(result, "baseline_gate_decision", context="baseline_gate_decision")
    return result
