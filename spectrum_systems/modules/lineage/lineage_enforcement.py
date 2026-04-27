"""LIN: lineage enforcement support — promotion prerequisite checks.

NX-10: This module wraps the existing lineage primitives and exposes a
single fail-closed seam used at the certification gate to assert that an
artifact has:
  - parent artifact references
  - produced-artifact linkage in the registry
  - trace_id and span/run_id present
  - a chain back to an immutable input artifact

It does not duplicate ``artifact_lineage``; it leverages the existing
``verify_lineage_completeness`` plus minimal additional checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from spectrum_systems.modules.lineage.lineage_verifier import (
    INPUT_ARTIFACT_TYPES,
    verify_lineage_completeness,
)


class LineageEnforcementError(ValueError):
    """Raised when lineage enforcement cannot be deterministically performed."""


CANONICAL_LINEAGE_REASON_CODES = {
    "LINEAGE_OK",
    "LINEAGE_MISSING_PARENT_ARTIFACT",
    "LINEAGE_MISSING_PRODUCED_ARTIFACT",
    "LINEAGE_MISSING_TRACE_ID",
    "LINEAGE_MISSING_RUN_ID",
    "LINEAGE_MISSING_INPUT_CHAIN",
    "LINEAGE_ORPHANED_NON_ROOT",
    "LINEAGE_STORE_UNAVAILABLE",
}


def assert_lineage_promotion_prerequisites(
    *,
    artifact: Mapping[str, Any],
    artifact_store: Mapping[str, Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    """Check that ``artifact`` is promotion-ready from a lineage standpoint.

    Returns a dict with keys:
      {"decision": "allow"|"block", "reason_code": str,
       "blocking_reasons": [str,...]}
    """
    if not isinstance(artifact, Mapping):
        raise LineageEnforcementError("artifact must be a mapping")

    artifact_id = artifact.get("artifact_id") or artifact.get("id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_PRODUCED_ARTIFACT",
            "blocking_reasons": ["artifact missing artifact_id"],
        }

    artifact_type = artifact.get("artifact_type")
    if not isinstance(artifact_type, str) or not artifact_type.strip():
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_PRODUCED_ARTIFACT",
            "blocking_reasons": ["artifact missing artifact_type"],
        }

    trace_id = artifact.get("trace_id") or (artifact.get("trace") or {}).get("trace_id") if isinstance(artifact.get("trace"), Mapping) else artifact.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_TRACE_ID",
            "blocking_reasons": [f"artifact {artifact_id} missing trace_id"],
        }

    run_id = artifact.get("run_id") or (artifact.get("trace") or {}).get("run_id") if isinstance(artifact.get("trace"), Mapping) else artifact.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_RUN_ID",
            "blocking_reasons": [f"artifact {artifact_id} missing run_id"],
        }

    if artifact_store is None:
        return {
            "decision": "block",
            "reason_code": "LINEAGE_STORE_UNAVAILABLE",
            "blocking_reasons": [f"artifact store unavailable for {artifact_id}"],
        }

    if artifact_id not in artifact_store:
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_PRODUCED_ARTIFACT",
            "blocking_reasons": [
                f"produced artifact {artifact_id} not registered in lineage store"
            ],
        }

    upstream = artifact.get("upstream_artifacts") or artifact.get("parent_artifact_ids") or []
    if not isinstance(upstream, list):
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_PARENT_ARTIFACT",
            "blocking_reasons": [f"upstream_artifacts must be a list for {artifact_id}"],
        }

    if not upstream and artifact_type not in INPUT_ARTIFACT_TYPES:
        return {
            "decision": "block",
            "reason_code": "LINEAGE_ORPHANED_NON_ROOT",
            "blocking_reasons": [
                f"non-root artifact {artifact_id} ({artifact_type}) has no parents"
            ],
        }

    for parent_id in upstream:
        if parent_id not in artifact_store:
            return {
                "decision": "block",
                "reason_code": "LINEAGE_MISSING_PARENT_ARTIFACT",
                "blocking_reasons": [
                    f"artifact {artifact_id} references missing parent {parent_id}"
                ],
            }

    is_complete, errors = verify_lineage_completeness(
        artifact_id, dict(artifact_store)
    )
    if not is_complete:
        return {
            "decision": "block",
            "reason_code": "LINEAGE_MISSING_INPUT_CHAIN",
            "blocking_reasons": errors,
        }

    return {
        "decision": "allow",
        "reason_code": "LINEAGE_OK",
        "blocking_reasons": [],
    }


def build_lineage_coverage_summary(
    *,
    artifacts: List[Mapping[str, Any]],
    artifact_store: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate lineage status across many artifacts into a coverage summary."""
    total = len(artifacts)
    if total == 0:
        return {
            "total": 0,
            "complete": 0,
            "incomplete": 0,
            "completeness_rate": 0.0,
            "reason_codes": {},
            "status": "blocked",
            "debug_message": "No artifacts present — lineage coverage is zero.",
        }

    complete = 0
    incomplete = 0
    reason_counts: Dict[str, int] = {}
    for artifact in artifacts:
        try:
            result = assert_lineage_promotion_prerequisites(
                artifact=artifact, artifact_store=artifact_store
            )
        except LineageEnforcementError:
            incomplete += 1
            reason_counts["LINEAGE_MISSING_PRODUCED_ARTIFACT"] = (
                reason_counts.get("LINEAGE_MISSING_PRODUCED_ARTIFACT", 0) + 1
            )
            continue

        if result["decision"] == "allow":
            complete += 1
            reason_counts["LINEAGE_OK"] = reason_counts.get("LINEAGE_OK", 0) + 1
        else:
            incomplete += 1
            code = result["reason_code"]
            reason_counts[code] = reason_counts.get(code, 0) + 1

    completeness_rate = complete / total
    status = "healthy" if incomplete == 0 else "blocked"
    debug = (
        f"{complete}/{total} artifacts have complete lineage."
        if incomplete == 0
        else f"{incomplete}/{total} artifacts have incomplete lineage; promotion blocked."
    )
    return {
        "total": total,
        "complete": complete,
        "incomplete": incomplete,
        "completeness_rate": completeness_rate,
        "reason_codes": reason_counts,
        "status": status,
        "debug_message": debug,
    }


__all__ = [
    "CANONICAL_LINEAGE_REASON_CODES",
    "LineageEnforcementError",
    "assert_lineage_promotion_prerequisites",
    "build_lineage_coverage_summary",
]
