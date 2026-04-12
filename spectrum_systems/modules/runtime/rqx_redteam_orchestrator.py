"""RQX bounded red-team orchestration foundation (RQX-01..RQX-03)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from spectrum_systems.contracts import validate_artifact


class RQXRedTeamError(ValueError):
    """Raised when RQX orchestration fails closed."""


_OWNER_BY_CLASS = {
    "interpretation": "RIL",
    "repair_planning": "FRE",
    "decision_quality": "CDE",
    "enforcement_mismatch": "SEL",
    "execution_trace": "PQX",
    "trust_policy": "TPA",
}


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RQXRedTeamError(f"{field} must be a non-empty string")
    return value.strip()


def _ensure_list(value: Any, *, field: str, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise RQXRedTeamError(f"{field} must be a list")
    cleaned = sorted({str(item).strip() for item in value if str(item).strip()})
    if len(cleaned) < min_items:
        raise RQXRedTeamError(f"{field} must include at least {min_items} values")
    return cleaned


def route_finding_owner(*, finding_record: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(finding_record), "redteam_finding_record")
    finding_class = str(finding_record.get("finding_class", "")).strip()
    owner = _OWNER_BY_CLASS.get(finding_class)
    if owner is None:
        raise RQXRedTeamError(f"finding_class '{finding_class}' has no canonical owner mapping")

    routing = {
        "owner": owner,
        "routing_reason": f"class:{finding_class}",
        "routing_ref": f"redteam_finding_record:{finding_record['finding_id']}",
    }
    return routing


def build_fix_slice_request(*, finding_record: Mapping[str, Any], round_config: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(finding_record), "redteam_finding_record")
    validate_artifact(dict(round_config), "redteam_round_config")
    routing = route_finding_owner(finding_record=finding_record)

    request = {
        "artifact_type": "redteam_fix_slice_request",
        "schema_version": "1.0.0",
        "request_id": f"rqx-fix-{_digest([finding_record['finding_id'], routing['owner']])[:16]}",
        "trace_id": finding_record["trace_id"],
        "finding_ref": f"redteam_finding_record:{finding_record['finding_id']}",
        "owner": routing["owner"],
        "owner_routing_reason": routing["routing_reason"],
        "bounded_scope": _require_text(finding_record.get("bounded_scope"), field="bounded_scope"),
        "required_proof_types": ["eval_case", "regression_test", "hardened_contract_path"],
        "deadline_ref": _require_text(round_config.get("deadline_ref"), field="deadline_ref"),
        "non_authority_assertions": [
            "rqx_orchestration_only",
            "rqx_must_not_reinterpret_semantics",
            "rqx_must_not_enforce_runtime_action",
        ],
    }
    validate_artifact(request, "redteam_fix_slice_request")
    return request


def verify_closure_proof(*, closure_request: Mapping[str, Any], finding_record: Mapping[str, Any]) -> dict[str, Any]:
    validate_artifact(dict(closure_request), "redteam_closure_request")
    validate_artifact(dict(finding_record), "redteam_finding_record")

    reasons: list[str] = []
    if closure_request.get("finding_ref") != f"redteam_finding_record:{finding_record['finding_id']}":
        reasons.append("finding_linkage_missing")

    proofs = closure_request.get("proof_refs", [])
    if not any(str(ref).startswith("eval_case:") for ref in proofs):
        reasons.append("missing_eval_case_proof")
    if not any(str(ref).startswith("regression_test:") for ref in proofs):
        reasons.append("missing_regression_test_proof")
    if not any(str(ref).startswith("hardened_contract_path:") for ref in proofs):
        reasons.append("missing_hardening_proof")

    status = "pass" if not reasons else "fail"
    return {
        "status": status,
        "blocking_reasons": sorted(reasons),
    }


def run_redteam_cycle(*, review_request: Mapping[str, Any], round_config: Mapping[str, Any], findings: Sequence[Mapping[str, Any]], exploit_bundle: Mapping[str, Any], closure_requests: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validate_artifact(dict(review_request), "redteam_review_request")
    validate_artifact(dict(round_config), "redteam_round_config")
    validate_artifact(dict(exploit_bundle), "redteam_exploit_bundle")

    if review_request.get("trace_id") != round_config.get("trace_id"):
        raise RQXRedTeamError("trace mismatch between review request and round config")

    fix_requests: list[dict[str, Any]] = []
    operator_handoffs: list[dict[str, Any]] = []

    finding_map: dict[str, Mapping[str, Any]] = {}
    for finding in findings:
        validate_artifact(dict(finding), "redteam_finding_record")
        if finding.get("trace_id") != review_request.get("trace_id"):
            raise RQXRedTeamError("finding trace mismatch")
        finding_id = str(finding["finding_id"])
        finding_map[finding_id] = finding
        try:
            fix_requests.append(build_fix_slice_request(finding_record=finding, round_config=round_config))
        except RQXRedTeamError:
            operator_handoffs.append(
                {
                    "finding_ref": f"redteam_finding_record:{finding_id}",
                    "handoff_reason": "owner_unmappable",
                    "operator_action": "manual_owner_assignment_required",
                }
            )

    closure_results: list[dict[str, Any]] = []
    for closure in closure_requests:
        validate_artifact(dict(closure), "redteam_closure_request")
        finding_ref = str(closure.get("finding_ref", ""))
        finding_id = finding_ref.split(":", 1)[1] if ":" in finding_ref else ""
        finding = finding_map.get(finding_id)
        if finding is None:
            raise RQXRedTeamError("closure request linked to unknown finding")
        proof = verify_closure_proof(closure_request=closure, finding_record=finding)
        closure_results.append(
            {
                "closure_request_id": closure["closure_request_id"],
                "finding_ref": finding_ref,
                "status": proof["status"],
                "blocking_reasons": proof["blocking_reasons"],
            }
        )

    return {
        "status": "completed",
        "trace_id": review_request["trace_id"],
        "review_request_ref": f"redteam_review_request:{review_request['request_id']}",
        "round_config_ref": f"redteam_round_config:{round_config['round_id']}",
        "exploit_bundle_ref": f"redteam_exploit_bundle:{exploit_bundle['bundle_id']}",
        "finding_count": len(findings),
        "fix_slice_requests": fix_requests,
        "operator_handoffs": operator_handoffs,
        "closure_results": closure_results,
    }


def build_redteam_finding_record(*, trace_id: str, finding_class: str, finding_statement: str, exploit_refs: Sequence[str], bounded_scope: str) -> dict[str, Any]:
    if finding_class not in _OWNER_BY_CLASS:
        raise RQXRedTeamError("unsupported finding_class")
    record = {
        "artifact_type": "redteam_finding_record",
        "schema_version": "1.0.0",
        "finding_id": f"rqx-find-{_digest([trace_id, finding_class, finding_statement])[:16]}",
        "trace_id": _require_text(trace_id, field="trace_id"),
        "finding_class": finding_class,
        "finding_statement": _require_text(finding_statement, field="finding_statement"),
        "exploit_refs": _ensure_list(list(exploit_refs), field="exploit_refs"),
        "bounded_scope": _require_text(bounded_scope, field="bounded_scope"),
        "severity": "high",
    }
    validate_artifact(record, "redteam_finding_record")
    return record
