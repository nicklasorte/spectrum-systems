"""Deterministic next-phase governance primitives (CDX-01)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def translate_source_to_artifact(source: dict[str, Any], *, source_system: str = "TRN") -> dict[str, Any]:
    """Translate raw external input into governed translation artifact."""
    source_id = str(source.get("source_id", "unknown"))
    raw_payload = source.get("payload", {})
    classification = str(source.get("classification", "unclassified"))
    simulated = bool(source.get("simulated", False))
    return {
        "artifact_type": "context_source_admission_record",
        "schema_version": "1.0.0",
        "trace_id": f"trace-trn-{_stable_hash(source_id)}",
        "created_at": _utc_now(),
        "provenance": {
            "source_system": source_system,
            "inputs": [source_id],
            "simulated": simulated,
        },
        "record_id": f"trn-{_stable_hash(source_id)}",
        "status": "translated",
        "reason_codes": ["translation_complete"],
        "payload": {
            "source_metadata": {
                "source_id": source_id,
                "classification": classification,
            },
            "normalized_handoff_required": True,
            "raw_payload": raw_payload,
        },
    }


def normalize_text(value: str) -> str:
    """Deterministic normalization for comparison/replay stability."""
    return " ".join(value.strip().lower().split())


def normalize_translation_artifact(artifact: dict[str, Any], *, source_system: str = "NRM") -> dict[str, Any]:
    payload = artifact.get("payload", {})
    raw_payload = payload.get("raw_payload", {})
    canonical = {k: normalize_text(str(v)) for k, v in sorted(raw_payload.items())}
    fingerprint = _stable_hash("|".join(f"{k}={v}" for k, v in canonical.items()))
    return {
        "artifact_type": "context_bundle_record",
        "schema_version": "1.0.0",
        "trace_id": artifact["trace_id"],
        "created_at": _utc_now(),
        "provenance": {
            "source_system": source_system,
            "inputs": [artifact.get("record_id", "missing")],
            "simulated": bool(artifact.get("provenance", {}).get("simulated", False)),
        },
        "record_id": f"ctx-{fingerprint}",
        "status": "normalized",
        "reason_codes": ["deterministic_normalization"],
        "payload": {
            "canonical_payload": canonical,
            "fingerprint": fingerprint,
        },
    }


def build_context_preflight_result(
    *,
    bundle: dict[str, Any],
    required_sources: set[str],
    freshness_ok: bool,
    conflicts: list[str],
) -> dict[str, Any]:
    present_sources = set(bundle.get("provenance", {}).get("inputs", []))
    required_sources_ok = required_sources.issubset(present_sources)
    provenance_complete = bool(bundle.get("trace_id")) and bool(bundle.get("provenance"))
    trust_score = 1.0
    if not freshness_ok:
        trust_score -= 0.4
    if conflicts:
        trust_score -= 0.3
    if not required_sources_ok:
        trust_score -= 0.3
    trust_score = max(0.0, round(trust_score, 3))
    return {
        "artifact_type": "context_preflight_result",
        "schema_version": "1.0.0",
        "trace_id": bundle.get("trace_id", "trace-missing"),
        "created_at": _utc_now(),
        "provenance": {"source_system": "CTX", "inputs": [bundle.get("record_id", "missing")], "simulated": False},
        "record_id": f"ctx-preflight-{_stable_hash(bundle.get('record_id', 'missing'))}",
        "status": "pass" if trust_score >= 0.7 else "block",
        "reason_codes": [] if trust_score >= 0.7 else ["context_insufficient"],
        "payload": {},
        "freshness_ok": freshness_ok,
        "provenance_complete": provenance_complete,
        "required_sources_ok": required_sources_ok,
        "conflicts": conflicts,
        "trust_score": trust_score,
    }


def build_evidence_sufficiency_result(evidence_count: int, threshold: int = 3) -> dict[str, Any]:
    sufficient = evidence_count >= threshold
    return {
        "artifact_type": "evidence_sufficiency_result",
        "schema_version": "1.0.0",
        "trace_id": f"trace-evd-{evidence_count}",
        "created_at": _utc_now(),
        "provenance": {"source_system": "EVD", "inputs": ["evidence_bundle"], "simulated": False},
        "record_id": f"evd-{evidence_count}-{threshold}",
        "status": "sufficient" if sufficient else "insufficient",
        "reason_codes": [] if sufficient else ["materially_insufficient_evidence"],
        "payload": {"evidence_count": evidence_count, "threshold": threshold},
    }


def build_abstention_record(reason_taxonomy: str, trace_id: str) -> dict[str, Any]:
    return {
        "artifact_type": "abstention_record",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "created_at": _utc_now(),
        "provenance": {"source_system": "ABS", "inputs": [trace_id], "simulated": False},
        "record_id": f"abs-{_stable_hash(trace_id + reason_taxonomy)}",
        "status": "abstain",
        "reason_codes": [reason_taxonomy],
        "payload": {},
        "reason_taxonomy": reason_taxonomy,
        "escalation_required": True,
    }


def quarantine_simulated_for_promotion(artifacts: list[dict[str, Any]], *, allow_simulated: bool = False) -> list[str]:
    if allow_simulated:
        return []
    blocked = []
    for artifact in artifacts:
        if artifact.get("provenance", {}).get("simulated", False):
            blocked.append(f"simulated_artifact_blocked:{artifact.get('artifact_type','unknown')}")
    return blocked


def validate_cross_artifact_consistency(*, trace_ids: set[str], policy_active: bool, replay_ok: bool) -> dict[str, Any]:
    checks = [
        {"name": "single_trace", "ok": len(trace_ids) == 1, "reason_code": "ok" if len(trace_ids) == 1 else "trace_mismatch"},
        {"name": "policy_active", "ok": policy_active, "reason_code": "ok" if policy_active else "inactive_policy"},
        {"name": "replay_ok", "ok": replay_ok, "reason_code": "ok" if replay_ok else "replay_missing"},
    ]
    consistent = all(item["ok"] for item in checks)
    return {
        "artifact_type": "cross_artifact_consistency_report",
        "schema_version": "1.0.0",
        "trace_id": next(iter(trace_ids)) if trace_ids else "trace-missing",
        "created_at": _utc_now(),
        "provenance": {"source_system": "CRS", "inputs": ["consistency_inputs"], "simulated": False},
        "record_id": f"crs-{_stable_hash('|'.join(sorted(trace_ids)))}",
        "status": "consistent" if consistent else "inconsistent",
        "reason_codes": [c["reason_code"] for c in checks if not c["ok"]],
        "payload": {},
        "consistent": consistent,
        "checks": checks,
    }


def filter_active_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Active-only retrieval default for retirement/supersession."""
    return [r for r in records if not r.get("retired", False) and not r.get("superseded", False)]


def build_query_index_manifest(reason_index: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "artifact_type": "query_index_manifest",
        "schema_version": "1.0.0",
        "trace_id": "trace-qry-index",
        "created_at": _utc_now(),
        "provenance": {"source_system": "QRY", "inputs": ["artifact_index"], "simulated": False},
        "record_id": "qry-index-v1",
        "status": "ready",
        "reason_codes": [],
        "payload": {"queries": reason_index},
    }


def build_synthesized_trust_signal(
    *,
    context_trust_score: float,
    evidence_sufficient: bool,
    consistency_ok: bool,
    override_rate: float,
) -> dict[str, Any]:
    score = context_trust_score
    if not evidence_sufficient:
        score -= 0.35
    if not consistency_ok:
        score -= 0.35
    score -= min(0.2, override_rate)
    score = max(0.0, min(1.0, round(score, 3)))
    return {
        "artifact_type": "synthesized_trust_signal",
        "schema_version": "1.0.0",
        "trace_id": "trace-syn-001",
        "created_at": _utc_now(),
        "provenance": {"source_system": "SYN", "inputs": ["ctx", "evd", "crs", "hit"], "simulated": False},
        "record_id": "syn-001",
        "status": "freeze" if score < 0.5 else "monitor",
        "reason_codes": ["trust_freeze_triggered"] if score < 0.5 else [],
        "payload": {"override_rate": override_rate},
        "score": score,
        "freeze_triggered": score < 0.5,
    }


@dataclass(frozen=True)
class PromotionEnvelopeInput:
    context_ready: bool
    required_evals_present: bool
    evidence_sufficient: bool
    judgment_present: bool
    consistency_ok: bool
    replay_ok: bool
    active_policy: bool
    control_clearance: bool
    no_simulated_evidence: bool


def evaluate_promotion_trust_envelope(data: PromotionEnvelopeInput) -> dict[str, Any]:
    reasons: list[str] = []
    if not data.context_ready:
        reasons.append("context_incomplete")
    if not data.required_evals_present:
        reasons.append("required_evals_missing")
    if not data.evidence_sufficient:
        reasons.append("evidence_insufficient")
    if not data.judgment_present:
        reasons.append("required_judgment_missing")
    if not data.consistency_ok:
        reasons.append("cross_artifact_inconsistency")
    if not data.replay_ok:
        reasons.append("replay_missing_or_failed")
    if not data.active_policy:
        reasons.append("inactive_or_superseded_policy")
    if not data.control_clearance:
        reasons.append("control_clearance_missing")
    if not data.no_simulated_evidence:
        reasons.append("simulated_evidence_not_allowed")

    return {
        "promotion_allowed": not reasons,
        "blocking_reasons": reasons,
    }
