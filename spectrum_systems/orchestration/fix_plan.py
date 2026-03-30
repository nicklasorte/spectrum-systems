"""Deterministic governed fix-plan generation from remediation artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class FixPlanError(ValueError):
    """Raised when deterministic fix-plan generation fails fail-closed checks."""


def _canonical_json_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_ACTION_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "manifest_repair": [
        {"action_type": "update_manifest", "target": "cycle_manifest", "required": True},
        {"action_type": "rerun_validation", "target": "next_step_decision", "required": True},
    ],
    "provenance_repair": [
        {"action_type": "restore_provenance", "target": "governance_provenance", "required": True},
        {"action_type": "regenerate_review", "target": "roadmap_review_artifact", "required": True},
    ],
    "contract_repair": [
        {"action_type": "repair_artifact", "target": "contract_payload", "required": True},
        {"action_type": "rerun_validation", "target": "contract_schema", "required": True},
    ],
    "roadmap_repair": [
        {"action_type": "repair_artifact", "target": "drift_detection_result", "required": True},
        {"action_type": "rerun_validation", "target": "next_step_decision", "required": True},
    ],
    "review_repair": [
        {"action_type": "create_artifact", "target": "required_review_artifact", "required": True},
        {"action_type": "reroute_for_review", "target": "roadmap_or_implementation_review", "required": True},
    ],
    "execution_artifact_repair": [
        {"action_type": "create_artifact", "target": "required_execution_artifact", "required": True},
        {"action_type": "rerun_validation", "target": "execution_artifact_schema", "required": True},
    ],
    "governance_alignment_repair": [
        {"action_type": "update_manifest", "target": "governance_authorities", "required": True},
        {"action_type": "attach_missing_evidence", "target": "source_authorities", "required": True},
    ],
    "judgment_evidence_repair": [
        {"action_type": "attach_missing_evidence", "target": "judgment_evidence", "required": True},
        {"action_type": "rerun_validation", "target": "judgment_eval_result", "required": True},
    ],
    "certification_input_repair": [
        {"action_type": "attach_missing_evidence", "target": "done_certification_input_refs", "required": True},
        {"action_type": "rerun_validation", "target": "done_certification_record", "required": True},
    ],
}


def build_fix_plan_artifact(*, manifest: Dict[str, Any], decision: Dict[str, Any], remediation: Dict[str, Any]) -> Dict[str, Any]:
    required = ("cycle_id", "decision_id", "remediation_id", "remediation_class", "policy_id", "policy_version", "policy_hash")
    for key in required:
        if not isinstance(remediation.get(key), str) or not remediation.get(key):
            raise FixPlanError(f"missing remediation field required for fix plan: {key}")

    remediation_class = str(remediation["remediation_class"])
    actions = _ACTION_TEMPLATES.get(remediation_class)
    if actions is None:
        raise FixPlanError(f"unsupported remediation_class for fix-plan generation: {remediation_class}")

    generated_at = manifest.get("updated_at") if isinstance(manifest.get("updated_at"), str) else "1970-01-01T00:00:00Z"
    category = remediation.get("normalized_category", "lifecycle_state_input_mismatch")

    required_artifacts = sorted({
        action["target"] for action in actions
    } | {"next_step_decision_artifact", "drift_remediation_artifact"})

    core = {
        "cycle_id": remediation["cycle_id"],
        "remediation_id": remediation["remediation_id"],
        "decision_id": remediation["decision_id"],
        "current_state": remediation.get("current_state", manifest.get("current_state", "invalid")),
        "blocking": bool(remediation.get("blocking", True)),
        "remediation_class": remediation_class,
        "objective": f"produce governed artifacts required to clear {category}",
        "required_actions": actions,
        "required_artifacts": required_artifacts,
        "validation_requirements": [
            "schema:drift_remediation_artifact",
            "schema:fix_plan_artifact",
            f"policy:{remediation['policy_id']}@{remediation['policy_version']}",
        ],
        "completion_criteria": [
            f"{category} resolved",
            "next_step_decision.blocking == false",
        ],
        "blocking_conditions": [
            "required_actions_incomplete",
            "required_artifacts_missing",
            "validation_requirements_failed",
        ],
        "allowed_next_state_when_satisfied": str(decision.get("current_state", manifest.get("current_state", "blocked"))),
        "prohibited_progression_until_complete": True,
        "evidence_refs": sorted(set(str(item) for item in remediation.get("evidence_refs", []) if isinstance(item, str))),
        "policy_id": remediation["policy_id"],
        "policy_version": remediation["policy_version"],
        "policy_hash": remediation["policy_hash"],
        "generated_at": generated_at,
    }

    artifact = {
        "fix_plan_id": _canonical_json_id(core),
        **core,
    }

    schema = load_schema("fix_plan_artifact")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)
    return artifact
