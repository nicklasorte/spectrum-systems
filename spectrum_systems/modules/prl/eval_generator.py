"""PRL-03: Failure → eval generation and promotion pipeline.

Promotion rule: eval_case_candidate → prl_eval_case ONLY IF:
  1. failure_class is in KNOWN_FAILURE_CLASSES (and not unknown_failure)
  2. deterministic validation exists (eval_type in _DETERMINISTIC_EVAL_TYPES)
  3. schema + threshold defined in _EVAL_TEMPLATES

Else: mark as requires_human_review. Fail-closed everywhere.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from spectrum_systems.utils.artifact_envelope import build_artifact_envelope
from spectrum_systems.utils.deterministic_id import deterministic_id
from spectrum_systems.modules.prl.failure_classifier import (
    Classification,
    KNOWN_FAILURE_CLASSES,
)

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "prl"

_EVAL_TEMPLATES: dict[str, dict[str, Any]] = {
    "pytest_selection_missing": {
        "eval_type": "failure_regression_check",
        "target_artifact": "pytest_collection_output",
        "pass_condition": "pytest collection includes at least one test for the changed module",
        "threshold": 1.0,
    },
    "authority_shape_violation": {
        "eval_type": "policy_alignment",
        "target_artifact": "authority_shape_preflight_result",
        "pass_condition": "authority_shape_preflight reports zero violations for changed files",
        "threshold": 1.0,
    },
    "system_registry_mismatch": {
        "eval_type": "schema_conformance",
        "target_artifact": "system_registry_guard_result",
        "pass_condition": "system_registry_guard reports zero mismatches",
        "threshold": 1.0,
    },
    "contract_schema_violation": {
        "eval_type": "schema_conformance",
        "target_artifact": "contract_preflight_result",
        "pass_condition": "all artifact schemas validate without errors against contracts/schemas/",
        "threshold": 1.0,
    },
    "missing_required_artifact": {
        "eval_type": "failure_regression_check",
        "target_artifact": "artifact_lineage_record",
        "pass_condition": "all required artifacts are present in lineage before downstream steps",
        "threshold": 1.0,
    },
    "trace_missing": {
        "eval_type": "schema_conformance",
        "target_artifact": "artifact_trace_refs",
        "pass_condition": "all produced artifacts have non-empty trace_refs.primary",
        "threshold": 1.0,
    },
    "replay_mismatch": {
        "eval_type": "replay_consistency",
        "target_artifact": "replay_integrity_result",
        "pass_condition": "replay determinism rate >= 0.95 across 3 independent runs",
        "threshold": 0.95,
    },
    "policy_mismatch": {
        "eval_type": "policy_alignment",
        "target_artifact": "trust_policy_decision",
        "pass_condition": "policy alignment check passes with zero violations",
        "threshold": 1.0,
    },
    "timeout": {
        "eval_type": "failure_regression_check",
        "target_artifact": "pqx_execution_closure_record",
        "pass_condition": "execution completes within configured timeout budget",
        "threshold": 1.0,
    },
    "rate_limited": {
        "eval_type": "failure_regression_check",
        "target_artifact": "pqx_execution_closure_record",
        "pass_condition": "execution succeeds with retry backoff applied, no rate limit error",
        "threshold": 1.0,
    },
    "unknown_failure": {
        "eval_type": "failure_regression_check",
        "target_artifact": "fre_diagnosis_record",
        "pass_condition": "failure classified and FRE diagnosis record produced",
        "threshold": 1.0,
    },
}

_DETERMINISTIC_EVAL_TYPES: frozenset[str] = frozenset({
    "schema_conformance",
    "policy_alignment",
    "replay_consistency",
    "failure_regression_check",
})


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"PRL schema not found — fail-closed: {path}")
    with path.open() as f:
        return json.load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate(artifact: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    try:
        jsonschema.validate(artifact, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"PRL artifact {schema_name} failed schema validation: {exc.message}"
        ) from exc


def _is_promotable(classification: Classification) -> tuple[bool, str]:
    """Promotion eligibility check. Fail-closed: unknown → not eligible."""
    fc = classification.failure_class
    if fc not in KNOWN_FAILURE_CLASSES or fc == "unknown_failure":
        return False, "unknown_failure requires human review before eval promotion"
    template = _EVAL_TEMPLATES.get(fc)
    if template is None:
        return False, f"no eval template defined for failure_class={fc}"
    if template["eval_type"] not in _DETERMINISTIC_EVAL_TYPES:
        return False, f"eval_type={template['eval_type']} is not deterministically validatable"
    return True, ""


def generate_eval_case_candidate(
    *,
    failure_packet: dict[str, Any],
    classification: Classification,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Generate an eval_case_candidate. Step 1 of the eval promotion pipeline."""
    ts = _now_iso()
    packet_ref = f"pre_pr_failure_packet:{failure_packet['id']}"
    template = _EVAL_TEMPLATES.get(
        classification.failure_class,
        _EVAL_TEMPLATES["unknown_failure"],
    )
    promotable, block_reason = _is_promotable(classification)

    payload = {
        "packet_ref": packet_ref,
        "failure_class": classification.failure_class,
        "eval_type": template["eval_type"],
        "run_id": run_id,
    }
    artifact_id = deterministic_id(
        prefix="prl-cnd",
        payload=payload,
        namespace="prl::candidate",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
        related_trace_refs=[failure_packet["trace_id"]],
    )
    artifact: dict[str, Any] = {
        "artifact_type": "eval_case_candidate",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "failure_packet_ref": packet_ref,
        "failure_class": classification.failure_class,
        "eval_type": template["eval_type"],
        "target_artifact": template["target_artifact"],
        "pass_condition": template["pass_condition"],
        "required": True,
        "promotion_eligible": promotable,
        "promotion_blocked_reason": block_reason if not promotable else "",
    }
    _validate(artifact, "eval_case_candidate")
    return artifact


def promote_to_eval_case(
    *,
    candidate: dict[str, Any],
    classification: Classification,
    run_id: str,
    trace_id: str,
) -> Optional[dict[str, Any]]:
    """Promote eval_case_candidate → prl_eval_case if eligible. Returns None otherwise."""
    if not candidate.get("promotion_eligible", False):
        return None

    ts = _now_iso()
    template = _EVAL_TEMPLATES[classification.failure_class]
    candidate_ref = f"eval_case_candidate:{candidate['id']}"

    payload = {
        "candidate_ref": candidate_ref,
        "failure_class": classification.failure_class,
        "eval_type": template["eval_type"],
        "run_id": run_id,
    }
    artifact_id = deterministic_id(
        prefix="prl-evl",
        payload=payload,
        namespace="prl::eval",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
        related_trace_refs=[candidate["trace_id"]],
    )
    artifact: dict[str, Any] = {
        "artifact_type": "prl_eval_case",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "candidate_ref": candidate_ref,
        "failure_class": classification.failure_class,
        "eval_type": template["eval_type"],
        "target_artifact": template["target_artifact"],
        "pass_condition": template["pass_condition"],
        "required": True,
        "threshold": template["threshold"],
        "promoted_at": ts,
    }
    _validate(artifact, "prl_eval_case")
    return artifact


def build_generation_record(
    *,
    failure_packet: dict[str, Any],
    candidate: dict[str, Any],
    promoted_eval: Optional[dict[str, Any]],
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Build prl_eval_generation_record tracking the full failure → eval pipeline."""
    ts = _now_iso()
    packet_ref = f"pre_pr_failure_packet:{failure_packet['id']}"

    if promoted_eval is not None:
        promotion_status = "promoted"
        promoted_eval_id: Optional[str] = promoted_eval["id"]
        block_reason = ""
    else:
        block_reason = candidate.get("promotion_blocked_reason", "")
        promotion_status = "requires_human_review" if block_reason else "blocked"
        promoted_eval_id = None

    payload = {
        "packet_ref": packet_ref,
        "candidate_id": candidate["id"],
        "promotion_status": promotion_status,
        "run_id": run_id,
    }
    artifact_id = deterministic_id(
        prefix="prl-gen",
        payload=payload,
        namespace="prl::generation",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
        related_trace_refs=[candidate["trace_id"]],
    )
    artifact: dict[str, Any] = {
        "artifact_type": "prl_eval_generation_record",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "failure_packet_ref": packet_ref,
        "candidate_id": candidate["id"],
        "promotion_status": promotion_status,
        "promotion_blocked_reason": block_reason,
    }
    if promoted_eval_id is not None:
        artifact["promoted_eval_id"] = promoted_eval_id

    _validate(artifact, "prl_eval_generation_record")
    return artifact
