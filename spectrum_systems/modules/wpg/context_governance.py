from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from spectrum_systems.modules.wpg.common import stable_hash


CRITICAL_COMPONENTS: tuple[str, ...] = (
    "transcript",
    "meeting_minutes",
    "slides",
    "critique_artifacts",
    "prior_wpg_outputs",
    "eval_outputs",
)

SOURCE_CLASSIFICATION: dict[str, str] = {
    "transcript": "real-time",
    "meeting_minutes": "recent",
    "slides": "recent",
    "critique_artifacts": "recent",
    "prior_wpg_outputs": "archival",
    "eval_outputs": "recent",
}

FRESHNESS_MAX_AGE_DAYS: dict[str, int] = {
    "real-time": 1,
    "recent": 14,
    "archival": 365,
}


class ContextGovernanceError(RuntimeError):
    """Fail-closed context governance error."""


@dataclass(frozen=True)
class Contradiction:
    topic: str
    a_ref: str
    b_ref: str
    a_polarity: str
    b_polarity: str



def _utc_now_iso(now: datetime | None = None) -> str:
    candidate = now or datetime.now(timezone.utc)
    return candidate.replace(microsecond=0).isoformat().replace("+00:00", "Z")



def _parse_iso(ts: str) -> datetime:
    cleaned = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)



def _extract_statements(component: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for row in component.get("statements", []) if isinstance(component.get("statements"), list) else []:
        if not isinstance(row, dict):
            continue
        topic = str(row.get("topic") or "").strip().lower()
        polarity = str(row.get("polarity") or "").strip().lower()
        text = str(row.get("text") or "").strip()
        if topic and polarity in {"affirm", "deny"} and text:
            findings.append({"topic": topic, "polarity": polarity, "text": text})
    return findings



def detect_context_contradictions(components: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    by_topic: dict[str, list[tuple[str, str]]] = {}
    for component in components:
        ref = str(component.get("source_ref") or component.get("component_type") or "unknown")
        for st in _extract_statements(component):
            by_topic.setdefault(st["topic"], []).append((ref, st["polarity"]))

    contradictions: list[dict[str, str]] = []
    for topic, rows in sorted(by_topic.items()):
        affirm = [row for row in rows if row[1] == "affirm"]
        deny = [row for row in rows if row[1] == "deny"]
        if not affirm or not deny:
            continue
        a_ref = sorted(affirm, key=lambda r: r[0])[0][0]
        b_ref = sorted(deny, key=lambda r: r[0])[0][0]
        contradictions.append(
            {
                "topic": topic,
                "left_ref": a_ref,
                "right_ref": b_ref,
                "left_polarity": "affirm",
                "right_polarity": "deny",
                "status": "unresolved",
            }
        )
    return contradictions



def enforce_context_freshness(
    components: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_dt = now or datetime.now(timezone.utc)
    stale_sources: list[dict[str, Any]] = []

    for component in components:
        source_type = str(component.get("source_type") or "")
        source_ref = str(component.get("source_ref") or source_type)
        captured_at = str(component.get("captured_at") or "")
        bucket = SOURCE_CLASSIFICATION.get(source_type, "recent")
        max_age_days = FRESHNESS_MAX_AGE_DAYS[bucket]
        try:
            age_days = (now_dt - _parse_iso(captured_at)).total_seconds() / 86400.0
        except Exception:
            stale_sources.append(
                {
                    "source_ref": source_ref,
                    "source_type": source_type,
                    "classification": bucket,
                    "age_days": None,
                    "max_age_days": max_age_days,
                    "reason": "invalid_or_missing_timestamp",
                    "critical": source_type in CRITICAL_COMPONENTS,
                }
            )
            continue

        if age_days > max_age_days:
            stale_sources.append(
                {
                    "source_ref": source_ref,
                    "source_type": source_type,
                    "classification": bucket,
                    "age_days": round(age_days, 3),
                    "max_age_days": max_age_days,
                    "reason": "stale",
                    "critical": source_type in CRITICAL_COMPONENTS,
                }
            )

    critical_stale = [row for row in stale_sources if row.get("critical")]
    action = "FREEZE" if critical_stale else ("BLOCK" if stale_sources else "ALLOW")
    return {
        "freshness_status": "pass" if not stale_sources else "fail",
        "stale_sources": stale_sources,
        "critical_stale_sources": critical_stale,
        "freshness_action": action,
    }



def build_context_bundle_artifact(
    *,
    trace_id: str,
    run_id: str,
    components: Mapping[str, Mapping[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for component_type in CRITICAL_COMPONENTS:
        payload = dict(components.get(component_type, {}))
        source_ref = str(payload.get("source_ref") or f"{component_type}_artifact")
        captured_at = str(payload.get("captured_at") or created_at or _utc_now_iso())
        statements = payload.get("statements") if isinstance(payload.get("statements"), list) else []
        content = payload.get("content", {})
        items.append(
            {
                "component_type": component_type,
                "required": True,
                "source_type": component_type,
                "source_ref": source_ref,
                "captured_at": captured_at,
                "content_hash": stable_hash(content),
                "statements": statements,
                "provenance": {
                    "source_uri": str(payload.get("source_uri") or f"artifact://{source_ref}"),
                    "source_system": str(payload.get("source_system") or "wpg"),
                    "collected_by": str(payload.get("collected_by") or "wpg_context_governance"),
                    "collected_at": captured_at,
                    "attribution": str(payload.get("attribution") or source_ref),
                },
            }
        )

    artifact = {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": f"ctxb-{stable_hash({'trace_id': trace_id, 'run_id': run_id, 'items': items})[:12]}",
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "created_at": created_at or _utc_now_iso(),
        "components": items,
    }
    return artifact



def evaluate_context_admission(
    context_bundle_artifact: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    components = context_bundle_artifact.get("components")
    if not isinstance(components, list):
        components = []

    present_types = {str(item.get("component_type") or "") for item in components if isinstance(item, Mapping)}
    missing = sorted([name for name in CRITICAL_COMPONENTS if name not in present_types])

    blocking_reasons: list[str] = []
    if missing:
        blocking_reasons.extend([f"missing_required_component:{name}" for name in missing])

    provenance_failures = []
    for item in components:
        if not isinstance(item, Mapping):
            continue
        prov = item.get("provenance")
        if not isinstance(prov, Mapping):
            provenance_failures.append(str(item.get("component_type") or "unknown"))
            continue
        required_prov = ("source_uri", "source_system", "collected_by", "collected_at", "attribution")
        if any(not str(prov.get(field) or "").strip() for field in required_prov):
            provenance_failures.append(str(item.get("component_type") or "unknown"))
    if provenance_failures:
        blocking_reasons.extend([f"missing_provenance:{name}" for name in sorted(set(provenance_failures))])

    contradictions = detect_context_contradictions([item for item in components if isinstance(item, Mapping)])
    if contradictions:
        blocking_reasons.append("unresolved_context_contradiction")

    freshness = enforce_context_freshness([item for item in components if isinstance(item, Mapping)], now=now)

    admission_status = "pass"
    enforcement = "ALLOW"
    if blocking_reasons:
        admission_status = "fail"
        enforcement = "BLOCK"
    elif freshness["freshness_action"] == "FREEZE":
        admission_status = "fail"
        enforcement = "FREEZE"
    elif freshness["freshness_action"] == "BLOCK":
        admission_status = "fail"
        enforcement = "BLOCK"

    return {
        "artifact_type": "context_admission_result",
        "schema_version": "1.0.0",
        "admission_id": f"ctxa-{stable_hash({'bundle': context_bundle_artifact.get('context_bundle_id', ''), 'status': admission_status, 'reasons': blocking_reasons, 'freshness': freshness['stale_sources'], 'contradictions': contradictions})[:12]}",
        "context_bundle_id": str(context_bundle_artifact.get("context_bundle_id") or ""),
        "trace": dict(context_bundle_artifact.get("trace") or {}),
        "admission_status": admission_status,
        "enforcement_action": enforcement,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "stale_sources": freshness["stale_sources"],
        "contradictions": contradictions,
        "created_at": _utc_now_iso(now),
        "checks": {
            "completeness": len(missing) == 0,
            "freshness": freshness["freshness_status"] == "pass",
            "contradiction": len(contradictions) == 0,
            "provenance": len(provenance_failures) == 0,
        },
    }



def build_context_redteam_findings(*, trace_id: str) -> dict[str, Any]:
    findings = [
        {"case_id": "ctx-rt-01", "failure_class": "stale_data", "expected_action": "FREEZE"},
        {"case_id": "ctx-rt-02", "failure_class": "missing_sources", "expected_action": "BLOCK"},
        {"case_id": "ctx-rt-03", "failure_class": "conflicting_inputs", "expected_action": "BLOCK"},
        {"case_id": "ctx-rt-04", "failure_class": "prompt_like_injection", "expected_action": "BLOCK"},
    ]
    return {
        "artifact_type": "context_redteam_findings",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "findings": findings,
    }



def evaluate_context_readiness_integration(admission_result: Mapping[str, Any]) -> dict[str, Any]:
    status = str(admission_result.get("admission_status") or "fail")
    return {
        "artifact_type": "context_readiness_integration",
        "schema_version": "1.0.0",
        "admission_status": status,
        "readiness_decision": "BLOCK" if status != "pass" else "ALLOW",
        "blocking_reasons": list(admission_result.get("blocking_reasons") or []),
        "enforcement_action": str(admission_result.get("enforcement_action") or "BLOCK"),
    }


__all__ = [
    "CRITICAL_COMPONENTS",
    "ContextGovernanceError",
    "build_context_bundle_artifact",
    "build_context_redteam_findings",
    "detect_context_contradictions",
    "enforce_context_freshness",
    "evaluate_context_admission",
    "evaluate_context_readiness_integration",
]
