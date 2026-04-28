"""OBS: Trust artifact freshness audit (NT-01..03).

Audits the freshness of the small set of trust artifacts that gate the
canonical loop:

  - artifact tier policy
  - reason-code alias map
  - certification evidence index
  - loop proof bundle
  - failure / pass trace
  - replay-lineage join summary
  - SLO signal policy

Each item is checked against three repo-native signals (in priority order):

  1. ``producer_input_digest``   — recomputed digest of the producer-side
                                   inputs that should match the artifact's
                                   declared digest.
  2. ``source_artifact_digest``  — digest of the upstream/source artifact
                                   compared to the value the audited
                                   artifact references.
  3. ``generated_at`` /
     ``checked_at``              — zero-offset timestamp strings; only
                                   consulted if no digest signal is
                                   available, so the audit does not
                                   silently rely on time alone when a
                                   stronger signal exists.

Outcome status per item:

  - ``current``  — digest match (or, when no digest is available, a fresh
                   timestamp inside the policy budget).
  - ``stale``    — digest mismatch, expired timestamp, or freshness policy
                   violation.
  - ``unknown``  — neither digest nor timestamp present; treated as a hard
                   trust failure unless the policy explicitly allows it.

The audit is fail-closed: missing required artifacts produce a stale entry
with a canonical reason rather than a silent skip. The canonical reasons
emitted are aliased into the canonical reason-code mapping layer so
downstream certification can fail closed with a stable category.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = (
    REPO_ROOT
    / "contracts"
    / "governance"
    / "trust_artifact_freshness_policy.json"
)


CANONICAL_FRESHNESS_REASON_CODES = {
    "TRUST_FRESHNESS_OK",
    "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH",
    "TRUST_FRESHNESS_STALE_SOURCE_DIGEST_MISMATCH",
    "TRUST_FRESHNESS_STALE_TIMESTAMP",
    "TRUST_FRESHNESS_UNKNOWN_NO_PROOF",
    "TRUST_FRESHNESS_MISSING_ARTIFACT",
    "TRUST_FRESHNESS_POLICY_UNAVAILABLE",
}


REQUIRED_TRUST_ARTIFACT_KINDS = (
    "artifact_tier_policy",
    "reason_code_alias_map",
    "certification_evidence_index",
    "loop_proof_bundle",
    "failure_trace",
    "replay_lineage_join_summary",
    "slo_signal_policy",
)


class TrustFreshnessError(ValueError):
    """Raised when freshness audit cannot be deterministically performed."""


def _canonical_hash(payload: Any) -> str:
    """Repo-native deterministic hash for arbitrary JSON-shaped payloads.

    Mirrors ``replay_support.canonical_hash`` so the freshness audit and
    replay coverage compute the same digest for the same inputs.
    """
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    if isinstance(payload, str):
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts.strip():
        return None
    raw = ts.strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def load_trust_artifact_freshness_policy(
    policy_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the canonical trust artifact freshness policy."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise TrustFreshnessError(
            f"trust artifact freshness policy not found at {path}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustFreshnessError(
            f"trust artifact freshness policy invalid JSON: {exc}"
        ) from exc
    if data.get("artifact_type") != "trust_artifact_freshness_policy":
        raise TrustFreshnessError(
            "trust artifact freshness policy artifact_type mismatch"
        )
    if not isinstance(data.get("artifact_kinds"), dict):
        raise TrustFreshnessError(
            "trust artifact freshness policy missing artifact_kinds"
        )
    return data


def _kind_policy(
    policy: Mapping[str, Any], kind: str
) -> Mapping[str, Any]:
    kinds = policy.get("artifact_kinds") or {}
    spec = kinds.get(kind)
    if not isinstance(spec, Mapping):
        # Default conservative budget for kinds not explicitly listed.
        return policy.get("default_kind_budget") or {
            "max_age_days": 7,
            "require_digest": True,
            "allow_unknown": False,
        }
    return spec


def _derive_inputs_for_digest(
    artifact: Mapping[str, Any]
) -> Optional[Any]:
    """Return the producer-side payload to hash, when present.

    Producers may declare any of the following keys (checked in order):
      - ``producer_inputs``      — explicit canonical inputs
      - ``producer_input_payload``
      - ``inputs_for_digest``
    """
    for key in ("producer_inputs", "producer_input_payload", "inputs_for_digest"):
        if key in artifact:
            return artifact[key]
    return None


def _audit_one(
    *,
    kind: str,
    artifact: Optional[Mapping[str, Any]],
    source_artifacts: Optional[Mapping[str, Mapping[str, Any]]],
    policy: Mapping[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    """Audit a single trust artifact and return its per-item record."""
    spec = _kind_policy(policy, kind)
    max_age_days = float(spec.get("max_age_days", 7))
    allow_unknown = bool(spec.get("allow_unknown", False))

    if artifact is None:
        return {
            "kind": kind,
            "artifact_id": None,
            "status": "stale",
            "canonical_reason": "TRUST_FRESHNESS_MISSING_ARTIFACT",
            "detail": f"no {kind} artifact supplied",
        }

    artifact_id = (
        artifact.get("artifact_id")
        or artifact.get("index_id")
        or artifact.get("bundle_id")
        or artifact.get("policy_id")
        or artifact.get("summary_id")
        or artifact.get("trace_id")
    )

    # 1. producer_input_digest check (strongest)
    declared_input_digest = artifact.get("producer_input_digest")
    inputs = _derive_inputs_for_digest(artifact)
    if isinstance(declared_input_digest, str) and declared_input_digest.strip():
        if inputs is None:
            return {
                "kind": kind,
                "artifact_id": artifact_id,
                "status": "unknown",
                "canonical_reason": "TRUST_FRESHNESS_UNKNOWN_NO_PROOF",
                "detail": (
                    "producer_input_digest declared but producer_inputs/"
                    "producer_input_payload/inputs_for_digest absent"
                ),
            }
        recomputed = _canonical_hash(inputs)
        if recomputed != declared_input_digest:
            return {
                "kind": kind,
                "artifact_id": artifact_id,
                "status": "stale",
                "canonical_reason": "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH",
                "detail": (
                    f"producer_input_digest mismatch: declared="
                    f"{declared_input_digest[:12]}…, recomputed="
                    f"{recomputed[:12]}…"
                ),
                "declared_input_digest": declared_input_digest,
                "recomputed_input_digest": recomputed,
            }
        # Digest matches — strong proof, but still verify source digest if claimed.
    # 2. source_artifact_digest check
    declared_source_digest = artifact.get("source_artifact_digest")
    declared_source_id = artifact.get("source_artifact_id")
    if (
        isinstance(declared_source_digest, str)
        and declared_source_digest.strip()
        and isinstance(declared_source_id, str)
        and declared_source_id.strip()
    ):
        store = source_artifacts or {}
        source_obj = store.get(declared_source_id)
        if source_obj is None:
            return {
                "kind": kind,
                "artifact_id": artifact_id,
                "status": "unknown",
                "canonical_reason": "TRUST_FRESHNESS_UNKNOWN_NO_PROOF",
                "detail": (
                    f"source_artifact_id={declared_source_id!r} not in "
                    "source_artifacts"
                ),
            }
        actual = _canonical_hash(source_obj)
        if actual != declared_source_digest:
            return {
                "kind": kind,
                "artifact_id": artifact_id,
                "status": "stale",
                "canonical_reason": "TRUST_FRESHNESS_STALE_SOURCE_DIGEST_MISMATCH",
                "detail": (
                    f"source_artifact_digest mismatch: declared="
                    f"{declared_source_digest[:12]}…, recomputed="
                    f"{actual[:12]}…"
                ),
                "declared_source_digest": declared_source_digest,
                "recomputed_source_digest": actual,
            }

    # 3. timestamp budget — only as a freshness signal when no digest available.
    declared_ts = artifact.get("generated_at") or artifact.get("checked_at")
    parsed_ts = _parse_iso(declared_ts) if isinstance(declared_ts, str) else None

    has_strong_proof = (
        isinstance(declared_input_digest, str)
        and bool(declared_input_digest.strip())
    ) or (
        isinstance(declared_source_digest, str)
        and bool(declared_source_digest.strip())
    )

    if has_strong_proof:
        # Digest signal exists and (above) matched. Status is current.
        # Timestamp, if present, is recorded but not a gate.
        return {
            "kind": kind,
            "artifact_id": artifact_id,
            "status": "current",
            "canonical_reason": "TRUST_FRESHNESS_OK",
            "detail": "digest proof matches",
            "generated_at": declared_ts if isinstance(declared_ts, str) else None,
        }

    # No digest available — fall back to timestamp budget.
    if parsed_ts is not None:
        age_days = (now - parsed_ts).total_seconds() / 86400.0
        if age_days > max_age_days:
            return {
                "kind": kind,
                "artifact_id": artifact_id,
                "status": "stale",
                "canonical_reason": "TRUST_FRESHNESS_STALE_TIMESTAMP",
                "detail": (
                    f"age {age_days:.2f}d > max_age_days={max_age_days}"
                ),
                "generated_at": declared_ts,
                "age_days": age_days,
            }
        return {
            "kind": kind,
            "artifact_id": artifact_id,
            "status": "current",
            "canonical_reason": "TRUST_FRESHNESS_OK",
            "detail": (
                f"timestamp within budget: age {age_days:.2f}d ≤ "
                f"{max_age_days}d"
            ),
            "generated_at": declared_ts,
            "age_days": age_days,
        }

    # No digest and no timestamp at all. Fail closed unless the policy
    # explicitly opts the kind out via ``allow_unknown``.
    if allow_unknown:
        return {
            "kind": kind,
            "artifact_id": artifact_id,
            "status": "current",
            "canonical_reason": "TRUST_FRESHNESS_OK",
            "detail": "policy.allow_unknown=true; treated as current",
        }
    return {
        "kind": kind,
        "artifact_id": artifact_id,
        "status": "unknown",
        "canonical_reason": "TRUST_FRESHNESS_UNKNOWN_NO_PROOF",
        "detail": (
            "no producer_input_digest, source_artifact_digest, or generated_at"
        ),
    }


def audit_trust_artifact_freshness(
    *,
    audit_id: str,
    artifacts: Mapping[str, Optional[Mapping[str, Any]]],
    source_artifacts: Optional[Mapping[str, Mapping[str, Any]]] = None,
    policy: Optional[Mapping[str, Any]] = None,
    audit_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Audit the freshness of a bundle of trust artifacts.

    Parameters
    ----------
    audit_id:
        Stable id for the audit record.
    artifacts:
        Mapping of trust artifact kind → artifact payload (or ``None`` if
        the producer claims the artifact is absent). Recognised kinds are
        listed in ``REQUIRED_TRUST_ARTIFACT_KINDS``; unknown kinds are
        accepted and audited under the policy's default budget.
    source_artifacts:
        Optional mapping of artifact_id → upstream artifact payload, used to
        verify ``source_artifact_digest`` claims.
    policy:
        Optional policy override; defaults to
        ``contracts/governance/trust_artifact_freshness_policy.json``.
    audit_timestamp:
        Optional override for the audit clock; a zero-offset timestamp
        string (e.g. ``"2026-04-27T12:00:00Z"``). Defaults to the current
        zero-offset time.

    Returns a ``trust_artifact_freshness_audit`` artifact:
        {
          "artifact_type": "trust_artifact_freshness_audit",
          "audit_id": str,
          "status": "current"|"stale",
          "canonical_reason": canonical reason code,
          "stale_kinds": [str,...],
          "unknown_kinds": [str,...],
          "items": [per-item records],
          "human_readable": str,
        }
    """
    if not isinstance(audit_id, str) or not audit_id.strip():
        raise TrustFreshnessError("audit_id must be a non-empty string")
    if not isinstance(artifacts, Mapping):
        raise TrustFreshnessError("artifacts must be a mapping")

    pol = dict(policy) if policy is not None else load_trust_artifact_freshness_policy()
    now = (
        _parse_iso(audit_timestamp)
        if audit_timestamp
        else datetime.now(timezone.utc)
    )
    if now is None:
        raise TrustFreshnessError(
            f"audit_timestamp could not be parsed: {audit_timestamp!r}"
        )

    items: List[Dict[str, Any]] = []
    for kind in REQUIRED_TRUST_ARTIFACT_KINDS:
        item = _audit_one(
            kind=kind,
            artifact=artifacts.get(kind),
            source_artifacts=source_artifacts,
            policy=pol,
            now=now,
        )
        items.append(item)

    # Honor extra kinds the caller passed; they get audited but do not gate.
    extra_kinds = [k for k in artifacts if k not in REQUIRED_TRUST_ARTIFACT_KINDS]
    for kind in extra_kinds:
        item = _audit_one(
            kind=kind,
            artifact=artifacts.get(kind),
            source_artifacts=source_artifacts,
            policy=pol,
            now=now,
        )
        item["non_required"] = True
        items.append(item)

    stale_kinds = [it["kind"] for it in items if it["status"] == "stale"]
    unknown_kinds = [it["kind"] for it in items if it["status"] == "unknown"]
    overall_status = "current"
    canonical_reason = "TRUST_FRESHNESS_OK"
    blocking_item: Optional[Dict[str, Any]] = None
    for it in items:
        if it.get("non_required"):
            continue
        if it["status"] in {"stale", "unknown"}:
            overall_status = "stale"
            canonical_reason = it["canonical_reason"]
            blocking_item = it
            break

    human_lines = [
        f"TRUST ARTIFACT FRESHNESS AUDIT — audit_id={audit_id} now={now.isoformat()}",
        f"overall_status: {overall_status}",
        f"canonical_reason: {canonical_reason}",
    ]
    if blocking_item is not None:
        human_lines.append(
            f"first_blocking_kind: {blocking_item['kind']} "
            f"(detail: {blocking_item['detail']})"
        )
    human_lines.append("items:")
    for it in items:
        human_lines.append(
            f"  - kind={it['kind']:<32} status={it['status']:<8} "
            f"reason={it['canonical_reason']:<48} id={it.get('artifact_id') or '-'}"
        )

    return {
        "artifact_type": "trust_artifact_freshness_audit",
        "schema_version": "1.0.0",
        "audit_id": audit_id,
        "status": overall_status,
        "canonical_reason": canonical_reason,
        "stale_kinds": stale_kinds,
        "unknown_kinds": unknown_kinds,
        "items": items,
        "human_readable": "\n".join(human_lines),
    }


__all__ = [
    "CANONICAL_FRESHNESS_REASON_CODES",
    "REQUIRED_TRUST_ARTIFACT_KINDS",
    "TrustFreshnessError",
    "audit_trust_artifact_freshness",
    "load_trust_artifact_freshness_policy",
]
