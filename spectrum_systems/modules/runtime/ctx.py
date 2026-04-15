"""CTX — Context eXchange."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_context_recipe(*, recipe: dict[str, Any]) -> dict[str, Any]:
    required = ("recipe_id", "artifact_family", "strict_mode", "required_sources")
    missing = [field for field in required if field not in recipe]
    if missing:
        raise ValueError(f"missing context recipe fields: {', '.join(sorted(missing))}")
    return dict(recipe)


def gather_context_candidates(*, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(item) for item in candidates), key=lambda item: str(item.get("source_id", "")))


def gather_sources(*, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alias preserved for OSX-03 phase contract wording."""
    return gather_context_candidates(candidates=candidates)


def enforce_context_admission(*, recipe: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    trusted_sources = set(recipe.get("required_sources", []))
    strict_mode = bool(recipe.get("strict_mode", True))
    admitted: list[dict[str, Any]] = []
    reasons: list[str] = []
    for candidate in candidates:
        source_id = str(candidate.get("source_id") or "")
        if source_id not in trusted_sources:
            reasons.append(f"source_not_admitted:{source_id}")
            continue
        if strict_mode and not candidate.get("trace_ref"):
            reasons.append(f"missing_trace_ref:{source_id}")
            continue
        admitted.append(candidate)
    return admitted, sorted(set(reasons))


def rank_context_candidates(*, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (
            int(item.get("priority", 1000)),
            str(item.get("source_id", "")),
            str(item.get("content_hash", "")),
        ),
    )


def detect_context_conflicts(*, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_key: dict[str, str] = {}
    conflicts: list[dict[str, str]] = []
    for candidate in candidates:
        policy_key = str(candidate.get("policy_key") or "")
        policy_value = str(candidate.get("policy_value") or "")
        if not policy_key:
            continue
        previous = by_key.get(policy_key)
        if previous is not None and previous != policy_value:
            conflicts.append({"policy_key": policy_key, "existing_value": previous, "new_value": policy_value})
        by_key[policy_key] = policy_value
    return {
        "artifact_type": "context_conflict_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
        "conflict_codes": [f"context_conflict:{item['policy_key']}" for item in conflicts],
    }


def assemble_context_bundle(*, run_id: str, trace_id: str, recipe: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = rank_context_candidates(candidates=candidates)
    serialized = "|".join(str(item.get("content_hash") or "") for item in ordered)
    manifest_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "artifact_type": "context_bundle",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "bundle_id": f"CTXB-{run_id}-{trace_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "recipe_id": recipe["recipe_id"],
        "artifact_family": recipe["artifact_family"],
        "entries": ordered,
        "manifest_hash": manifest_hash,
    }


def emit_context_manifest(*, bundle: dict[str, Any], policy_version: str) -> dict[str, Any]:
    return {
        "artifact_type": "context_manifest",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "manifest_id": f"CTXM-{bundle['run_id']}-{bundle['trace_id']}",
        "run_id": bundle["run_id"],
        "trace_id": bundle["trace_id"],
        "bundle_ref": f"context_bundle:{bundle['bundle_id']}",
        "manifest_hash": bundle["manifest_hash"],
        "policy_version": policy_version,
        "created_at": _iso_now(),
    }


def run_context_preflight(*, recipe: dict[str, Any], admitted_candidates: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    required = set(recipe.get("required_sources", []))
    provided = {str(item.get("source_id")) for item in admitted_candidates}
    missing = sorted(required - provided)
    if missing:
        reasons.extend([f"missing_required_source:{item}" for item in missing])
    for item in admitted_candidates:
        if bool(recipe.get("strict_mode", True)) and not item.get("fresh", False):
            reasons.append(f"stale_context:{item.get('source_id')}")
        expires_at = item.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            except ValueError:
                reasons.append(f"invalid_expires_at:{item.get('source_id')}")
                continue
            if expiry <= datetime.now(timezone.utc) + timedelta(seconds=0):
                reasons.append(f"expired_context:{item.get('source_id')}")
        if bool(recipe.get("strict_mode", True)) and not item.get("content_hash"):
            reasons.append(f"missing_content_hash:{item.get('source_id')}")
    return len(reasons) == 0, sorted(set(reasons))


def emit_context_preflight_result(*, run_id: str, trace_id: str, bundle_ref: str, passed: bool, reason_codes: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": "context_preflight_result",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "result_id": f"CTXP-{run_id}-{trace_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "bundle_ref": bundle_ref,
        "passed": bool(passed),
        "reason_codes": sorted(set(reason_codes)),
    }
