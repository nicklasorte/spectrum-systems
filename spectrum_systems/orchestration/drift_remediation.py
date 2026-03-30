"""Deterministic drift remediation policy loading and artifact generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "policy" / "drift_remediation_policy.json"
_REQUIRED_POLICY_ID = "DRIFT_REMEDIATION_POLICY"
_REQUIRED_COMPATIBILITY_VERSION = "1.0"


class DriftRemediationError(ValueError):
    """Raised when remediation policy or artifact generation fails fail-closed checks."""


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DriftRemediationError(f"expected object artifact: {path}")
    return payload


def _canonical_json_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_json_id(payload: Dict[str, Any]) -> str:
    return _canonical_json_hash(payload)


def _validate_policy_compatibility(policy: Dict[str, Any]) -> None:
    if policy.get("policy_id") != _REQUIRED_POLICY_ID:
        raise DriftRemediationError("drift remediation policy_id is incompatible")
    if policy.get("compatibility_version") != _REQUIRED_COMPATIBILITY_VERSION:
        raise DriftRemediationError("drift remediation policy compatibility_version is incompatible")

    mappings = policy.get("category_mappings")
    if not isinstance(mappings, list) or not mappings:
        raise DriftRemediationError("drift remediation policy missing category_mappings")

    seen_categories: set[str] = set()
    for item in mappings:
        if not isinstance(item, dict):
            raise DriftRemediationError("drift remediation policy category mapping entry must be an object")
        category = item.get("category")
        if not isinstance(category, str) or not category:
            raise DriftRemediationError("drift remediation policy category mapping missing category")
        if category in seen_categories:
            raise DriftRemediationError(f"drift remediation policy has ambiguous duplicate category mapping: {category}")
        seen_categories.add(category)


def load_drift_remediation_policy(policy_path: str | Path | None = None) -> tuple[Dict[str, Any], str]:
    path = Path(policy_path) if policy_path is not None else _POLICY_PATH
    if not path.is_file():
        raise DriftRemediationError(f"drift remediation policy missing: {path}")

    try:
        policy = _load_json(path)
    except json.JSONDecodeError as exc:
        raise DriftRemediationError("drift remediation policy is not valid JSON") from exc

    schema = load_schema("drift_remediation_policy")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(policy), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise DriftRemediationError(f"drift remediation policy failed schema validation: {details}")

    _validate_policy_compatibility(policy)
    return policy, _canonical_json_hash(policy)


def normalize_blocking_category(*, decision: Dict[str, Any], manifest: Dict[str, Any]) -> str:
    required_missing = decision.get("required_inputs_missing")
    if isinstance(required_missing, list):
        missing_joined = " ".join(str(item) for item in required_missing)
        if "strategy_authority" in missing_joined:
            return "missing_strategy_authority"
        if "source_authorities" in missing_joined:
            return "missing_source_authorities"
        if "roadmap_review_artifact_paths" in missing_joined or "implementation_review_paths" in missing_joined:
            return "missing_required_review_artifact"
        if "execution_report_paths" in missing_joined or "fix_execution_report_paths" in missing_joined:
            return "missing_required_execution_artifact"
        if "done_certification_input_refs" in missing_joined:
            return "certification_readiness_gap"
        if "judgment_" in missing_joined:
            return "judgment_gap"

    drift_detected = decision.get("drift_detected") is True
    if drift_detected:
        return "blocking_drift_finding"

    reasons = decision.get("blocking_reasons")
    reasons_joined = " ".join(str(item) for item in reasons) if isinstance(reasons, list) else ""
    if "invariant" in reasons_joined:
        return "blocking_invariant_violation"
    if "provenance" in reasons_joined:
        return "invalid_governance_provenance"
    if "schema validation" in reasons_joined or "schema" in reasons_joined:
        return "schema_compliance_gap"

    current_state = manifest.get("current_state")
    decision_state = decision.get("current_state")
    if isinstance(current_state, str) and isinstance(decision_state, str) and current_state != decision_state:
        return "lifecycle_state_input_mismatch"

    if str(manifest.get("current_state", "")) == "blocked":
        return "blocking_invariant_violation"

    return "lifecycle_state_input_mismatch"


def _resolve_mapping(category: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    mappings = [item for item in policy["category_mappings"] if item.get("category") == category]
    if len(mappings) != 1:
        raise DriftRemediationError(f"drift remediation routing is ambiguous for category: {category}")
    return mappings[0]


def build_drift_remediation_artifact(
    *, manifest: Dict[str, Any], decision: Dict[str, Any], policy: Dict[str, Any], policy_hash: str
) -> Dict[str, Any]:
    if decision.get("blocking") is not True:
        raise DriftRemediationError("drift remediation artifact requires blocking decision")

    cycle_id = manifest.get("cycle_id")
    decision_id = decision.get("decision_id")
    current_state = manifest.get("current_state")
    if not all(isinstance(item, str) and item for item in (cycle_id, decision_id, current_state)):
        raise DriftRemediationError("missing required cycle/decision identity fields for remediation artifact")

    category = normalize_blocking_category(decision=decision, manifest=manifest)
    mapping = _resolve_mapping(category, policy)

    blocking_reasons = decision.get("blocking_reasons")
    if isinstance(blocking_reasons, list) and blocking_reasons:
        triggering_issue = str(sorted(blocking_reasons)[0])
    else:
        triggering_issue = "blocking decision requires governed remediation"

    evidence_refs = sorted(set(str(item) for item in decision.get("drift_reasons", []) if isinstance(item, str)))
    strategy = manifest.get("strategy_authority")
    strategy_ref = strategy.get("path") if isinstance(strategy, dict) else None
    sources = manifest.get("source_authorities")
    source_refs = sorted(
        {
            str(item.get("path"))
            for item in sources
            if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("path")
        }
    )

    created_at = manifest.get("updated_at") if isinstance(manifest.get("updated_at"), str) else "1970-01-01T00:00:00Z"
    core = {
        "cycle_id": cycle_id,
        "decision_id": decision_id,
        "current_state": current_state,
        "triggering_issue": triggering_issue,
        "normalized_category": category,
        "remediation_class": mapping["remediation_class"],
        "blocking": bool(mapping.get("blocking", policy.get("default_blocking", True))),
        "evidence_refs": evidence_refs,
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "policy_hash": policy_hash,
        "strategy_authority_ref": strategy_ref,
        "source_authorities_refs": source_refs,
        "trace_ref": cycle_id,
        "created_at": created_at,
    }
    remediation = {
        "remediation_id": _canonical_json_id(core),
        **core,
        "rationale": (
            f"category={category};class={mapping['remediation_class']};"
            f"blocking={'true' if core['blocking'] else 'false'}"
        ),
    }

    schema = load_schema("drift_remediation_artifact")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(remediation)
    return remediation
