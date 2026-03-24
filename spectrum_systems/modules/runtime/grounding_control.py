"""HS-20 deterministic grounding control gate.

Consumes HS-19 grounding_factcheck_eval outputs and emits an auditable,
schema-valid grounding_control_decision artifact used for enforcement wiring.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class GroundingControlError(RuntimeError):
    """Fail-closed runtime error for HS-20 grounding control gate."""


_DEFAULT_POLICY_ID = "grounding-control-v1"
_DEFAULT_GENERATED_BY_VERSION = "hs-20.1.0"


def _deterministic_timestamp(payload: Mapping[str, Any], *, stage: str) -> str:
    seed = json.dumps({"stage": stage, "payload": payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _valid_timestamp_or_fallback(candidate: Any, fallback_payload: Mapping[str, Any]) -> str:
    if isinstance(candidate, str):
        try:
            datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return candidate.replace("+00:00", "Z")
        except ValueError:
            pass
    return _deterministic_timestamp(fallback_payload, stage="grounding_control_decision")


def build_grounding_control_decision(
    eval_artifact: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build deterministic HS-20 control decision from HS-19 evaluation output."""
    policy_map = dict(policy or {})
    policy_id = str(policy_map.get("policy_id") or _DEFAULT_POLICY_ID)
    generated_by_version = str(policy_map.get("generated_by_version") or _DEFAULT_GENERATED_BY_VERSION)
    triggered_rules: list[str] = []

    malformed_input = not isinstance(eval_artifact, Mapping)
    eval_map = dict(eval_artifact) if isinstance(eval_artifact, Mapping) else {}

    trace_linkage = eval_map.get("trace_linkage") if isinstance(eval_map.get("trace_linkage"), Mapping) else {}
    run_id = str(trace_linkage.get("run_id") or "")
    trace_id = str(trace_linkage.get("trace_id") or "")
    grounding_eval_id = str(eval_map.get("eval_id") or "")

    if (
        str(eval_map.get("artifact_type") or "") != "grounding_factcheck_eval"
        or not run_id
        or not trace_id
        or not grounding_eval_id
        or not isinstance(eval_map.get("claim_results"), list)
    ):
        malformed_input = True

    total_claims = 0
    supported_claims = 0
    unsupported_claims = 0
    invalid_evidence_refs = 0

    if malformed_input:
        triggered_rules.append("malformed_eval_input")
    else:
        claim_results = list(eval_map.get("claim_results") or [])
        total_claims = len(claim_results)
        for claim in claim_results:
            if not isinstance(claim, Mapping):
                malformed_input = True
                triggered_rules = ["malformed_eval_input"]
                break
            classification = str(claim.get("claim_classification_from_binding") or "").strip()
            rationale_code = str(claim.get("rationale_code") or "").strip()
            if classification == "unsupported":
                unsupported_claims += 1
            if rationale_code == "direct_invalid_evidence_ref":
                invalid_evidence_refs += 1
            if classification in {"directly_supported", "inferred"}:
                supported_claims += 1

    if malformed_input:
        status = "block"
        enforcement_action = "block_execution"
        if not run_id:
            run_id = "malformed-run"
        if not trace_id:
            trace_id = "malformed-trace"
        if not grounding_eval_id:
            grounding_eval_id = "malformed-grounding-eval"
    elif invalid_evidence_refs > 0:
        status = "block"
        enforcement_action = "block_execution"
        triggered_rules.append("invalid_evidence_refs_gt_zero")
    elif unsupported_claims > 0:
        status = "warn"
        enforcement_action = "flag"
        triggered_rules.append("unsupported_claims_gt_zero")
    else:
        status = "pass"
        enforcement_action = "allow"
        triggered_rules.append("all_claims_grounded")

    seed_payload = {
        "trace_id": trace_id,
        "run_id": run_id,
        "grounding_eval_id": grounding_eval_id,
        "status": status,
        "failure_summary": {
            "total_claims": total_claims,
            "supported_claims": supported_claims,
            "unsupported_claims": unsupported_claims,
            "invalid_evidence_refs": invalid_evidence_refs,
        },
        "triggered_rules": sorted(triggered_rules),
        "policy_id": policy_id,
        "generated_by_version": generated_by_version,
    }

    decision = {
        "decision_id": deterministic_id(prefix="gcd", namespace="grounding_control_decision", payload=seed_payload),
        "timestamp": _valid_timestamp_or_fallback(eval_map.get("created_at"), seed_payload),
        "trace_id": trace_id,
        "run_id": run_id,
        "grounding_eval_id": grounding_eval_id,
        "status": status,
        "failure_summary": seed_payload["failure_summary"],
        "triggered_rules": sorted(triggered_rules),
        "enforcement_action": enforcement_action,
        "policy_id": policy_id,
        "generated_by_version": generated_by_version,
    }

    try:
        _validate_contract(decision, "grounding_control_decision")
    except Exception as exc:  # pragma: no cover - explicit fail-closed boundary
        raise GroundingControlError(f"grounding control decision validation failed: {exc}") from exc
    return decision
