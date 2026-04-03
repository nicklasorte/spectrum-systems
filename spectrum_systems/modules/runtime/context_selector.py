"""Deterministic governed context selection/ranking/lifecycle for CTX-001..CTX-005."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id

CONTEXT_BUNDLE_V2_SCHEMA = "context_bundle_v2"
CONTEXT_BUNDLE_V2_VERSION = "1.0.0"

RISK_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}


class ContextSelectorError(RuntimeError):
    """Fail-closed context selector error."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_serialize_context_bundle(bundle: Mapping[str, Any]) -> str:
    """Canonical compact deterministic serialization for replay/diff safety."""
    return _canonical(bundle)


def _parse_dt(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _artifact_ref(artifact: Mapping[str, Any]) -> str:
    artifact_type = str(artifact.get("artifact_type") or "artifact")
    artifact_id = str(
        artifact.get("artifact_id")
        or artifact.get("id")
        or artifact.get("review_id")
        or artifact.get("eval_id")
        or artifact.get("build_report_id")
        or artifact.get("handoff_id")
        or "unknown"
    )
    return f"{artifact_type}:{artifact_id}"


def _scope_match(artifact: Mapping[str, Any], target_scope: Mapping[str, str]) -> bool:
    scope_id = target_scope["scope_id"]
    direct = [
        artifact.get("scope_id"),
        artifact.get("slice_id"),
        artifact.get("batch_id"),
        artifact.get("program_id"),
    ]
    nested = artifact.get("target_scope")
    if isinstance(nested, Mapping):
        direct.extend([nested.get("scope_id"), nested.get("slice_id"), nested.get("batch_id"), nested.get("program_id")])
    return any(str(value or "") == scope_id for value in direct)


def _overlap_count(artifact: Mapping[str, Any], touched_modules: Sequence[str]) -> int:
    touched = set(str(v) for v in touched_modules)
    candidates: List[str] = []
    for key in ("touched_module_refs", "module_refs", "files", "touched_files"):
        raw = artifact.get(key)
        if isinstance(raw, list):
            candidates.extend(str(item) for item in raw)
    return len(touched.intersection(candidates))


def _risk_severity(artifact: Mapping[str, Any], active_risks: Sequence[Mapping[str, Any]]) -> int:
    ref = _artifact_ref(artifact)
    level = 0
    for risk in active_risks:
        risk_refs = risk.get("related_refs")
        if isinstance(risk_refs, list) and ref not in [str(v) for v in risk_refs]:
            continue
        severity = str(risk.get("severity") or "none").lower()
        level = max(level, RISK_SEVERITY_ORDER.get(severity, 0))
    return level


def _is_closed_failure(artifact: Mapping[str, Any]) -> bool:
    if str(artifact.get("artifact_type") or "") != "failure_eval_case":
        return False
    status = str(artifact.get("status") or "").lower()
    return status in {"closed", "resolved", "done"}


def _is_expired(artifact: Mapping[str, Any], now: datetime, stale_after_days: int, active_risks: Sequence[Mapping[str, Any]]) -> bool:
    ref = _artifact_ref(artifact)
    for risk in active_risks:
        related = risk.get("related_refs")
        if isinstance(related, list) and ref in [str(v) for v in related]:
            return False
    created = _parse_dt(artifact.get("created_at"))
    return created < now - timedelta(days=stale_after_days)


def _dedupe_superseded(artifacts: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for artifact in artifacts:
        key = f"{artifact.get('artifact_type')}::{artifact.get('subject_id') or artifact.get('scope_id') or _artifact_ref(artifact)}"
        existing = latest.get(key)
        candidate = dict(artifact)
        if existing is None or _parse_dt(candidate.get("created_at")) > _parse_dt(existing.get("created_at")):
            latest[key] = candidate
    return sorted(latest.values(), key=lambda item: (_parse_dt(item.get("created_at")), _artifact_ref(item)), reverse=True)


def _validate_contract(bundle: Mapping[str, Any]) -> None:
    schema = load_schema(CONTEXT_BUNDLE_V2_SCHEMA)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(dict(bundle))
    except ValidationError as exc:
        raise ContextSelectorError(f"context_bundle_v2 validation failed: {exc.message}") from exc


def _rank_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    target_scope: Mapping[str, str],
    touched_modules: Sequence[str],
    active_risks: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    def sort_key(artifact: Mapping[str, Any]) -> Tuple[int, int, int, int, int, str]:
        scope = 1 if _scope_match(artifact, target_scope) else 0
        locality = _overlap_count(artifact, touched_modules)
        risk = _risk_severity(artifact, active_risks)
        review_eval = 1 if str(artifact.get("artifact_type") or "") in {"review_artifact", "eval_result", "failure_eval_case"} else 0
        closed_penalty = 0 if not _is_closed_failure(artifact) else -1
        recency = int(_parse_dt(artifact.get("created_at")).timestamp())
        return (scope, locality, risk + closed_penalty, review_eval, recency, _artifact_ref(artifact))

    ranked = sorted((dict(a) for a in artifacts), key=sort_key, reverse=True)
    return ranked


def build_context_bundle(
    *,
    roadmap_state: Mapping[str, Any],
    target_scope: Mapping[str, str],
    review_artifacts: Sequence[Mapping[str, Any]],
    eval_artifacts: Sequence[Mapping[str, Any]],
    failure_artifacts: Sequence[Mapping[str, Any]],
    build_report_artifacts: Sequence[Mapping[str, Any]],
    handoff_artifacts: Sequence[Mapping[str, Any]],
    pqx_execution_artifacts: Sequence[Mapping[str, Any]],
    touched_module_refs: Sequence[str],
    active_risks: Sequence[Mapping[str, Any]],
    intent_refs: Sequence[str],
    trace_id: str,
    stale_after_days: int = 14,
    max_selected_artifacts: int = 16,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Build deterministic governed context bundle; fail closed on missing required inputs."""

    required_inputs = {
        "roadmap_state": roadmap_state,
        "target_scope": target_scope,
        "build_report_artifacts": build_report_artifacts,
        "handoff_artifacts": handoff_artifacts,
        "touched_module_refs": touched_module_refs,
        "trace_id": trace_id,
    }
    missing = [name for name, value in required_inputs.items() if value in (None, "") or value == []]
    if missing:
        raise ContextSelectorError(f"missing required inputs: {', '.join(sorted(missing))}")

    if target_scope.get("scope_type") not in {"slice_id", "batch_id", "program_id"}:
        raise ContextSelectorError("target_scope.scope_type must be one of slice_id|batch_id|program_id")

    moment = now or datetime.now(timezone.utc)

    candidates: List[Mapping[str, Any]] = []
    for artifact in [
        *review_artifacts,
        *eval_artifacts,
        *failure_artifacts,
        *build_report_artifacts,
        *handoff_artifacts,
        *pqx_execution_artifacts,
    ]:
        if _scope_match(artifact, target_scope) or _overlap_count(artifact, touched_module_refs) > 0:
            if not _is_expired(artifact, moment, stale_after_days, active_risks):
                candidates.append(artifact)

    deduped = _dedupe_superseded(candidates)
    ranked = _rank_artifacts(
        deduped,
        target_scope=target_scope,
        touched_modules=touched_module_refs,
        active_risks=active_risks,
    )
    selected = ranked[:max_selected_artifacts]

    review_refs = sorted(_artifact_ref(a) for a in selected if str(a.get("artifact_type") or "") == "review_artifact")
    eval_refs = sorted(_artifact_ref(a) for a in selected if str(a.get("artifact_type") or "") in {"eval_result", "failure_eval_case"})
    risk_refs = sorted(
        {
            str(risk.get("risk_ref") or f"risk_register:{risk.get('risk_id') or 'unknown'}")
            for risk in active_risks
            if str(risk.get("status") or "active").lower() != "resolved"
        }
    )
    build_refs = sorted(_artifact_ref(a) for a in selected if str(a.get("artifact_type") or "") == "build_report")
    handoff_refs = sorted(_artifact_ref(a) for a in selected if str(a.get("artifact_type") or "") == "next_slice_handoff")
    selected_refs = [_artifact_ref(a) for a in selected]

    source_refs = sorted(
        set(
            selected_refs
            + review_refs
            + eval_refs
            + build_refs
            + handoff_refs
            + risk_refs
            + [str(ref) for ref in roadmap_state.get("source_refs", [])]
        )
    )

    bundle_identity = {
        "target_scope": dict(target_scope),
        "selected_refs": selected_refs,
        "trace_id": trace_id,
        "touched_modules": list(touched_module_refs),
        "intent_refs": sorted(str(i) for i in intent_refs),
    }
    bundle: Dict[str, Any] = {
        "artifact_type": "context_bundle_v2",
        "schema_version": CONTEXT_BUNDLE_V2_VERSION,
        "context_id": deterministic_id(prefix="ctx2", namespace="context_bundle_v2", payload=bundle_identity),
        "target_scope": {
            "scope_type": str(target_scope["scope_type"]),
            "scope_id": str(target_scope["scope_id"]),
        },
        "selected_artifact_refs": selected_refs,
        "review_signal_refs": review_refs,
        "eval_signal_refs": eval_refs,
        "active_risk_refs": risk_refs,
        "recent_build_report_refs": build_refs,
        "handoff_refs": handoff_refs,
        "touched_module_refs": sorted(str(v) for v in touched_module_refs),
        "intent_refs": sorted(str(v) for v in intent_refs),
        "priority_metadata": {
            "ranking_policy": "deterministic_context_ranking",
            "ranking_policy_version": "1.0.0",
            "lifecycle_policy": "expiry_and_active_risk_persistence",
            "max_selected_artifacts": int(max_selected_artifacts),
            "deterministic_ordering": True,
            "canonical_serialization": "json_sort_keys_compact_utf8",
        },
        "created_at": moment.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "trace_id": trace_id,
        "source_refs": source_refs,
    }
    _validate_contract(bundle)
    return bundle


__all__ = [
    "ContextSelectorError",
    "build_context_bundle",
    "canonical_serialize_context_bundle",
]
