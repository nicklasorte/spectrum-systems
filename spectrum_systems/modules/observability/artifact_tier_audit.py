"""OBS: Artifact tier audit + retention policy validation.

NS-01..03: Build a deterministic, fail-closed inventory/audit capability that
classifies generated artifacts into a small set of tiers, and enforce that
report/generated_cache/test_temp artifacts cannot satisfy required promotion
evidence unless explicitly allowlisted.

This module reads the canonical tier policy from
``contracts/governance/artifact_tier_policy.json`` and exposes:

  * ``load_artifact_tier_policy()`` → policy mapping
  * ``classify_artifact(item, policy)`` → tier-bearing classification
  * ``audit_artifacts(items, policy)`` → inventory result
  * ``validate_promotion_evidence_tiers(items, policy)`` → fail-closed gate

It does not invent tier semantics; the policy file is canonical. The module
is a non-owning seam — it reports tier validation results that downstream
seams (certification evidence index, registry validator) consume.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "contracts" / "governance" / "artifact_tier_policy.json"
)


CANONICAL_TIER_VALIDATION_REASON_CODES = {
    "TIER_OK",
    "TIER_TEST_TEMP_AS_EVIDENCE",
    "TIER_REPORT_AS_AUTHORITY",
    "TIER_GENERATED_CACHE_AS_CANONICAL",
    "TIER_DUPLICATE_LOW_SIGNAL",
    "TIER_STALE_GENERATED",
    "TIER_UNKNOWN_TIER",
    "TIER_POLICY_UNAVAILABLE",
}


class ArtifactTierError(ValueError):
    """Raised when artifact tier audit cannot be deterministically performed."""


def load_artifact_tier_policy(
    policy_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the canonical artifact tier policy."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise ArtifactTierError(
            f"artifact tier policy not found at {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactTierError(f"artifact tier policy invalid JSON: {exc}") from exc
    if data.get("artifact_type") != "artifact_tier_policy":
        raise ArtifactTierError(
            f"artifact tier policy artifact_type mismatch: {data.get('artifact_type')!r}"
        )
    if not isinstance(data.get("tiers"), dict):
        raise ArtifactTierError("artifact tier policy missing tiers")
    return data


def _match_path_prefixes(path: Optional[str], prefixes: Iterable[str]) -> bool:
    if not isinstance(path, str) or not path:
        return False
    norm = path.lstrip("./")
    for prefix in prefixes:
        if norm.startswith(prefix):
            return True
    return False


def classify_artifact(
    item: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    """Classify a single artifact item according to the tier policy.

    ``item`` is a mapping that can carry any subset of:
      - artifact_id (required)
      - artifact_path
      - artifact_type
      - artifact_family
      - owner_system
      - producer_path
      - tier (explicit; takes precedence)

    Returns the input fields plus tier classification.
    """
    if not isinstance(item, Mapping):
        raise ArtifactTierError("artifact item must be a mapping")
    artifact_id = item.get("artifact_id") or item.get("id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise ArtifactTierError("artifact item missing artifact_id")

    explicit_tier = item.get("tier")
    tier: Optional[str] = None
    if isinstance(explicit_tier, str) and explicit_tier in policy.get("tiers", {}):
        tier = explicit_tier

    if tier is None:
        for rule in policy.get("tier_assignment_rules", []) or []:
            if not isinstance(rule, Mapping):
                continue
            path_prefixes = rule.get("match_path_prefixes") or []
            if path_prefixes and _match_path_prefixes(
                item.get("artifact_path"), path_prefixes
            ):
                tier = str(rule.get("tier"))
                break
            artifact_types = rule.get("match_artifact_types") or []
            if artifact_types and item.get("artifact_type") in artifact_types:
                tier = str(rule.get("tier"))
                break

    if tier is None:
        tier = str(policy.get("default_tier_when_unmatched", "report"))

    tier_def = policy.get("tiers", {}).get(tier)
    if not isinstance(tier_def, Mapping):
        raise ArtifactTierError(f"unknown tier {tier!r} for artifact {artifact_id}")

    return {
        "artifact_id": artifact_id,
        "artifact_path": str(item.get("artifact_path") or ""),
        "artifact_family": str(item.get("artifact_family") or ""),
        "artifact_type": str(item.get("artifact_type") or ""),
        "owner_system": str(item.get("owner_system") or ""),
        "producer_path": str(item.get("producer_path") or ""),
        "tier": tier,
        "promotion_relevant": bool(tier_def.get("promotion_relevant", False)),
        "replay_relevant": bool(tier_def.get("replay_relevant", False)),
        "lineage_relevant": bool(tier_def.get("lineage_relevant", False)),
        "retention": str(tier_def.get("retention", "ephemeral")),
        "scan_scope": str(tier_def.get("scan_scope", "tooling_only")),
    }


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def audit_artifacts(
    items: Iterable[Mapping[str, Any]],
    *,
    policy: Optional[Mapping[str, Any]] = None,
    now_iso: Optional[str] = None,
    stale_after_days: int = 30,
) -> Dict[str, Any]:
    """Build an inventory + tier classification across the supplied items.

    Returns
    -------
    {"items": [...classified...],
     "tier_counts": {tier: count},
     "duplicates": [(artifact_id, duplicate_of), ...],
     "stale": [artifact_id, ...]}
    """
    pol = dict(policy) if policy is not None else load_artifact_tier_policy()
    classified: List[Dict[str, Any]] = []
    seen_keys: Dict[str, str] = {}
    duplicates: List[Dict[str, str]] = []
    stale_ids: List[str] = []
    now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)

    for raw in items:
        cls = classify_artifact(raw, pol)
        # duplicate detection: same artifact_type + path + content_hash count as dup
        dup_key = "|".join(
            [
                cls["artifact_type"] or "",
                cls["artifact_family"] or "",
                cls["artifact_path"] or "",
                str(raw.get("content_hash") or ""),
            ]
        )
        if dup_key.strip("|") and dup_key in seen_keys:
            cls["duplicate_of"] = seen_keys[dup_key]
            duplicates.append({"artifact_id": cls["artifact_id"], "duplicate_of": seen_keys[dup_key]})
        elif dup_key.strip("|"):
            seen_keys[dup_key] = cls["artifact_id"]

        # staleness detection for generated_cache only
        if cls["tier"] == "generated_cache":
            generated_at = raw.get("generated_at") or raw.get("created_at")
            if isinstance(generated_at, str):
                ts = _parse_iso(generated_at)
                if ts is not None and now is not None:
                    age_days = (now - ts).total_seconds() / 86400.0
                    if age_days > stale_after_days:
                        cls["stale"] = True
                        stale_ids.append(cls["artifact_id"])

        classified.append(cls)

    counts: Dict[str, int] = {}
    for c in classified:
        counts[c["tier"]] = counts.get(c["tier"], 0) + 1

    return {
        "items": classified,
        "tier_counts": counts,
        "duplicates": duplicates,
        "stale": stale_ids,
    }


def validate_promotion_evidence_tiers(
    promotion_evidence_items: Iterable[Mapping[str, Any]],
    *,
    policy: Optional[Mapping[str, Any]] = None,
    validation_id: str,
    trace_id: str = "",
) -> Dict[str, Any]:
    """Fail-closed validation: every promotion evidence item must be tier
    ``canonical`` or ``evidence`` (or be in the explicit override list).

    Returns a result conformant to ``artifact_tier_validation_result``.
    """
    pol = dict(policy) if policy is not None else load_artifact_tier_policy()
    allow_tiers = set(pol.get("promotion_evidence_allowlist_tiers", ["canonical", "evidence"]))
    overrides = {str(o) for o in pol.get("explicit_promotion_overrides", []) or []}

    classified: List[Dict[str, Any]] = []
    blocking: List[str] = []
    decision = "allow"
    reason_code = "TIER_OK"
    counts: Dict[str, int] = {}

    for raw in promotion_evidence_items:
        cls = classify_artifact(raw, pol)
        classified.append(cls)
        counts[cls["tier"]] = counts.get(cls["tier"], 0) + 1
        tier = cls["tier"]
        artifact_id = cls["artifact_id"]

        if tier in allow_tiers or artifact_id in overrides:
            continue

        decision = "block"
        if tier == "test_temp":
            blocking.append(
                f"artifact {artifact_id} is tier=test_temp; cannot be promotion evidence"
            )
            if reason_code == "TIER_OK":
                reason_code = "TIER_TEST_TEMP_AS_EVIDENCE"
        elif tier == "report":
            blocking.append(
                f"artifact {artifact_id} is tier=report; reports are not authority-bearing"
            )
            if reason_code == "TIER_OK":
                reason_code = "TIER_REPORT_AS_AUTHORITY"
        elif tier == "generated_cache":
            blocking.append(
                f"artifact {artifact_id} is tier=generated_cache; not canonical evidence"
            )
            if reason_code == "TIER_OK":
                reason_code = "TIER_GENERATED_CACHE_AS_CANONICAL"
        else:
            blocking.append(
                f"artifact {artifact_id} has unknown tier {tier!r}"
            )
            if reason_code == "TIER_OK":
                reason_code = "TIER_UNKNOWN_TIER"

    return {
        "artifact_type": "artifact_tier_validation_result",
        "schema_version": "1.0.0",
        "validation_id": validation_id,
        "trace_id": trace_id,
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "tier_counts": counts,
        "items": classified,
    }


__all__ = [
    "ArtifactTierError",
    "CANONICAL_TIER_VALIDATION_REASON_CODES",
    "audit_artifacts",
    "classify_artifact",
    "load_artifact_tier_policy",
    "validate_promotion_evidence_tiers",
]
