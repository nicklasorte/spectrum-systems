"""OC-13..15: Work selection signal (non-owning recommendation surface).

Recommends the next work item from a finite list of justification kinds:

    current_bottleneck | proof_delta | failing_trust_regression |
    weak_trust_regression | dashboard_proof_mismatch |
    measurable_signal_gap

Attractive but unsupported expansion work (``expansion_unsupported``,
``low_trust``) is rejected: such candidates always score below the
acceptance threshold and the record records the rejection reason.

Scoring (deterministic):

  * ``failing_trust_regression``  — 100
  * ``current_bottleneck``        — 80
  * ``dashboard_proof_mismatch``  — 70
  * ``proof_delta``               — 60
  * ``weak_trust_regression``     — 50
  * ``measurable_signal_gap``     — 40
  * ``expansion_unsupported``     — 0   (rejected)
  * ``low_trust``                 — 0   (rejected)

A candidate is accepted only if its justification kind is in the
"supported" set AND its evidence_ref is not None. Ties break by
candidate work_item_id ascending. If no candidates are accepted, the
record reports ``selection_status = no_recommendation``.

Module is non-owning: it only emits an advisory work-selection signal
for downstream readiness packaging. CDE retains final transition
decision responsibility. Readiness packaging remains evidence-only and
cannot authorize progression.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence


SUPPORTED_JUSTIFICATIONS = frozenset(
    {
        "current_bottleneck",
        "proof_delta",
        "failing_trust_regression",
        "weak_trust_regression",
        "dashboard_proof_mismatch",
        "measurable_signal_gap",
    }
)


REJECTED_JUSTIFICATIONS = frozenset(
    {
        "expansion_unsupported",
        "low_trust",
    }
)


JUSTIFICATION_SCORES: Dict[str, float] = {
    "failing_trust_regression": 100.0,
    "current_bottleneck": 80.0,
    "dashboard_proof_mismatch": 70.0,
    "proof_delta": 60.0,
    "weak_trust_regression": 50.0,
    "measurable_signal_gap": 40.0,
    "expansion_unsupported": 0.0,
    "low_trust": 0.0,
}


CANONICAL_REASON_CODES = frozenset(
    {
        "WORK_SELECTION_OK",
        "WORK_SELECTION_NO_RECOMMENDATION",
        "WORK_SELECTION_BLOCKED",
        "WORK_SELECTION_UNKNOWN",
        "WORK_SELECTION_REJECTED_EXPANSION",
        "WORK_SELECTION_REJECTED_LOW_TRUST",
        "WORK_SELECTION_MISSING_EVIDENCE",
    }
)


class WorkSelectionError(ValueError):
    """Raised when the work selection record cannot be deterministically built."""


def build_work_selection_record(
    *,
    record_id: str,
    audit_timestamp: str,
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(record_id, str) or not record_id.strip():
        raise WorkSelectionError("record_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise WorkSelectionError("audit_timestamp must be a non-empty string")

    out_candidates: List[Dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, Mapping):
            continue
        wid = c.get("work_item_id")
        if not isinstance(wid, str) or not wid.strip():
            continue
        kind = c.get("justification_kind")
        if not isinstance(kind, str):
            kind = ""
        evidence_ref = c.get("evidence_ref")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            evidence_ref = None
        if kind in REJECTED_JUSTIFICATIONS:
            reason = (
                "WORK_SELECTION_REJECTED_EXPANSION"
                if kind == "expansion_unsupported"
                else "WORK_SELECTION_REJECTED_LOW_TRUST"
            )
            out_candidates.append(
                {
                    "work_item_id": wid,
                    "justification_kind": kind,
                    "evidence_ref": evidence_ref,
                    "score": 0.0,
                    "accepted": False,
                    "reason_code": reason,
                }
            )
            continue
        if kind not in SUPPORTED_JUSTIFICATIONS:
            out_candidates.append(
                {
                    "work_item_id": wid,
                    "justification_kind": kind or "unknown",
                    "evidence_ref": evidence_ref,
                    "score": 0.0,
                    "accepted": False,
                    "reason_code": "WORK_SELECTION_BLOCKED",
                }
            )
            continue
        if evidence_ref is None:
            out_candidates.append(
                {
                    "work_item_id": wid,
                    "justification_kind": kind,
                    "evidence_ref": None,
                    "score": 0.0,
                    "accepted": False,
                    "reason_code": "WORK_SELECTION_MISSING_EVIDENCE",
                }
            )
            continue
        score = JUSTIFICATION_SCORES.get(kind, 0.0)
        out_candidates.append(
            {
                "work_item_id": wid,
                "justification_kind": kind,
                "evidence_ref": evidence_ref,
                "score": score,
                "accepted": True,
                "reason_code": "WORK_SELECTION_OK",
            }
        )

    accepted = [c for c in out_candidates if c["accepted"]]
    if accepted:
        # rank by score desc, work_item_id asc
        accepted_sorted = sorted(
            accepted, key=lambda c: (-c["score"], c["work_item_id"])
        )
        recommended = accepted_sorted[0]["work_item_id"]
        selection_status = "selected"
        reason_code = "WORK_SELECTION_OK"
    else:
        recommended = None
        if out_candidates:
            selection_status = "no_recommendation"
            reason_code = "WORK_SELECTION_NO_RECOMMENDATION"
        else:
            selection_status = "unknown"
            reason_code = "WORK_SELECTION_UNKNOWN"

    return {
        "artifact_type": "work_selection_record",
        "schema_version": "1.0.0",
        "record_id": record_id,
        "audit_timestamp": audit_timestamp,
        "candidates": out_candidates,
        "recommended_work_item_id": recommended,
        "selection_status": selection_status,
        "reason_code": reason_code,
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
            "not_promotion_authority",
            "not_enforcement_authority",
        ],
    }
