"""Certification delta index (NT-19..21).

Compares two certification evidence indexes and produces a delta artifact
that lists what changed between proof runs:

  - added evidence references
  - removed evidence references
  - changed evidence digests (same id, different content hash)
  - changed evidence statuses (same id, status flipped)
  - changed canonical reasons (same id, canonical reason category changed)
  - changed owner systems (same id, owning system changed)
  - unchanged references

The delta is non-owning. It does not decide promotion; it surfaces the
change set so the readiness check can refuse to advance unless every
required delta is explained.

Delta risk levels:
  - ``none``    nothing meaningful changed
  - ``low``     only refs added or unchanged
  - ``medium``  status / reason / owner changed for non-blocking refs
  - ``high``    digest changed, references removed, or any blocking flip

A high delta blocks readiness unless the caller supplies an
``explained_delta_keys`` set covering every changed key.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional


CANONICAL_DELTA_REASON_CODES = {
    "CERT_DELTA_OK",
    "CERT_DELTA_ADDED",
    "CERT_DELTA_REMOVED",
    "CERT_DELTA_CHANGED_DIGEST",
    "CERT_DELTA_CHANGED_STATUS",
    "CERT_DELTA_CHANGED_REASON",
    "CERT_DELTA_CHANGED_OWNER",
    "CERT_DELTA_UNEXPLAINED",
    "CERT_DELTA_SILENT_REMOVAL",
}


class CertificationDeltaError(ValueError):
    """Raised when a certification delta cannot be deterministically built."""


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _flatten_refs(index: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return ``{ref_key: {artifact_id, status, reason, owner, digest}}``.

    Reads from a certification_evidence_index. ``status`` / ``reason`` /
    ``owner`` / ``digest`` are best-effort: not every wrapper exposes
    each field, and absence is recorded as None.
    """
    out: Dict[str, Dict[str, Any]] = {}
    refs = index.get("references")
    detail_codes = index.get("blocking_detail_codes") or []
    detail_codes_str = list(str(c) for c in detail_codes if isinstance(c, str))
    if isinstance(refs, Mapping):
        for ref_key, artifact_id in refs.items():
            if artifact_id is None:
                continue
            entry: Dict[str, Any] = {
                "artifact_id": str(artifact_id),
                "status": None,
                "canonical_reason": None,
                "owner": None,
                "digest": None,
            }
            # Index-level digests block keyed by ref_key
            digests = index.get("evidence_digests")
            if isinstance(digests, Mapping):
                d = digests.get(ref_key)
                if isinstance(d, str) and d.strip():
                    entry["digest"] = d
            statuses = index.get("evidence_statuses")
            if isinstance(statuses, Mapping):
                s = statuses.get(ref_key)
                if isinstance(s, str) and s.strip():
                    entry["status"] = s.lower()
            owners = index.get("evidence_owners")
            if isinstance(owners, Mapping):
                o = owners.get(ref_key)
                if isinstance(o, str) and o.strip():
                    entry["owner"] = o
            # Per-key reason: derive from blocking_detail_codes when this
            # ref is named in one of the codes.
            for code in detail_codes_str:
                if ref_key.replace("_ref", "").upper() in code.upper():
                    entry["canonical_reason"] = code
                    break
            out[ref_key] = entry
    return out


def compute_certification_delta(
    *,
    delta_id: str,
    previous_index: Optional[Mapping[str, Any]],
    current_index: Mapping[str, Any],
    explained_delta_keys: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Build a certification_delta artifact comparing two evidence indexes."""
    if not isinstance(delta_id, str) or not delta_id.strip():
        raise CertificationDeltaError("delta_id must be a non-empty string")
    if not isinstance(current_index, Mapping):
        raise CertificationDeltaError("current_index must be a mapping")

    prev = _flatten_refs(previous_index or {})
    curr = _flatten_refs(current_index)

    explained = {str(k) for k in (explained_delta_keys or [])}

    added: List[str] = sorted(set(curr) - set(prev))
    removed: List[str] = sorted(set(prev) - set(curr))
    common: List[str] = sorted(set(prev) & set(curr))

    changed_digest: List[Dict[str, Any]] = []
    changed_status: List[Dict[str, Any]] = []
    changed_reason: List[Dict[str, Any]] = []
    changed_owner: List[Dict[str, Any]] = []
    unchanged: List[str] = []

    for key in common:
        p = prev[key]
        c = curr[key]
        any_change = False
        if p["artifact_id"] != c["artifact_id"]:
            # Same ref_key but different artifact_id — this is a digest-class
            # change: silently swapped evidence under the same field.
            changed_digest.append(
                {"ref_key": key, "previous": p["artifact_id"], "current": c["artifact_id"]}
            )
            any_change = True
        if p["digest"] is not None and c["digest"] is not None and p["digest"] != c["digest"]:
            changed_digest.append(
                {"ref_key": key, "previous_digest": p["digest"], "current_digest": c["digest"]}
            )
            any_change = True
        if p["status"] is not None and c["status"] is not None and p["status"] != c["status"]:
            changed_status.append(
                {"ref_key": key, "previous_status": p["status"], "current_status": c["status"]}
            )
            any_change = True
        if (
            p["canonical_reason"] is not None
            and c["canonical_reason"] is not None
            and p["canonical_reason"] != c["canonical_reason"]
        ):
            changed_reason.append(
                {
                    "ref_key": key,
                    "previous_reason": p["canonical_reason"],
                    "current_reason": c["canonical_reason"],
                }
            )
            any_change = True
        if p["owner"] is not None and c["owner"] is not None and p["owner"] != c["owner"]:
            changed_owner.append(
                {"ref_key": key, "previous_owner": p["owner"], "current_owner": c["owner"]}
            )
            any_change = True
        if not any_change:
            unchanged.append(key)

    risk = "none"
    if added or unchanged:
        risk = "low"
    if changed_status or changed_reason or changed_owner:
        risk = "medium"
    if changed_digest or removed:
        risk = "high"

    # Unexplained delta gating: every change key must be in explained_delta_keys
    # for the readiness gate to pass when risk == high.
    changed_keys = (
        {entry["ref_key"] for entry in changed_digest}
        | {entry["ref_key"] for entry in changed_status}
        | {entry["ref_key"] for entry in changed_reason}
        | {entry["ref_key"] for entry in changed_owner}
        | set(removed)
    )
    unexplained = sorted(changed_keys - explained)

    decision = "allow"
    canonical_reason = "CERT_DELTA_OK"
    blocking: List[str] = []
    if removed:
        decision = "block"
        canonical_reason = "CERT_DELTA_SILENT_REMOVAL"
        blocking.append(
            f"references removed without replacement: {sorted(removed)}"
        )
    if changed_digest and decision == "allow":
        decision = "block"
        canonical_reason = "CERT_DELTA_CHANGED_DIGEST"
        blocking.append(
            f"evidence digest changed for: {[c['ref_key'] for c in changed_digest]}"
        )
    if risk == "high" and unexplained and decision == "allow":
        decision = "block"
        canonical_reason = "CERT_DELTA_UNEXPLAINED"
        blocking.append(
            f"high-risk delta has unexplained keys: {unexplained}"
        )

    summary_lines = [
        f"CERTIFICATION DELTA — delta_id={delta_id} risk={risk}",
        f"added: {len(added)}  removed: {len(removed)}  unchanged: {len(unchanged)}",
        f"changed_digest: {len(changed_digest)}  changed_status: {len(changed_status)}",
        f"changed_reason: {len(changed_reason)}  changed_owner: {len(changed_owner)}",
        f"unexplained_keys: {unexplained}",
    ]

    return {
        "artifact_type": "certification_delta",
        "schema_version": "1.0.0",
        "delta_id": delta_id,
        "overall_delta_risk": risk,
        "decision": decision,
        "canonical_reason": canonical_reason,
        "blocking_reasons": blocking,
        "added_refs": added,
        "removed_refs": removed,
        "changed_digest": changed_digest,
        "changed_status": changed_status,
        "changed_reason": changed_reason,
        "changed_owner": changed_owner,
        "unchanged_refs": unchanged,
        "explained_delta_keys": sorted(explained),
        "unexplained_delta_keys": unexplained,
        "human_readable": "\n".join(summary_lines),
    }


__all__ = [
    "CANONICAL_DELTA_REASON_CODES",
    "CertificationDeltaError",
    "compute_certification_delta",
]
