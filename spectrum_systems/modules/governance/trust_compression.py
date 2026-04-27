"""NT trust compression utilities: freshness, size budgets, reason lifecycle, delta."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
FRESHNESS_POLICY_PATH = REPO_ROOT / "contracts" / "governance" / "trust_artifact_freshness_policy.json"
SIZE_POLICY_PATH = REPO_ROOT / "contracts" / "governance" / "proof_bundle_size_policy.json"
REASON_ALIAS_PATH = REPO_ROOT / "contracts" / "governance" / "reason_code_aliases.json"


class TrustCompressionError(ValueError):
    """Raised when trust compression checks cannot be evaluated deterministically."""


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise TrustCompressionError(f"required policy missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustCompressionError(f"invalid json at {path}: {exc}") from exc


def _sha256_json(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _parse_iso(value: str | None) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def audit_trust_artifact_freshness(
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    now_iso: str | None = None,
    policy: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    pol = dict(policy) if policy is not None else _load_json(FRESHNESS_POLICY_PATH)
    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    artifact_rules = pol.get("artifacts") or {}
    reasons = pol.get("canonical_reasons") or {}

    results: Dict[str, Dict[str, Any]] = {}
    stale_or_unknown: list[str] = []

    for artifact_name, item in artifacts.items():
        rule = artifact_rules.get(artifact_name, {})
        expected_digest = item.get("source_digest")
        actual_digest = item.get("producer_input_digest")
        generated_at = _parse_iso(item.get("generated_at") or item.get("checked_at"))

        status = "current"
        reason = ""

        if isinstance(expected_digest, str) and expected_digest and isinstance(actual_digest, str) and actual_digest:
            if expected_digest != actual_digest:
                status = "stale"
                reason = reasons.get("digest_mismatch", "TRUST_ARTIFACT_DIGEST_MISMATCH")
        elif rule.get("require_source_digest"):
            status = "unknown"
            reason = reasons.get("missing_digest", "TRUST_ARTIFACT_MISSING_DIGEST")

        if status == "current" and generated_at is not None and isinstance(rule.get("max_age_hours"), (int, float)):
            age_hours = (now - generated_at).total_seconds() / 3600.0
            if age_hours > float(rule["max_age_hours"]):
                status = "stale"
                reason = reasons.get("stale_timestamp", "TRUST_ARTIFACT_STALE")
        elif status == "current" and rule.get("require_generated_at"):
            status = "unknown"
            reason = reasons.get("missing_timestamp", "TRUST_ARTIFACT_TIMESTAMP_MISSING")

        if status != "current":
            stale_or_unknown.append(artifact_name)
        results[artifact_name] = {
            "status": status,
            "reason": reason,
            "producer_input_digest": actual_digest,
            "source_digest": expected_digest,
            "generated_at": item.get("generated_at"),
            "checked_at": item.get("checked_at"),
        }

    overall = "current" if not stale_or_unknown else "stale"
    return {
        "artifact_type": "trust_artifact_freshness_audit",
        "status": overall,
        "results": results,
        "stale_or_unknown": sorted(stale_or_unknown),
    }


def _count_nested_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, Mapping):
        if not value:
            return depth
        return max(_count_nested_depth(v, depth + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return depth
        return max(_count_nested_depth(v, depth + 1) for v in value)
    return depth


def enforce_proof_size_budget(*, proof_bundle: Mapping[str, Any], evidence_index: Mapping[str, Any] | None = None, one_page_trace: str = "", policy: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    pol = dict(policy) if policy is not None else _load_json(SIZE_POLICY_PATH)
    limits = pol.get("limits") or {}
    b_lim = limits.get("loop_proof_bundle", {})
    e_lim = limits.get("certification_evidence_index", {})
    t_lim = limits.get("one_page_trace", {})

    reasons: list[str] = []
    decision = "allow"

    refs = [k for k in proof_bundle.keys() if k.endswith("_ref") and proof_bundle.get(k)]
    if len(refs) > int(b_lim.get("max_top_level_evidence_refs", 999999)):
        decision = "block"
        reasons.append("PROOF_BUNDLE_OVERSIZED_REFS")

    if _count_nested_depth(proof_bundle) > int(b_lim.get("max_nested_depth", 999999)):
        decision = "block"
        reasons.append("PROOF_BUNDLE_NESTED_DEPTH_EXCEEDED")

    lines = [ln for ln in one_page_trace.splitlines() if ln.strip()]
    if len(lines) > int(t_lim.get("max_summary_lines", 999999)):
        decision = "block"
        reasons.append("ONE_PAGE_TRACE_OVERSIZED")

    if isinstance(evidence_index, Mapping):
        e_refs = [k for k in (evidence_index.get("references") or {}).keys() if (evidence_index.get("references") or {}).get(k)]
        if len(e_refs) > int(e_lim.get("max_top_level_evidence_refs", 999999)):
            decision = "block"
            reasons.append("CERT_INDEX_OVERSIZED_REFS")
        if _count_nested_depth(evidence_index) > int(e_lim.get("max_nested_depth", 999999)):
            decision = "block"
            reasons.append("CERT_INDEX_NESTED_DEPTH_EXCEEDED")

    return {
        "decision": decision,
        "reason_codes": sorted(set(reasons)),
        "overflow_behavior": (pol.get("overflow_behavior") or {}).get("mode", "reference_external_evidence"),
        "external_reference_field": (pol.get("overflow_behavior") or {}).get("external_reference_field", "external_evidence_refs"),
    }


def compress_evidence_refs(refs: Iterable[str]) -> list[str]:
    return sorted({str(ref) for ref in refs if isinstance(ref, str) and ref.strip()})


def build_certification_delta(*, current_index: Mapping[str, Any], previous_index: Mapping[str, Any] | None) -> Dict[str, Any]:
    cur_refs = current_index.get("references") if isinstance(current_index, Mapping) else {}
    prev_refs = previous_index.get("references") if isinstance(previous_index, Mapping) else {}
    cur_refs = dict(cur_refs or {})
    prev_refs = dict(prev_refs or {})

    cur_keys = set(cur_refs)
    prev_keys = set(prev_refs)
    added = sorted(cur_keys - prev_keys)
    removed = sorted(prev_keys - cur_keys)
    unchanged = sorted([k for k in cur_keys & prev_keys if cur_refs.get(k) == prev_refs.get(k)])
    changed = sorted([k for k in cur_keys & prev_keys if cur_refs.get(k) != prev_refs.get(k)])

    current_digest = _sha256_json(current_index)
    previous_digest = _sha256_json(previous_index or {})

    if not added and not removed and not changed:
        risk = "none"
    elif removed or len(changed) >= 3:
        risk = "high"
    elif changed or added:
        risk = "medium"
    else:
        risk = "low"

    return {
        "artifact_type": "certification_delta_index",
        "added_evidence_refs": added,
        "removed_evidence_refs": removed,
        "changed_evidence_refs": changed,
        "unchanged_refs": unchanged,
        "changed_statuses": {
            "previous": (previous_index or {}).get("status"),
            "current": current_index.get("status"),
        },
        "changed_canonical_reasons": {
            "previous": (previous_index or {}).get("blocking_reason_canonical"),
            "current": current_index.get("blocking_reason_canonical"),
        },
        "changed_owner_systems": {
            "previous": (previous_index or {}).get("owner_system"),
            "current": current_index.get("owner_system"),
        },
        "current_digest": current_digest,
        "previous_digest": previous_digest,
        "overall_delta_risk": risk,
    }


def audit_reason_code_lifecycle(*, emitted_codes: Iterable[str], alias_map: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    amap = dict(alias_map) if alias_map is not None else _load_json(REASON_ALIAS_PATH)
    aliases = amap.get("aliases") or {}
    canonical_categories = set(amap.get("canonical_categories") or [])
    lifecycle = amap.get("lifecycle") or {}
    deprecated = set((lifecycle.get("deprecated") or {}).keys())
    forbidden = set((lifecycle.get("forbidden") or {}).keys())
    merged = lifecycle.get("merged") or {}

    emitted = [str(c) for c in emitted_codes]
    unknown_blocking = [c for c in emitted if c.lower() in {"blocked", "freeze", "fail", "error", "rejected"} and c.lower() not in aliases]
    unmapped = [c for c in emitted if c.upper() not in canonical_categories and c.lower() not in aliases]
    deprecated_emitted = sorted({c for c in emitted if c.lower() in deprecated})
    forbidden_emitted = sorted({c for c in emitted if c.lower() in forbidden})

    duplicate_meaning: Dict[str, list[str]] = {}
    reverse: Dict[str, list[str]] = {}
    for a, cat in aliases.items():
        reverse.setdefault(str(cat), []).append(str(a))
    for cat, vals in reverse.items():
        if len(vals) > 1:
            duplicate_meaning[cat] = sorted(vals)

    aliases_missing_category = sorted([a for a, cat in aliases.items() if str(cat) not in canonical_categories])
    unused_aliases = sorted([a for a in aliases.keys() if str(a) not in [e.lower() for e in emitted]])

    return {
        "unmapped_blocking_reason_codes": sorted(set(unknown_blocking)),
        "unmapped_reason_codes": sorted(set(unmapped)),
        "unused_aliases": unused_aliases,
        "duplicate_alias_meanings": duplicate_meaning,
        "aliases_pointing_to_missing_category": aliases_missing_category,
        "deprecated_aliases_emitted": deprecated_emitted,
        "forbidden_aliases_emitted": forbidden_emitted,
        "merged_aliases": merged,
        "decision": "block" if unknown_blocking or forbidden_emitted else "allow",
    }


__all__ = [
    "TrustCompressionError",
    "audit_reason_code_lifecycle",
    "audit_trust_artifact_freshness",
    "build_certification_delta",
    "compress_evidence_refs",
    "enforce_proof_size_budget",
]
