"""OC-19..21: Cleanup candidate report (advisory only — never deletes).

Classifies repo artifacts as one of:

    keep | regenerate | candidate_archive | never_delete | unknown_blocked

The report is advisory only. It NEVER deletes artifacts and never
authorizes deletion. Required proof evidence is forced to
``never_delete``. Ambiguous classifications are forced to
``unknown_blocked`` so downstream operators cannot accidentally archive
something the closure bundle still needs.

Module is non-owning. Canonical authority unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set


CANONICAL_REASON_CODES = frozenset(
    {
        "CLEANUP_KEEP_DEFAULT",
        "CLEANUP_REGENERATE_REPRODUCIBLE",
        "CLEANUP_CANDIDATE_ARCHIVE_AGED",
        "CLEANUP_NEVER_DELETE_REQUIRED_PROOF",
        "CLEANUP_NEVER_DELETE_CANONICAL_OWNER",
        "CLEANUP_UNKNOWN_BLOCKED_AMBIGUOUS",
        "CLEANUP_UNKNOWN_BLOCKED_NO_INPUT",
    }
)


# Required proof evidence kinds — these are forced to never_delete.
REQUIRED_PROOF_EVIDENCE_KINDS = frozenset(
    {
        "loop_proof_bundle",
        "certification_evidence_index",
        "certification_delta_proof",
        "trust_regression_pack",
        "failure_trace",
        "replay_lineage_join_summary",
        "artifact_tier_policy",
        "reason_code_alias_map",
        "slo_signal_policy",
        "operational_closure_bundle",
        "closure_decision_packet",
        "proof_intake_index",
        "dashboard_truth_projection",
        "bottleneck_classification",
    }
)


# Canonical owner path roots that must never be auto-archived even
# when the artifact_kind is unknown.
CANONICAL_OWNER_ROOTS = (
    "spectrum_systems/modules/runtime/",
    "spectrum_systems/modules/governance/",
    "contracts/governance/",
    "contracts/schemas/",
    "docs/architecture/",
)


VALID_CLASSIFICATIONS = frozenset(
    {"keep", "regenerate", "candidate_archive", "never_delete", "unknown_blocked"}
)


class CleanupCandidateError(ValueError):
    """Raised when the cleanup report cannot be deterministically constructed."""


def _is_required_proof(candidate: Mapping[str, Any]) -> bool:
    kind = candidate.get("artifact_kind")
    if isinstance(kind, str) and kind in REQUIRED_PROOF_EVIDENCE_KINDS:
        return True
    role = candidate.get("evidence_role")
    if isinstance(role, str) and role == "required_proof_evidence":
        return True
    path = candidate.get("artifact_path")
    if isinstance(path, str):
        for root in CANONICAL_OWNER_ROOTS:
            if path.startswith(root):
                return True
    return False


def _classify_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    path = candidate.get("artifact_path")
    if not isinstance(path, str) or not path.strip():
        raise CleanupCandidateError("candidate missing artifact_path")
    kind = candidate.get("artifact_kind") if isinstance(
        candidate.get("artifact_kind"), str
    ) else None
    proposed = candidate.get("proposed_classification")
    if not isinstance(proposed, str):
        proposed = None

    if _is_required_proof(candidate):
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "never_delete",
            "reason_code": "CLEANUP_NEVER_DELETE_REQUIRED_PROOF",
            "evidence_role": "required_proof_evidence",
        }

    # Treat any candidate flagged as ambiguous, or whose proposed
    # classification falls outside the valid set, as unknown_blocked.
    if proposed in (None, "", "unknown"):
        # If we have no proposal, default to keep.
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "keep",
            "reason_code": "CLEANUP_KEEP_DEFAULT",
            "evidence_role": candidate.get("evidence_role")
            if isinstance(candidate.get("evidence_role"), str)
            else "unknown",
        }
    if proposed not in VALID_CLASSIFICATIONS:
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "unknown_blocked",
            "reason_code": "CLEANUP_UNKNOWN_BLOCKED_AMBIGUOUS",
            "evidence_role": "unknown",
        }
    if proposed == "regenerate":
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "regenerate",
            "reason_code": "CLEANUP_REGENERATE_REPRODUCIBLE",
            "evidence_role": candidate.get("evidence_role")
            if isinstance(candidate.get("evidence_role"), str)
            else "supporting_proof_evidence",
        }
    if proposed == "candidate_archive":
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "candidate_archive",
            "reason_code": "CLEANUP_CANDIDATE_ARCHIVE_AGED",
            "evidence_role": candidate.get("evidence_role")
            if isinstance(candidate.get("evidence_role"), str)
            else "advisory",
        }
    if proposed == "never_delete":
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "never_delete",
            "reason_code": "CLEANUP_NEVER_DELETE_CANONICAL_OWNER",
            "evidence_role": candidate.get("evidence_role")
            if isinstance(candidate.get("evidence_role"), str)
            else "supporting_proof_evidence",
        }
    if proposed == "keep":
        return {
            "artifact_path": path,
            "artifact_kind": kind,
            "classification": "keep",
            "reason_code": "CLEANUP_KEEP_DEFAULT",
            "evidence_role": candidate.get("evidence_role")
            if isinstance(candidate.get("evidence_role"), str)
            else "none",
        }
    return {
        "artifact_path": path,
        "artifact_kind": kind,
        "classification": "unknown_blocked",
        "reason_code": "CLEANUP_UNKNOWN_BLOCKED_AMBIGUOUS",
        "evidence_role": "unknown",
    }


def build_cleanup_candidate_report(
    *,
    report_id: str,
    audit_timestamp: str,
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build an advisory-only cleanup candidate report."""
    if not isinstance(report_id, str) or not report_id.strip():
        raise CleanupCandidateError("report_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise CleanupCandidateError(
            "audit_timestamp must be a non-empty string"
        )

    out: List[Dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, Mapping):
            continue
        out.append(_classify_candidate(c))

    return {
        "artifact_type": "cleanup_candidate_report",
        "schema_version": "1.0.0",
        "report_id": report_id,
        "audit_timestamp": audit_timestamp,
        "candidates": out,
        "non_authority_assertions": [
            "advisory_only",
            "no_deletion",
            "preparatory_only",
            "not_control_authority",
            "not_enforcement_authority",
        ],
    }
