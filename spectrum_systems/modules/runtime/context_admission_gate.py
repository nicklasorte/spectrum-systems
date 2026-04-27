"""CTX admission gate — strict, fail-closed context bundle admission.

NX-19: This module wraps the existing ``ctx`` primitives with an explicit
admission gate that fail-closes on:
  - missing source provenance
  - stale TTL
  - schema-incompatible candidates
  - untrusted candidates marked as instructions
  - contradictory candidates
  - missing preflight

It does not duplicate ``ctx``; it is a thin adjudication seam used at the
admission boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple


class ContextAdmissionError(ValueError):
    """Raised when context admission cannot be deterministically performed."""


CANONICAL_CTX_REASON_CODES = {
    "CTX_OK",
    "CTX_MISSING_PROVENANCE",
    "CTX_STALE_TTL",
    "CTX_SCHEMA_INCOMPATIBLE",
    "CTX_UNTRUSTED_INSTRUCTION",
    "CTX_CONTRADICTORY_CONTEXT",
    "CTX_MALFORMED_BUNDLE",
    "CTX_MISSING_PREFLIGHT",
}


_INSTRUCTION_ROLES = {"system", "instruction", "policy", "directive"}


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def admit_context_bundle(
    *,
    bundle: Mapping[str, Any],
    now_iso: Optional[str] = None,
    require_preflight: bool = True,
    expected_schema_versions: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Admit or block a context bundle.

    Returns
    -------
    {"decision": "allow"|"block",
     "reason_code": canonical reason,
     "blocking_reasons": [str,...],
     "rejected_candidate_ids": [str,...]}
    """
    if not isinstance(bundle, Mapping):
        raise ContextAdmissionError("bundle must be a mapping")

    now = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
    if now is None:
        raise ContextAdmissionError(f"now_iso is not a valid ISO timestamp: {now_iso!r}")

    candidates = bundle.get("admitted_candidates") or bundle.get("candidates") or []
    if not isinstance(candidates, list):
        return {
            "decision": "block",
            "reason_code": "CTX_MALFORMED_BUNDLE",
            "blocking_reasons": ["candidates must be a list"],
            "rejected_candidate_ids": [],
        }

    blocking: List[str] = []
    rejected: List[str] = []
    reason_code = "CTX_OK"

    if require_preflight and not bundle.get("preflight_passed"):
        blocking.append("preflight not passed for context bundle")
        reason_code = "CTX_MISSING_PREFLIGHT"

    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            blocking.append(f"candidate[{idx}] is not a mapping")
            rejected.append(str(idx))
            reason_code = "CTX_MALFORMED_BUNDLE"
            continue

        cid = str(candidate.get("candidate_id") or candidate.get("id") or idx)

        provenance = candidate.get("provenance") or candidate.get("source_provenance")
        if not provenance or (isinstance(provenance, Mapping) and not provenance.get("source")):
            blocking.append(f"candidate {cid} missing source provenance")
            rejected.append(cid)
            if reason_code == "CTX_OK":
                reason_code = "CTX_MISSING_PROVENANCE"
            continue

        # TTL check (if present)
        expires_at = candidate.get("expires_at")
        if isinstance(expires_at, str):
            expires = _parse_iso(expires_at)
            if expires is not None and expires < now:
                blocking.append(f"candidate {cid} stale (expired at {expires_at})")
                rejected.append(cid)
                if reason_code == "CTX_OK":
                    reason_code = "CTX_STALE_TTL"
                continue

        # Schema version compatibility
        if expected_schema_versions:
            artifact_type = str(candidate.get("artifact_type") or "")
            cv = str(candidate.get("schema_version") or "")
            expected = expected_schema_versions.get(artifact_type)
            if expected and cv and cv != expected:
                blocking.append(
                    f"candidate {cid} schema_version {cv!r} != expected {expected!r}"
                )
                rejected.append(cid)
                if reason_code == "CTX_OK":
                    reason_code = "CTX_SCHEMA_INCOMPATIBLE"
                continue

        # Untrusted instruction injection: untrusted role with instruction-class.
        trust_level = str(candidate.get("trust_level") or "untrusted").lower()
        role = str(candidate.get("role") or "").lower()
        if trust_level == "untrusted" and role in _INSTRUCTION_ROLES:
            blocking.append(
                f"candidate {cid} is untrusted ({role}) but flagged as instruction"
            )
            rejected.append(cid)
            if reason_code == "CTX_OK":
                reason_code = "CTX_UNTRUSTED_INSTRUCTION"
            continue

    # Contradiction check: candidates that have the same `topic` but
    # conflicting `assertion` values should fail closed.
    topic_assertions: Dict[str, set] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        topic = candidate.get("topic")
        assertion = candidate.get("assertion")
        if isinstance(topic, str) and isinstance(assertion, str):
            topic_assertions.setdefault(topic, set()).add(assertion)
    for topic, asserts in topic_assertions.items():
        if len(asserts) > 1:
            blocking.append(
                f"contradictory context for topic {topic!r}: {sorted(asserts)}"
            )
            if reason_code == "CTX_OK":
                reason_code = "CTX_CONTRADICTORY_CONTEXT"

    decision = "allow" if not blocking else "block"
    return {
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "rejected_candidate_ids": rejected,
    }


__all__ = [
    "CANONICAL_CTX_REASON_CODES",
    "ContextAdmissionError",
    "admit_context_bundle",
]
