"""JDX judgment governance runtime (non-authoritative)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class JDXRuntimeError(ValueError):
    pass


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_judgment_record(*, evidence_refs: list[str], policy_ref: str, rationale: str, contradiction_refs: list[str], uncertainty_flags: list[str], lineage_ref: str, created_at: str, artifact_id: str = "jdx-judgment-001") -> dict[str, Any]:
    if not evidence_refs:
        raise JDXRuntimeError("missing_evidence_refs")
    if not policy_ref:
        raise JDXRuntimeError("missing_policy_ref")
    record = {
        "artifact_type": "jdx_judgment_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "evidence_refs": sorted(evidence_refs),
        "policy_ref": policy_ref,
        "rationale": rationale,
        "uncertainty_flags": sorted(set(uncertainty_flags)),
        "contradiction_refs": sorted(set(contradiction_refs)),
        "lineage_ref": lineage_ref,
        "non_authoritative": True,
    }
    validate_artifact(record, "jdx_judgment_record")
    return record


def evaluate_judgment(*, judgment_record: Mapping[str, Any], policy_rules: list[str], created_at: str) -> dict[str, Any]:
    missing = [rule for rule in policy_rules if rule == "require_evidence" and not judgment_record.get("evidence_refs")]
    contradiction_suppressed = bool(judgment_record.get("contradiction_refs") == [] and "require_contradictions" in policy_rules)
    reasons = []
    if missing:
        reasons.append("missing_required_evidence")
    if contradiction_suppressed:
        reasons.append("contradiction_suppressed")
    status = "pass" if not reasons else "fail"
    result = {
        "artifact_type": "jdx_judgment_eval_result",
        "artifact_id": f"jdx-eval-{judgment_record.get('artifact_id', 'unknown')}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "judgment_ref": f"jdx_judgment_record:{judgment_record.get('artifact_id')}",
        "status": status,
        "reason_codes": reasons or ["coverage_ok"],
        "coverage_score": 1.0 if not reasons else 0.0,
        "replay_consistent": True,
        "policy_aligned": not reasons,
    }
    validate_artifact(result, "jdx_judgment_eval_result")
    return result


def build_application_record(*, judgment_record: Mapping[str, Any], policy_ref: str, precedent_refs: list[str], created_at: str) -> dict[str, Any]:
    if not policy_ref:
        raise JDXRuntimeError("missing_policy_ref")
    if not judgment_record.get("evidence_refs"):
        raise JDXRuntimeError("missing_evidence_refs")
    rec = {
        "artifact_type": "jdx_judgment_application_record",
        "artifact_id": f"jdx-application-{judgment_record.get('artifact_id', 'unknown')}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "judgment_ref": f"jdx_judgment_record:{judgment_record.get('artifact_id')}",
        "policy_ref": policy_ref,
        "precedent_refs": sorted(precedent_refs),
        "evidence_refs": sorted(judgment_record["evidence_refs"]),
        "non_authority_assertion": "candidate_only_lineage_record",
    }
    validate_artifact(rec, "jdx_judgment_application_record")
    return rec


def run_jdx_redteam(*, judgment_record: Mapping[str, Any], replay_payload: Mapping[str, Any]) -> dict[str, Any]:
    findings = []
    if not judgment_record.get("contradiction_refs"):
        findings.append("contradiction_suppression")
    if not judgment_record.get("non_authoritative", False):
        findings.append("shadow_authority_framing")
    if _fingerprint(judgment_record) != _fingerprint(replay_payload):
        findings.append("non_replayable_judgment")
    return {"status": "fail" if findings else "pass", "findings": sorted(findings)}
