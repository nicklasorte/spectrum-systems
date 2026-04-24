"""Deterministic drift, lifecycle, and roadmap steering signal builders."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.contracts import validate_artifact

_DRIFT_ORDER = (
    "artifact_drift",
    "eval_drift",
    "control_drift",
    "replay_trace_drift",
    "judgment_drift",
    "governance_drift",
    "roadmap_drift",
)

_SEVERITY_RANK = {"none": 0, "warning": 1, "freeze_candidate": 2, "block": 3}


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:12].upper()}"


def _as_reason_codes(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return sorted({str(value).strip() for value in (values or []) if str(value).strip()})


def _severity_from_score(score: float) -> str:
    if score >= 0.9:
        return "block"
    if score >= 0.6:
        return "freeze_candidate"
    if score > 0:
        return "warning"
    return "none"


def build_drift_detection_record(*, findings_input: list[dict[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for item in findings_input:
        drift_type = str(item.get("drift_type") or "").strip()
        if drift_type not in _DRIFT_ORDER:
            raise ValueError(f"unsupported drift_type: {drift_type}")
        score = float(item.get("severity_score", 0.0))
        severity = _severity_from_score(score)
        findings.append(
            {
                "drift_type": drift_type,
                "severity": severity,
                "affected_component": str(item.get("affected_component") or drift_type),
                "violated_invariant": str(item.get("violated_invariant") or "determinism_required"),
                "reason_codes": _as_reason_codes(item.get("reason_codes") or [f"{drift_type}:{severity}"]),
                "required_action": str(item.get("required_action") or "remediate"),
                "created_at": created_at,
                "trace_id": trace_id,
            }
        )

    findings.sort(key=lambda row: (_SEVERITY_RANK[row["severity"]] * -1, _DRIFT_ORDER.index(row["drift_type"]), row["affected_component"]))
    severity_summary = {key: 0 for key in ("none", "warning", "freeze_candidate", "block")}
    for finding in findings:
        severity_summary[finding["severity"]] += 1

    payload = {
        "drift_detection_id": _stable_id("DDR", {"created_at": created_at, "trace_id": trace_id, "findings": findings}),
        "schema_version": "1.0.0",
        "findings": findings,
        "severity_summary": severity_summary,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(payload, "drift_detection_record")
    return payload


def build_artifact_lifecycle_status_record(
    *,
    artifact_id: str,
    artifact_type: str,
    lifecycle_state: str,
    stale_days: int,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    trust_penalty = 0.0
    retrieval_weight = 1.0
    warnings: list[str] = []
    if lifecycle_state == "superseded":
        retrieval_weight = 0.5
        warnings.append("superseded_artifact_should_not_dominate")
    elif lifecycle_state == "stale":
        retrieval_weight = 0.2
        trust_penalty = 0.3
        warnings.extend(["stale_artifact_retrieval_downgrade", "stale_artifact_reduces_trust_posture"])
    elif lifecycle_state == "revoked":
        retrieval_weight = 0.0
        trust_penalty = 1.0
        warnings.append("revoked_artifact_must_not_be_used")

    if lifecycle_state == "stale" and artifact_type == "policy":
        warnings.append("stale_policy_triggers_freeze_warning")

    payload = {
        "lifecycle_status_id": _stable_id("ALS", {"artifact_id": artifact_id, "created_at": created_at, "trace_id": trace_id}),
        "schema_version": "1.0.0",
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "lifecycle_state": lifecycle_state,
        "stale_days": int(stale_days),
        "retrieval_weight": retrieval_weight,
        "trust_penalty": trust_penalty,
        "warnings": sorted(set(warnings)),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(payload, "artifact_lifecycle_status_record")
    return payload


def build_roadmap_signal_bundle(
    *,
    roadmap_id: str,
    drift_detection_record: dict[str, Any],
    override_hotspots: list[str],
    missing_eval_coverage: list[str],
    replay_mismatches: list[str],
    judgment_conflicts: list[str],
    budget_burn_rate: float,
    trust_posture_snapshot_ref: str,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    severity_summary = dict(drift_detection_record.get("severity_summary") or {})
    block_reasons = sorted({*override_hotspots[:3], *replay_mismatches[:3], *judgment_conflicts[:3]})

    highest_risk_subsystems: list[str] = []
    for finding in drift_detection_record.get("findings", []):
        if isinstance(finding, dict) and finding.get("severity") in {"freeze_candidate", "block"}:
            highest_risk_subsystems.append(str(finding.get("affected_component") or "unknown"))

    adjustments: list[dict[str, Any]] = []
    if severity_summary.get("block", 0) > 0:
        adjustments.append({"priority_class": "hardening", "reason": "blocking_drift_detected", "weight": 100})
    if severity_summary.get("freeze_candidate", 0) > 0:
        adjustments.append({"priority_class": "hardening", "reason": "freeze_candidate_drift", "weight": 80})
    if override_hotspots:
        adjustments.append({"priority_class": "governance", "reason": "override_hotspots", "weight": 70})
    if missing_eval_coverage:
        adjustments.append({"priority_class": "eval_coverage", "reason": "missing_eval_coverage", "weight": 60})
    if replay_mismatches:
        adjustments.append({"priority_class": "replay_hardening", "reason": "replay_mismatch", "weight": 55})
    if judgment_conflicts:
        adjustments.append({"priority_class": "ltv_followup", "reason": "judgment_conflict", "weight": 50})
    if budget_burn_rate > 0.8:
        adjustments.append({"priority_class": "budget_stabilization", "reason": "budget_burn_high", "weight": 45})

    payload = {
        "signal_bundle_id": _stable_id("RSB", {"roadmap_id": roadmap_id, "created_at": created_at, "trace_id": trace_id, "summary": severity_summary}),
        "schema_version": "1.0.0",
        "roadmap_id": roadmap_id,
        "drift_detection_ref": f"drift_detection_record:{drift_detection_record['drift_detection_id']}",
        "top_block_reasons": block_reasons,
        "highest_risk_subsystems": sorted(set(highest_risk_subsystems)),
        "missing_eval_coverage": sorted(set(missing_eval_coverage)),
        "override_hotspots": sorted(set(override_hotspots)),
        "drift_severity_summary": {
            "none": int(severity_summary.get("none", 0)),
            "warning": int(severity_summary.get("warning", 0)),
            "freeze_candidate": int(severity_summary.get("freeze_candidate", 0)),
            "block": int(severity_summary.get("block", 0)),
        },
        "replay_mismatch_refs": sorted(set(replay_mismatches)),
        "judgment_conflict_refs": sorted(set(judgment_conflicts)),
        "budget_burn_rate": float(budget_burn_rate),
        "trust_posture_snapshot_ref": trust_posture_snapshot_ref,
        "recommended_priority_adjustments": sorted(adjustments, key=lambda row: (-int(row["weight"]), row["priority_class"])),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    validate_artifact(payload, "roadmap_signal_bundle")
    return payload


def steering_enforcement(bundle: dict[str, Any]) -> tuple[str | None, list[str]]:
    summary = bundle.get("drift_severity_summary")
    if not isinstance(summary, dict):
        raise ValueError("roadmap_signal_bundle.drift_severity_summary missing")
    block = int(summary.get("block", 0))
    freeze = int(summary.get("freeze_candidate", 0))
    if block > 0:
        return "block", sorted(set(bundle.get("top_block_reasons") or ["blocking_drift_detected"]))
    if freeze > 0:
        return "freeze", sorted(set(bundle.get("top_block_reasons") or ["freeze_candidate_drift_detected"]))
    return None, []


def select_priority_batch(eligible_batch_ids: list[str], bundle: dict[str, Any]) -> str:
    if not eligible_batch_ids:
        raise ValueError("eligible_batch_ids must be non-empty")

    by_weight: dict[str, int] = {batch_id: 0 for batch_id in eligible_batch_ids}
    for row in bundle.get("recommended_priority_adjustments", []):
        if not isinstance(row, dict):
            continue
        target_batch_id = row.get("target_batch_id")
        if isinstance(target_batch_id, str) and target_batch_id in by_weight:
            by_weight[target_batch_id] += int(row.get("weight", 0))

    return sorted(eligible_batch_ids, key=lambda bid: (-by_weight[bid], eligible_batch_ids.index(bid)))[0]


_CANONICAL_LOOP_LEGS = frozenset({
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "OBS", "SLO",
})

_NON_DRIFT_SEVERITY = frozenset({"none", ""})


def get_active_drift_legs(bundle: dict[str, Any] | None) -> list[str]:
    """Return the canonical loop legs currently carrying active drift.

    Consumed by the RGE Loop Contribution Checker. A leg is considered 'in
    drift' when at least one finding with severity above 'none' names the
    leg in its affected_component string. Returns a sorted, de-duplicated
    list of leg codes.
    """
    if not bundle:
        return []
    findings: list[Any] = []
    for key in ("drift_findings", "findings", "drift_findings_input"):
        value = bundle.get(key)
        if isinstance(value, list):
            findings.extend(value)
    legs: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity", "")).lower()
        if severity in _NON_DRIFT_SEVERITY:
            continue
        component = str(finding.get("affected_component", "")).upper()
        for leg in _CANONICAL_LOOP_LEGS:
            if leg in component:
                legs.add(leg)
    return sorted(legs)
