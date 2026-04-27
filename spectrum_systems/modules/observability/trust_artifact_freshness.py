"""OBS: Trust artifact freshness audit (NT-01..03).

A small, fail-closed seam that determines whether trust artifacts (artifact
tier policy, reason-code alias map, certification evidence index, loop proof
bundle, failure trace, replay-lineage join summary, SLO signal policy,
freshness policy itself) are current, stale, or unknown.

A producer/source digest, when present, is the dominant freshness signal.
Timestamps are only used when no digest is available. Missing signal is
``unknown`` (not silently ``current``) so callers can fail closed.

The canonical policy lives at
``contracts/governance/trust_artifact_freshness_policy.json``. This module
does not own freshness semantics — it reports the result so downstream
seams (certification evidence index, loop proof bundle) can include or
gate on it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "contracts" / "governance" / "trust_artifact_freshness_policy.json"
)


CANONICAL_FRESHNESS_REASON_CODES = (
    "TRUST_FRESHNESS_OK",
    "TRUST_FRESHNESS_POLICY_STALE",
    "TRUST_FRESHNESS_ALIAS_MAP_STALE",
    "TRUST_FRESHNESS_EVIDENCE_INDEX_STALE",
    "TRUST_FRESHNESS_PROOF_BUNDLE_STALE",
    "TRUST_FRESHNESS_TRACE_STALE",
    "TRUST_FRESHNESS_JOIN_SUMMARY_STALE",
    "TRUST_FRESHNESS_SLO_POLICY_STALE",
    "TRUST_FRESHNESS_DIGEST_MISMATCH",
    "TRUST_FRESHNESS_UNKNOWN",
    "TRUST_FRESHNESS_POLICY_UNAVAILABLE",
)


FRESHNESS_STATUSES = ("current", "stale", "unknown")


class TrustArtifactFreshnessError(ValueError):
    """Raised when freshness audit cannot be deterministically performed."""


def load_trust_artifact_freshness_policy(
    policy_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the canonical trust artifact freshness policy."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise TrustArtifactFreshnessError(
            f"trust artifact freshness policy not found at {path}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustArtifactFreshnessError(
            f"trust artifact freshness policy invalid JSON: {exc}"
        ) from exc
    if data.get("artifact_type") != "trust_artifact_freshness_policy":
        raise TrustArtifactFreshnessError(
            f"trust artifact freshness policy artifact_type mismatch: "
            f"{data.get('artifact_type')!r}"
        )
    if not isinstance(data.get("rules"), list):
        raise TrustArtifactFreshnessError(
            "trust artifact freshness policy missing rules"
        )
    return data


def _parse_iso(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        norm = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        return datetime.fromisoformat(norm)
    except (TypeError, ValueError):
        return None


def _rule_for(artifact_type: str, policy: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    for rule in policy.get("rules", []) or []:
        if isinstance(rule, Mapping) and rule.get("match_artifact_type") == artifact_type:
            return rule
    return None


def audit_artifact_freshness(
    artifact: Mapping[str, Any],
    *,
    expected_input_digest: Optional[str] = None,
    expected_source_digest: Optional[str] = None,
    policy: Optional[Mapping[str, Any]] = None,
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    """Audit freshness of a single trust artifact.

    Parameters
    ----------
    artifact:
        The trust artifact dict (or summary). Must carry ``artifact_type``.
    expected_input_digest:
        The producer-input digest the caller observed at audit time. When
        provided alongside an artifact field carrying its recorded input
        digest, mismatch is a hard ``stale`` signal.
    expected_source_digest:
        The source-evidence digest the caller observed at audit time. When
        provided, mismatch is a hard ``stale`` signal that overrides any
        timestamp-based ``current`` reading.

    Returns
    -------
    {"artifact_type": str,
     "status": "current" | "stale" | "unknown",
     "reason_code": str (canonical CANONICAL_FRESHNESS_REASON_CODES),
     "canonical_reason": str (CERTIFICATION_GAP unless mapped otherwise),
     "checks": {"input_digest_match": bool|None,
                "source_digest_match": bool|None,
                "timestamp_within_max_age": bool|None},
     "details": {...}}
    """
    if not isinstance(artifact, Mapping):
        raise TrustArtifactFreshnessError("artifact must be a mapping")

    pol = dict(policy) if policy is not None else load_trust_artifact_freshness_policy()
    artifact_type = str(artifact.get("artifact_type") or "")
    rule = _rule_for(artifact_type, pol)

    canonical_reasons = pol.get("canonical_reason_codes") or {}

    if rule is None:
        return {
            "artifact_type": artifact_type or None,
            "status": "unknown",
            "reason_code": "TRUST_FRESHNESS_UNKNOWN",
            "canonical_reason": canonical_reasons.get(
                "TRUST_FRESHNESS_UNKNOWN", "CERTIFICATION_GAP"
            ),
            "checks": {
                "input_digest_match": None,
                "source_digest_match": None,
                "timestamp_within_max_age": None,
            },
            "details": {"note": "no freshness rule for artifact_type"},
        }

    input_digest_field = rule.get("input_digest_field")
    source_digest_field = rule.get("source_digest_field")
    timestamp_field = rule.get("timestamp_field")
    max_age_days = float(rule.get("max_age_days") or 0)
    stale_reason = str(rule.get("stale_reason") or "TRUST_FRESHNESS_UNKNOWN")
    missing_reason = str(rule.get("missing_reason") or "TRUST_FRESHNESS_UNKNOWN")

    # 1. Source digest dominates
    source_digest_match: Optional[bool] = None
    if source_digest_field:
        recorded_source = artifact.get(source_digest_field)
        if isinstance(recorded_source, str) and recorded_source.strip():
            if expected_source_digest is not None:
                source_digest_match = recorded_source == expected_source_digest

    # 2. Input digest secondary
    input_digest_match: Optional[bool] = None
    if input_digest_field:
        recorded_input = artifact.get(input_digest_field)
        if isinstance(recorded_input, str) and recorded_input.strip():
            if expected_input_digest is not None:
                input_digest_match = recorded_input == expected_input_digest

    # 3. Timestamp tertiary
    timestamp_within_max_age: Optional[bool] = None
    if timestamp_field and max_age_days > 0:
        ts_raw = artifact.get(timestamp_field)
        ts = _parse_iso(ts_raw)
        now = _parse_iso(now_iso) or datetime.now(timezone.utc)
        if ts is not None:
            age_days = (now - ts).total_seconds() / 86400.0
            timestamp_within_max_age = age_days <= max_age_days

    # Source-digest field is the dominant signal when the artifact records
    # one. If the caller could not verify it, we refuse to silently fall
    # back to the input-digest or timestamp signals.
    has_source_field = bool(
        source_digest_field
        and isinstance(artifact.get(source_digest_field), str)
        and artifact.get(source_digest_field).strip()
    )
    source_unverified = (
        has_source_field
        and source_digest_match is None
    )

    if source_digest_match is False or input_digest_match is False:
        status = "stale"
        reason_code = "TRUST_FRESHNESS_DIGEST_MISMATCH"
    elif source_unverified:
        status = "unknown"
        reason_code = "TRUST_FRESHNESS_UNKNOWN"
    elif source_digest_match is True or input_digest_match is True:
        if timestamp_within_max_age is False:
            status = "stale"
            reason_code = stale_reason
        else:
            status = "current"
            reason_code = "TRUST_FRESHNESS_OK"
    else:
        # No digest signal at all. Fall back to timestamp only when the
        # artifact carries no source_digest_field at all.
        if timestamp_within_max_age is True:
            status = "current"
            reason_code = "TRUST_FRESHNESS_OK"
        elif timestamp_within_max_age is False:
            status = "stale"
            reason_code = stale_reason
        else:
            status = "unknown"
            reason_code = missing_reason

    canonical_reason = canonical_reasons.get(reason_code, "CERTIFICATION_GAP")

    return {
        "artifact_type": artifact_type or None,
        "status": status,
        "reason_code": reason_code,
        "canonical_reason": canonical_reason,
        "checks": {
            "input_digest_match": input_digest_match,
            "source_digest_match": source_digest_match,
            "timestamp_within_max_age": timestamp_within_max_age,
        },
        "details": {
            "rule_id": rule.get("rule_id"),
            "max_age_days": max_age_days,
        },
    }


def audit_trust_artifact_freshness(
    artifacts: Iterable[Mapping[str, Any]],
    *,
    expected_digests_by_type: Optional[Mapping[str, Mapping[str, str]]] = None,
    policy: Optional[Mapping[str, Any]] = None,
    now_iso: Optional[str] = None,
) -> Dict[str, Any]:
    """Audit freshness across a collection of trust artifacts.

    ``expected_digests_by_type`` maps artifact_type → {"input": str,
    "source": str}; either subkey is optional.

    Returns a summary suitable for inclusion in a certification evidence
    index, loop proof bundle, or operator triage CLI.
    """
    pol = dict(policy) if policy is not None else load_trust_artifact_freshness_policy()
    expected = dict(expected_digests_by_type or {})

    items: List[Dict[str, Any]] = []
    counts = {"current": 0, "stale": 0, "unknown": 0}
    blocking: List[str] = []

    for art in artifacts:
        if not isinstance(art, Mapping):
            continue
        atype = str(art.get("artifact_type") or "")
        digests = expected.get(atype) or {}
        result = audit_artifact_freshness(
            art,
            expected_input_digest=digests.get("input"),
            expected_source_digest=digests.get("source"),
            policy=pol,
            now_iso=now_iso,
        )
        items.append(result)
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if result["status"] in {"stale", "unknown"}:
            blocking.append(
                f"{atype or 'unknown'}: {result['status']} ({result['reason_code']})"
            )

    overall_status = "current"
    if counts.get("stale", 0) > 0 or counts.get("unknown", 0) > 0:
        overall_status = "stale" if counts.get("stale", 0) > 0 else "unknown"

    return {
        "artifact_type": "trust_artifact_freshness_summary",
        "schema_version": "1.0.0",
        "overall_status": overall_status,
        "counts": counts,
        "items": items,
        "blocking_reasons": blocking,
    }


__all__ = [
    "CANONICAL_FRESHNESS_REASON_CODES",
    "FRESHNESS_STATUSES",
    "TrustArtifactFreshnessError",
    "audit_artifact_freshness",
    "audit_trust_artifact_freshness",
    "load_trust_artifact_freshness_policy",
]
