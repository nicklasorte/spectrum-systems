"""OC-01..03: Proof intake index.

Selects the latest valid proof artifact deterministically across the proof
families produced by NS-/NT-/NX- batches:

  - ``loop_proof_bundle``
  - ``certification_delta_proof``
  - ``trust_regression_result``
  - ``cli_summary``
  - ``dashboard_proof_ref``

The index is a non-owning support seam. It does NOT issue control or
certification verdicts. It records:

  * which artifact was selected per kind
  * why (digest match, freshest timestamp)
  * which candidates were rejected (stale, duplicate, conflicting)
  * a finite reason code per selection
  * an overall status (``ok`` / ``degraded`` / ``blocked``)

Selection rules (deterministic, fail-closed):

  1. If no candidates are supplied for a required kind, the kind is
     ``missing`` with reason ``PROOF_INTAKE_MISSING`` and contributes
     to ``blocked`` overall.
  2. If a single candidate is supplied, it is selected unless its
     declared digest does not match the recomputed digest of its
     ``producer_inputs`` (then ``stale`` with
     ``PROOF_INTAKE_STALE_DIGEST_MISMATCH``).
  3. If multiple candidates share the same ``artifact_id``, that is a
     duplicate; reason ``PROOF_INTAKE_DUPLICATE``.
  4. If multiple candidates with different ``artifact_id`` declare the
     same kind and disagree on the producer_input_digest, that is a
     conflict; reason ``PROOF_INTAKE_CONFLICT``. The intake refuses to
     pick a winner and the kind contributes to ``blocked``.
  5. If all candidates for a kind agree on digest but differ on
     ``generated_at``, the latest valid (non-stale) candidate is
     selected and the others are rejected with
     ``PROOF_INTAKE_SUPERSEDED``.

The intake never silently falls back to the older of two conflicting
proofs and never lets a stale proof win on timestamp alone.

Module is non-owning. This module only indexes proof inputs and does
not execute actions, alter state, package certification evidence, or
issue closure or transition responsibilities. References downstream
action evidence when present.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


REQUIRED_PROOF_KINDS = (
    "loop_proof_bundle",
    "certification_delta_proof",
    "trust_regression_result",
    "cli_summary",
    "dashboard_proof_ref",
)


CANONICAL_INTAKE_REASON_CODES = frozenset(
    {
        "PROOF_INTAKE_OK",
        "PROOF_INTAKE_MISSING",
        "PROOF_INTAKE_STALE_DIGEST_MISMATCH",
        "PROOF_INTAKE_STALE_TIMESTAMP",
        "PROOF_INTAKE_DUPLICATE",
        "PROOF_INTAKE_CONFLICT",
        "PROOF_INTAKE_SUPERSEDED",
        "PROOF_INTAKE_UNKNOWN",
    }
)


class ProofIntakeError(ValueError):
    """Raised when the proof intake index cannot be deterministically built."""


def _digest_of(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate_digest(candidate: Mapping[str, Any]) -> Optional[str]:
    declared = candidate.get("producer_input_digest")
    if isinstance(declared, str) and declared.strip():
        return declared
    inputs = candidate.get("producer_inputs")
    if inputs is None:
        return None
    return _digest_of(inputs)


def _is_stale(candidate: Mapping[str, Any]) -> bool:
    declared = candidate.get("producer_input_digest")
    inputs = candidate.get("producer_inputs")
    if not isinstance(declared, str) or not declared.strip():
        return False
    if inputs is None:
        return False
    recomputed = _digest_of(inputs)
    return recomputed != declared


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    for key in ("artifact_id", "id"):
        v = candidate.get(key)
        if isinstance(v, str) and v.strip():
            return v
    raise ProofIntakeError("proof candidate missing artifact_id")


def _classify_kind(
    kind: str, candidates: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    if not candidates:
        return {
            "kind": kind,
            "selected_artifact_id": None,
            "selected_digest": None,
            "selected_generated_at": None,
            "candidate_count": 0,
            "selection_status": "missing",
            "reason_code": "PROOF_INTAKE_MISSING",
            "rejected_candidates": [],
        }

    # detect duplicates (same artifact_id appearing twice)
    seen_ids: Dict[str, int] = {}
    for c in candidates:
        cid = _candidate_id(c)
        seen_ids[cid] = seen_ids.get(cid, 0) + 1
    duplicates = [cid for cid, n in seen_ids.items() if n > 1]
    if duplicates:
        return {
            "kind": kind,
            "selected_artifact_id": None,
            "selected_digest": None,
            "selected_generated_at": None,
            "candidate_count": len(candidates),
            "selection_status": "duplicate",
            "reason_code": "PROOF_INTAKE_DUPLICATE",
            "rejected_candidates": [
                {"artifact_id": cid, "reason_code": "PROOF_INTAKE_DUPLICATE"}
                for cid in duplicates
            ],
        }

    # detect stale candidates (declared digest but does not match recomputed)
    stale_ids = [
        _candidate_id(c) for c in candidates if _is_stale(c)
    ]
    fresh = [c for c in candidates if not _is_stale(c)]
    if not fresh:
        return {
            "kind": kind,
            "selected_artifact_id": None,
            "selected_digest": None,
            "selected_generated_at": None,
            "candidate_count": len(candidates),
            "selection_status": "stale",
            "reason_code": "PROOF_INTAKE_STALE_DIGEST_MISMATCH",
            "rejected_candidates": [
                {
                    "artifact_id": sid,
                    "reason_code": "PROOF_INTAKE_STALE_DIGEST_MISMATCH",
                }
                for sid in stale_ids
            ],
        }

    # detect conflict among fresh candidates: differing artifact_ids
    # with differing producer_input_digests.
    digests = {
        _candidate_digest(c) or "" for c in fresh
    }
    if len(fresh) > 1 and len(digests) > 1:
        return {
            "kind": kind,
            "selected_artifact_id": None,
            "selected_digest": None,
            "selected_generated_at": None,
            "candidate_count": len(candidates),
            "selection_status": "conflict",
            "reason_code": "PROOF_INTAKE_CONFLICT",
            "rejected_candidates": [
                {
                    "artifact_id": _candidate_id(c),
                    "reason_code": "PROOF_INTAKE_CONFLICT",
                }
                for c in fresh
            ],
        }

    # All fresh candidates agree on digest. Pick the one with the
    # latest generated_at timestamp deterministically; ties break by
    # artifact_id ascending.
    def _key(c: Mapping[str, Any]):
        ts = c.get("generated_at") or ""
        return (str(ts), _candidate_id(c))

    sorted_fresh = sorted(fresh, key=_key, reverse=True)
    chosen = sorted_fresh[0]
    rejected: List[Dict[str, str]] = []
    for sid in stale_ids:
        rejected.append(
            {
                "artifact_id": sid,
                "reason_code": "PROOF_INTAKE_STALE_DIGEST_MISMATCH",
            }
        )
    for c in sorted_fresh[1:]:
        rejected.append(
            {
                "artifact_id": _candidate_id(c),
                "reason_code": "PROOF_INTAKE_SUPERSEDED",
            }
        )

    return {
        "kind": kind,
        "selected_artifact_id": _candidate_id(chosen),
        "selected_digest": _candidate_digest(chosen),
        "selected_generated_at": chosen.get("generated_at"),
        "candidate_count": len(candidates),
        "selection_status": "selected",
        "reason_code": "PROOF_INTAKE_OK",
        "rejected_candidates": rejected,
    }


def build_proof_intake_index(
    *,
    intake_id: str,
    audit_timestamp: str,
    candidates_by_kind: Mapping[str, Iterable[Mapping[str, Any]]],
    required_kinds: Sequence[str] = REQUIRED_PROOF_KINDS,
) -> Dict[str, Any]:
    if not isinstance(intake_id, str) or not intake_id.strip():
        raise ProofIntakeError("intake_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise ProofIntakeError("audit_timestamp must be a non-empty string")

    selections: Dict[str, Any] = {}
    blocked = False
    degraded = False
    blocking_reason: Optional[str] = None

    for kind in required_kinds:
        raw_candidates = list(candidates_by_kind.get(kind, []) or [])
        result = _classify_kind(kind, raw_candidates)
        if result["reason_code"] not in CANONICAL_INTAKE_REASON_CODES:
            raise ProofIntakeError(
                f"non-canonical reason_code emitted: {result['reason_code']}"
            )
        selections[kind] = result
        status = result["selection_status"]
        if status in ("missing", "stale", "duplicate", "conflict"):
            blocked = True
            blocking_reason = blocking_reason or result["reason_code"]
        elif status not in ("selected",):
            degraded = True

    if blocked:
        overall_status = "blocked"
        overall_reason = blocking_reason or "PROOF_INTAKE_UNKNOWN"
    elif degraded:
        overall_status = "degraded"
        overall_reason = "PROOF_INTAKE_UNKNOWN"
    else:
        overall_status = "ok"
        overall_reason = "PROOF_INTAKE_OK"

    return {
        "artifact_type": "proof_intake_index",
        "schema_version": "1.0.0",
        "intake_id": intake_id,
        "audit_timestamp": audit_timestamp,
        "selections": selections,
        "overall_status": overall_status,
        "reason_code": overall_reason,
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_promotion_authority",
            "not_enforcement_authority",
        ],
    }
