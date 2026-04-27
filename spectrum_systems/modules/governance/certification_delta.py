"""GOV: Certification delta proof (NT-19..21).

Build a deterministic, reference-only delta between two certification
evidence indexes (or two loop proof bundles). The delta surfaces:

  * added evidence refs
  * removed evidence refs
  * changed evidence digests (same ref slot, different artifact id)
  * changed evidence statuses
  * changed canonical reason categories
  * changed owning systems
  * unchanged refs
  * an overall delta_risk: ``none`` | ``low`` | ``medium`` | ``high``

This module does not own decision authority. It produces a delta artifact
that downstream owners (CDE/SEL) and the operator triage CLI can consume.

Hidden-delta defenses:
  * a swap of an evidence ref while keeping its status reported pass is
    flagged as ``changed_digest`` even though both readings looked healthy.
  * silent removal of stale evidence (ref present in previous, absent in
    current, with no explicit explanation) is flagged.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


CANONICAL_DELTA_REASON_CODES = (
    "CERTIFICATION_DELTA_OK",
    "CERTIFICATION_DELTA_ADDED_UNEXPLAINED",
    "CERTIFICATION_DELTA_REMOVED_UNEXPLAINED",
    "CERTIFICATION_DELTA_CHANGED_DIGEST",
    "CERTIFICATION_DELTA_CHANGED_STATUS",
    "CERTIFICATION_DELTA_CHANGED_REASON",
    "CERTIFICATION_DELTA_CHANGED_OWNER",
    "CERTIFICATION_DELTA_UNKNOWN_BASELINE",
)


DELTA_RISK_LEVELS = ("none", "low", "medium", "high")


REQUIRED_EVIDENCE_KEYS = (
    "eval_summary_ref",
    "lineage_summary_ref",
    "replay_summary_ref",
    "control_decision_ref",
    "enforcement_action_ref",
    "authority_shape_preflight_ref",
    "registry_validation_ref",
    "artifact_tier_validation_ref",
    "failure_trace_ref",
)


class CertificationDeltaError(ValueError):
    """Raised when a certification delta cannot be deterministically built."""


def _refs_of(index: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    if "references" in index and isinstance(index["references"], Mapping):
        refs = index["references"]
    else:
        refs = index
    out: Dict[str, Optional[str]] = {}
    for k in REQUIRED_EVIDENCE_KEYS:
        v = refs.get(k) if isinstance(refs, Mapping) else None
        out[k] = v if isinstance(v, str) and v.strip() else None
    return out


def _status_of(index: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(index, Mapping):
        return ""
    return str(index.get("status") or "").lower()


def _reason_of(index: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(index, Mapping):
        return ""
    return str(index.get("blocking_reason_canonical") or "").upper()


def _owner_of(index: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(index, Mapping):
        return ""
    return str(index.get("owning_system") or index.get("owner_system") or "")


def _explanations_to_set(
    explained: Optional[Iterable[Mapping[str, Any]]],
) -> Tuple[set, set]:
    """Convert an explanations list into (added_keys, removed_keys) sets."""
    added: set = set()
    removed: set = set()
    if not explained:
        return added, removed
    for ex in explained:
        if not isinstance(ex, Mapping):
            continue
        kind = str(ex.get("kind") or "").lower()
        ref = str(ex.get("ref_key") or "")
        if kind == "added" and ref:
            added.add(ref)
        elif kind == "removed" and ref:
            removed.add(ref)
    return added, removed


def build_certification_delta_index(
    *,
    delta_id: str,
    trace_id: str,
    previous_evidence_index: Optional[Mapping[str, Any]],
    current_evidence_index: Mapping[str, Any],
    explanations: Optional[Iterable[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a certification delta artifact.

    ``explanations`` is an optional list of mappings with the shape::

        {"kind": "added"|"removed", "ref_key": "<name>",
         "rationale": "<short, traceable reason>"}

    Each entry tells the delta builder that an addition or removal at the
    referenced slot has been explicitly justified — otherwise it is
    flagged as unexplained.
    """
    if not isinstance(delta_id, str) or not delta_id.strip():
        raise CertificationDeltaError("delta_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise CertificationDeltaError("trace_id must be a non-empty string")
    if not isinstance(current_evidence_index, Mapping):
        raise CertificationDeltaError("current_evidence_index must be a mapping")

    if previous_evidence_index is None:
        return {
            "artifact_type": "certification_delta_index",
            "schema_version": "1.0.0",
            "delta_id": delta_id,
            "trace_id": trace_id,
            "delta_risk": "high",
            "reason_code": "CERTIFICATION_DELTA_UNKNOWN_BASELINE",
            "blocking_reasons": [
                "no previous certification evidence index supplied; baseline unknown"
            ],
            "added": [],
            "removed": [],
            "changed_digest": [],
            "changed_status": [],
            "changed_reason": [],
            "changed_owner": [],
            "unchanged": [],
        }

    prev_refs = _refs_of(previous_evidence_index)
    curr_refs = _refs_of(current_evidence_index)
    explained_added, explained_removed = _explanations_to_set(explanations)

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    changed_digest: List[Dict[str, Any]] = []
    unchanged: List[str] = []

    for k in REQUIRED_EVIDENCE_KEYS:
        p = prev_refs.get(k)
        c = curr_refs.get(k)
        if p == c and p is not None:
            unchanged.append(k)
        elif p is None and c is not None:
            added.append(
                {
                    "ref_key": k,
                    "current_ref": c,
                    "explained": k in explained_added,
                }
            )
        elif p is not None and c is None:
            removed.append(
                {
                    "ref_key": k,
                    "previous_ref": p,
                    "explained": k in explained_removed,
                }
            )
        elif p != c:
            changed_digest.append(
                {
                    "ref_key": k,
                    "previous_ref": p,
                    "current_ref": c,
                }
            )

    prev_status = _status_of(previous_evidence_index)
    curr_status = _status_of(current_evidence_index)
    changed_status: List[Dict[str, Any]] = []
    if prev_status != curr_status:
        changed_status.append(
            {"previous": prev_status, "current": curr_status}
        )

    prev_reason = _reason_of(previous_evidence_index)
    curr_reason = _reason_of(current_evidence_index)
    changed_reason: List[Dict[str, Any]] = []
    if prev_reason != curr_reason:
        changed_reason.append(
            {"previous": prev_reason or None, "current": curr_reason or None}
        )

    prev_owner = _owner_of(previous_evidence_index)
    curr_owner = _owner_of(current_evidence_index)
    changed_owner: List[Dict[str, Any]] = []
    if prev_owner != curr_owner:
        changed_owner.append(
            {"previous": prev_owner or None, "current": curr_owner or None}
        )

    blocking: List[str] = []
    reason_code = "CERTIFICATION_DELTA_OK"

    def _record(reason: str, why: str) -> None:
        nonlocal reason_code
        blocking.append(why)
        if reason_code == "CERTIFICATION_DELTA_OK":
            reason_code = reason

    if changed_digest:
        keys = ", ".join(d["ref_key"] for d in changed_digest)
        _record(
            "CERTIFICATION_DELTA_CHANGED_DIGEST",
            f"evidence digest changed at: {keys}",
        )
    unexplained_added = [a for a in added if not a["explained"]]
    unexplained_removed = [r for r in removed if not r["explained"]]
    if unexplained_added:
        _record(
            "CERTIFICATION_DELTA_ADDED_UNEXPLAINED",
            "added evidence without explanation: "
            + ", ".join(a["ref_key"] for a in unexplained_added),
        )
    if unexplained_removed:
        _record(
            "CERTIFICATION_DELTA_REMOVED_UNEXPLAINED",
            "removed evidence without explanation: "
            + ", ".join(r["ref_key"] for r in unexplained_removed),
        )
    if changed_status:
        _record(
            "CERTIFICATION_DELTA_CHANGED_STATUS",
            f"certification status changed: "
            f"{prev_status or '-'} -> {curr_status or '-'}",
        )
    if changed_reason:
        _record(
            "CERTIFICATION_DELTA_CHANGED_REASON",
            f"canonical blocking reason changed: "
            f"{prev_reason or '-'} -> {curr_reason or '-'}",
        )
    if changed_owner:
        _record(
            "CERTIFICATION_DELTA_CHANGED_OWNER",
            f"owning system changed: {prev_owner or '-'} -> {curr_owner or '-'}",
        )

    delta_risk = "none"
    if blocking:
        # any unexplained add/remove or digest change is at least medium;
        # changed status/reason/owner is high
        if changed_status or changed_reason or changed_owner:
            delta_risk = "high"
        elif changed_digest or unexplained_added or unexplained_removed:
            delta_risk = "medium"
        else:
            delta_risk = "low"

    return {
        "artifact_type": "certification_delta_index",
        "schema_version": "1.0.0",
        "delta_id": delta_id,
        "trace_id": trace_id,
        "delta_risk": delta_risk,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "added": added,
        "removed": removed,
        "changed_digest": changed_digest,
        "changed_status": changed_status,
        "changed_reason": changed_reason,
        "changed_owner": changed_owner,
        "unchanged": unchanged,
    }


__all__ = [
    "CANONICAL_DELTA_REASON_CODES",
    "DELTA_RISK_LEVELS",
    "REQUIRED_EVIDENCE_KEYS",
    "CertificationDeltaError",
    "build_certification_delta_index",
]
