"""MAP bounded mediation/projection hardening (MAP-01..MAP-FX2)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class MAPProjectionError(ValueError):
    """Raised when MAP projection processing must fail closed."""


_ALLOWED_UPSTREAM = {
    "review_projection_bundle_artifact",
    "roadmap_review_projection_artifact",
    "readiness_review_projection_artifact",
}

_FORBIDDEN_ACTION_PREFIXES = (
    "interpret_review",
    "issue_policy",
    "issue_closure",
    "execute_work",
    "enforce_runtime_action",
    "prioritize_program_governance",
)


_REQUIRED_SOURCE_PATHS = (
    "roadmap_projection",
    "control_loop_projection",
    "readiness_projection",
)


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_path(payload: Mapping[str, Any], dotted: str) -> Any:
    node: Any = payload
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def enforce_map_boundary(*, upstream_artifact_type: str, claimed_actions: list[str], emitted_artifact_types: list[str]) -> list[str]:
    fails: list[str] = []
    if upstream_artifact_type not in _ALLOWED_UPSTREAM:
        fails.append(f"invalid_upstream_artifact:{upstream_artifact_type}")
    for action in claimed_actions:
        if action.startswith(_FORBIDDEN_ACTION_PREFIXES):
            fails.append(f"forbidden_owner_overlap:{action}")
    for artifact_type in emitted_artifact_types:
        if artifact_type not in {
            "map_projection_record",
            "map_projection_eval_result",
            "map_projection_readiness_record",
            "map_projection_conflict_record",
            "map_projection_bundle",
            "map_projection_effectiveness_record",
            "map_projection_debt_record",
        }:
            fails.append(f"invalid_downstream_artifact:{artifact_type}")
    return sorted(set(fails))


def build_map_projection_record(*, review_projection_bundle_artifact: Mapping[str, Any], created_at: str, trace_id: str) -> dict[str, Any]:
    if str(review_projection_bundle_artifact.get("artifact_type")) != "review_projection_bundle_artifact":
        raise MAPProjectionError("map_requires_review_projection_bundle_artifact")

    missing_paths = [path for path in _REQUIRED_SOURCE_PATHS if _read_path(review_projection_bundle_artifact, path) is None]
    if missing_paths:
        raise MAPProjectionError(f"required_projection_sections_missing:{','.join(missing_paths)}")

    record = {
        "artifact_type": "map_projection_record",
        "projection_id": f"mpr-{_hash([trace_id, created_at, review_projection_bundle_artifact.get('review_projection_bundle_id')])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": str(review_projection_bundle_artifact.get("source_review_integration_packet_ref") or "lineage:unknown"),
        "source_artifact_ref": f"review_projection_bundle_artifact:{review_projection_bundle_artifact.get('review_projection_bundle_id')}",
        "source_artifact_hash": _hash(review_projection_bundle_artifact),
        "projection_scope": "mediation_projection_only",
        "non_authority_assertions": [
            "map_not_interpretation_authority",
            "map_not_policy_authority",
            "map_not_closure_authority",
            "map_not_execution_authority",
        ],
        "status_markers": {
            "blocker_present": bool(review_projection_bundle_artifact.get("blocker_present")),
            "escalation_present": bool(review_projection_bundle_artifact.get("escalation_present")),
            "highest_priority": str(review_projection_bundle_artifact.get("roadmap_projection", {}).get("highest_priority") or "monitor"),
        },
        "contradiction_markers": sorted(
            {
                str(item.get("source_input_id"))
                for item in review_projection_bundle_artifact.get("control_loop_projection", {}).get("control_queue_items", [])
                if item.get("priority") == "P0" and item.get("severity") == "medium"
            }
        ),
        "projected_payload": {
            "roadmap_projection_ref": review_projection_bundle_artifact.get("roadmap_projection_ref"),
            "control_loop_projection_ref": review_projection_bundle_artifact.get("control_loop_projection_ref"),
            "readiness_projection_ref": review_projection_bundle_artifact.get("readiness_projection_ref"),
            "roadmap_item_count": int(review_projection_bundle_artifact.get("roadmap_projection", {}).get("item_count", 0)),
            "control_queue_count": int(review_projection_bundle_artifact.get("control_loop_projection", {}).get("item_count", 0)),
            "readiness_item_count": int(review_projection_bundle_artifact.get("readiness_projection", {}).get("item_count", 0)),
            "evidence_trace_refs": sorted(
                {
                    str(trace.get("source_path"))
                    for section in (
                        review_projection_bundle_artifact.get("roadmap_projection", {}).get("projected_roadmap_items", []),
                        review_projection_bundle_artifact.get("control_loop_projection", {}).get("control_queue_items", []),
                        review_projection_bundle_artifact.get("readiness_projection", {}).get("readiness_items", []),
                    )
                    for item in section
                    for trace in item.get("trace_refs", [])
                    if trace.get("source_path")
                }
            ),
        },
    }
    validate_artifact(record, "map_projection_record")
    return record


def evaluate_map_projection(*, source_bundle: Mapping[str, Any], projection_record: Mapping[str, Any], expected_required_paths: list[str] | None = None, created_at: str, trace_id: str) -> dict[str, Any]:
    expected_paths = expected_required_paths or list(_REQUIRED_SOURCE_PATHS)
    missing_required_fields = [path for path in expected_paths if _read_path(source_bundle, path) is None]

    source_refs = {
        "roadmap": source_bundle.get("roadmap_projection_ref"),
        "control": source_bundle.get("control_loop_projection_ref"),
        "readiness": source_bundle.get("readiness_projection_ref"),
    }
    projection_payload = projection_record.get("projected_payload", {})
    projected_refs = {
        "roadmap": projection_payload.get("roadmap_projection_ref"),
        "control": projection_payload.get("control_loop_projection_ref"),
        "readiness": projection_payload.get("readiness_projection_ref"),
    }

    checks = {
        "completeness": not missing_required_fields,
        "provenance_retention": bool(projection_record.get("source_artifact_hash")) and bool(projection_payload.get("evidence_trace_refs")),
        "contradiction_visibility": bool(projection_record.get("contradiction_markers") or projection_record.get("status_markers", {}).get("blocker_present")),
        "required_field_preservation": source_refs == projected_refs,
        "formatting_correctness": str(projection_record.get("projection_scope")) == "mediation_projection_only",
        "field_loss_detector": not missing_required_fields,
        "status_washing_detector": projection_record.get("status_markers") == {
            "blocker_present": bool(source_bundle.get("blocker_present")),
            "escalation_present": bool(source_bundle.get("escalation_present")),
            "highest_priority": str(source_bundle.get("roadmap_projection", {}).get("highest_priority") or "monitor"),
        },
        "ril_to_map_integrity": str(source_bundle.get("source_review_integration_packet_ref")) in str(projection_record.get("lineage_ref")),
        "projection_to_governance_integrity": "map_not_policy_authority" in projection_record.get("non_authority_assertions", []),
    }

    fail_reasons = [k for k, ok in checks.items() if not ok]
    if missing_required_fields:
        fail_reasons.append("missing_required_source_fields")

    result = {
        "artifact_type": "map_projection_eval_result",
        "eval_id": f"mpe-{_hash([trace_id, projection_record.get('projection_id'), checks, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "projection_id": str(projection_record.get("projection_id")),
        "evaluation_status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "missing_required_fields": sorted(set(missing_required_fields)),
        "fail_reasons": sorted(set(fail_reasons)),
    }
    validate_artifact(result, "map_projection_eval_result")
    return result


def validate_map_projection_replay(*, prior_input: Mapping[str, Any], replay_input: Mapping[str, Any], prior_projection: Mapping[str, Any], replay_projection: Mapping[str, Any]) -> tuple[bool, list[str]]:
    fails: list[str] = []
    if _hash(prior_input) != _hash(replay_input):
        fails.append("projection_replay_input_drift")
    if _hash(prior_projection) != _hash(replay_projection):
        fails.append("projection_replay_output_drift")
    return not fails, fails


def build_map_projection_readiness(*, eval_result: Mapping[str, Any], evidence_refs: list[str], created_at: str, trace_id: str) -> dict[str, Any]:
    fail_reasons: list[str] = []
    if str(eval_result.get("evaluation_status")) != "pass":
        fail_reasons.append("projection_eval_failed")
    if len([x for x in evidence_refs if str(x).strip()]) < 2:
        fail_reasons.append("projection_evidence_incomplete")

    readiness = {
        "artifact_type": "map_projection_readiness_record",
        "readiness_id": f"mprr-{_hash([trace_id, eval_result.get('eval_id'), fail_reasons, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "projection_eval_ref": f"map_projection_eval_result:{eval_result.get('eval_id')}",
        "readiness_status": "candidate_only" if not fail_reasons else "blocked",
        "non_authority_assertions": [
            "candidate_only",
            "does_not_replace_cde",
            "does_not_replace_tpa",
            "does_not_replace_prg",
            "does_not_replace_rdx",
        ],
        "fail_reasons": sorted(set(fail_reasons)),
    }
    validate_artifact(readiness, "map_projection_readiness_record")
    return readiness


def build_map_projection_conflict_record(*, eval_result: Mapping[str, Any], redteam_findings: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    conflict_codes = sorted({*eval_result.get("fail_reasons", []), *(str(r.get("fixture_id")) for r in redteam_findings)})
    record = {
        "artifact_type": "map_projection_conflict_record",
        "conflict_id": f"mpc-{_hash([trace_id, conflict_codes, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "projection_eval_ref": f"map_projection_eval_result:{eval_result.get('eval_id')}",
        "conflict_codes": conflict_codes,
        "severity": "high" if conflict_codes else "none",
    }
    validate_artifact(record, "map_projection_conflict_record")
    return record


def build_map_projection_debt_record(*, incidents: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    counts = Counter(str(row.get("incident_code") or "unknown") for row in incidents)
    repeated = {k: v for k, v in counts.items() if v >= 2}
    record = {
        "artifact_type": "map_projection_debt_record",
        "debt_id": f"mpd-{_hash([trace_id, repeated, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "debt_items": [
            {"incident_code": code, "recurrence_count": count, "status": "open"}
            for code, count in sorted(repeated.items())
        ],
        "debt_status": "elevated" if repeated else "stable",
    }
    validate_artifact(record, "map_projection_debt_record")
    return record


def build_map_projection_effectiveness(*, outcomes: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    if not outcomes:
        raise MAPProjectionError("projection_effectiveness_outcomes_required")

    usable = sum(1 for row in outcomes if row.get("usability_improved") is True)
    distortion = sum(1 for row in outcomes if row.get("semantic_distortion_detected") is True)
    confusion = sum(1 for row in outcomes if row.get("authority_confusion_detected") is True)
    total = len(outcomes)
    score = round((usable - distortion - confusion) / total, 4)

    record = {
        "artifact_type": "map_projection_effectiveness_record",
        "effectiveness_id": f"mpeff-{_hash([trace_id, score, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "window_size": total,
        "usability_improvement_rate": round(usable / total, 4),
        "semantic_distortion_rate": round(distortion / total, 4),
        "authority_confusion_rate": round(confusion / total, 4),
        "effectiveness_score": score,
        "value_status": "improving" if score >= 0.3 else "degrading",
    }
    validate_artifact(record, "map_projection_effectiveness_record")
    return record


def run_map_boundary_redteam(*, fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in fixtures:
        if row.get("should_fail_closed") and row.get("observed") != "blocked":
            findings.append({"fixture_id": str(row.get("fixture_id")), "class": "boundary_fail_open", "severity": "high"})
    return sorted(findings, key=lambda row: row["fixture_id"])


def run_map_semantic_redteam(*, fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in fixtures:
        if row.get("semantic_risk") and row.get("observed") != "blocked":
            findings.append({"fixture_id": str(row.get("fixture_id")), "class": "semantic_presentation_fail_open", "severity": "high"})
    return sorted(findings, key=lambda row: row["fixture_id"])


def build_map_projection_bundle(*, projection_record: Mapping[str, Any], eval_result: Mapping[str, Any], readiness_record: Mapping[str, Any], conflict_record: Mapping[str, Any], debt_record: Mapping[str, Any], effectiveness_record: Mapping[str, Any], created_at: str, trace_id: str) -> dict[str, Any]:
    bundle = {
        "artifact_type": "map_projection_bundle",
        "bundle_id": f"mpb-{_hash([trace_id, projection_record.get('projection_id'), created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "projection_ref": f"map_projection_record:{projection_record.get('projection_id')}",
        "eval_ref": f"map_projection_eval_result:{eval_result.get('eval_id')}",
        "readiness_ref": f"map_projection_readiness_record:{readiness_record.get('readiness_id')}",
        "conflict_ref": f"map_projection_conflict_record:{conflict_record.get('conflict_id')}",
        "debt_ref": f"map_projection_debt_record:{debt_record.get('debt_id')}",
        "effectiveness_ref": f"map_projection_effectiveness_record:{effectiveness_record.get('effectiveness_id')}",
        "non_authority_assertions": projection_record.get("non_authority_assertions", []),
    }
    validate_artifact(bundle, "map_projection_bundle")
    return bundle
