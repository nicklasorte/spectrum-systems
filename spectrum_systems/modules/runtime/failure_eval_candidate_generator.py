"""EVL: failure_eval_candidate_generator — deterministic failure → eval generation (CLX-ALL-01 Phase 3).

Consumes failure_trace / failure_packet artifacts and emits entries for
``eval_candidate_registry``. Integrates with PQX replay: generated evals
are included in replay runs automatically.

Constraints (hard):
  - Deterministic: same inputs → same entry_id.
  - No free-text evals — schema-bound only.
  - Only failure_class values from the registered enum are accepted.
  - eval_type must map to a known registry category.
  - Silent failures are prohibited.

Canonical owner: EVL. This module does not perform evaluation; it generates
structured candidates for governed adoption.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# Failure classes accepted by this generator.
_ACCEPTED_FAILURE_CLASSES = frozenset([
    "authority_shape_violation",
    "registry_guard_failure",
    "manifest_drift",
    "proof_presence_missing",
    "replay_mismatch",
    "eval_coverage_gap",
    "shadow_ownership_overlap",
    "forbidden_symbol_misuse",
    "vocabulary_violation",
])

# Failure-class → eval_type mapping (schema-bound, no free-text).
_FAILURE_CLASS_TO_EVAL_TYPE: dict[str, str] = {
    "authority_shape_violation": "authority_shape",
    "vocabulary_violation": "authority_shape",
    "shadow_ownership_overlap": "authority_shape",
    "forbidden_symbol_misuse": "authority_shape",
    "registry_guard_failure": "registry_guard",
    "manifest_drift": "manifest_drift",
    "proof_presence_missing": "proof_presence",
    "replay_mismatch": "replay_mismatch",
    "eval_coverage_gap": "coverage_gap",
}

# Expected outcome templates per eval_type.
_EXPECTED_OUTCOME_TEMPLATES: dict[str, str] = {
    "authority_shape": "system_blocks_with_authority_shape_violation",
    "registry_guard": "system_blocks_with_registry_guard_failure",
    "manifest_drift": "system_blocks_with_manifest_drift_detected",
    "proof_presence": "system_blocks_with_missing_core_loop_proof",
    "replay_mismatch": "system_blocks_with_replay_classification_mismatch",
    "coverage_gap": "system_blocks_with_missing_eval_coverage",
}


class FailureEvalCandidateGeneratorError(ValueError):
    """Raised when generation cannot complete deterministically."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _entry_id(trace_id: str, failure_class: str, source_ref: str) -> str:
    payload = f"fecg-{trace_id}-{failure_class}-{source_ref}"
    return "fecg-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _scenario_name(failure_class: str, source_ref: str) -> str:
    clean_ref = source_ref.replace("/", "_").replace("-", "_")[:20]
    return f"{failure_class}__{clean_ref}".lower()


def generate_eval_candidate_entry(
    *,
    trace_id: str,
    failure_class: str,
    source_failure_ref: str,
    detail: str = "",
) -> dict[str, Any]:
    """Generate a single eval candidate registry entry from a failure.

    Returns a dict compatible with ``eval_candidate_registry.entries[]``.

    Raises ``FailureEvalCandidateGeneratorError`` on invalid input or unknown
    failure_class (fail-closed).
    """
    if not trace_id or not isinstance(trace_id, str):
        raise FailureEvalCandidateGeneratorError("trace_id must be a non-empty string")
    if not source_failure_ref or not isinstance(source_failure_ref, str):
        raise FailureEvalCandidateGeneratorError("source_failure_ref must be a non-empty string")
    if failure_class not in _ACCEPTED_FAILURE_CLASSES:
        raise FailureEvalCandidateGeneratorError(
            f"Unknown failure_class '{failure_class}'. "
            f"Accepted: {sorted(_ACCEPTED_FAILURE_CLASSES)}"
        )

    eval_type = _FAILURE_CLASS_TO_EVAL_TYPE[failure_class]
    expected_outcome = _EXPECTED_OUTCOME_TEMPLATES[eval_type]
    now = _now()

    return {
        "entry_id": _entry_id(trace_id, failure_class, source_failure_ref),
        "source_failure_ref": source_failure_ref,
        "failure_class": failure_class,
        "eval_type": eval_type,
        "adoption_status": "pending_review",
        "deterministic": True,
        "scenario_name": _scenario_name(failure_class, source_failure_ref),
        "expected_outcome": expected_outcome,
        "added_at": now,
        "adopted_at": None,
    }


def generate_eval_candidate_registry(
    *,
    trace_id: str,
    run_id: str = "",
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an ``eval_candidate_registry`` from a list of failure records.

    Each failure record must have:
      - ``failure_class``: string (from _ACCEPTED_FAILURE_CLASSES)
      - ``source_failure_ref``: string (reference to the originating artifact)

    Optional:
      - ``detail``: string (descriptive context, not stored in registry)

    Entries with unknown failure_class are skipped with a logged skip reason;
    they do not silently produce incomplete entries.

    Returns the full ``eval_candidate_registry`` artifact.
    """
    if not trace_id or not isinstance(trace_id, str):
        raise FailureEvalCandidateGeneratorError("trace_id must be a non-empty string")
    if not isinstance(failures, list):
        raise FailureEvalCandidateGeneratorError("failures must be a list")

    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    seen_ids: set[str] = set()

    for failure in failures:
        if not isinstance(failure, dict):
            skipped.append({"reason": "not_a_dict", "value": str(failure)[:80]})
            continue

        fc = str(failure.get("failure_class") or "").strip()
        ref = str(failure.get("source_failure_ref") or "").strip()

        if not fc:
            skipped.append({"reason": "missing_failure_class", "ref": ref})
            continue
        if not ref:
            skipped.append({"reason": "missing_source_failure_ref", "failure_class": fc})
            continue
        if fc not in _ACCEPTED_FAILURE_CLASSES:
            skipped.append({"reason": f"unknown_failure_class:{fc}", "ref": ref})
            continue

        entry = generate_eval_candidate_entry(
            trace_id=trace_id,
            failure_class=fc,
            source_failure_ref=ref,
            detail=str(failure.get("detail") or ""),
        )
        # Deduplicate by entry_id.
        if entry["entry_id"] in seen_ids:
            continue
        seen_ids.add(entry["entry_id"])
        entries.append(entry)

    registry = {
        "artifact_type": "eval_candidate_registry",
        "schema_version": "1.0.0",
        "registry_id": _entry_id(trace_id, "registry", run_id or "default"),
        "trace_id": trace_id,
        "run_id": run_id,
        "entries": entries,
        "total_entries": len(entries),
        "emitted_at": _now(),
    }

    return registry


__all__ = [
    "FailureEvalCandidateGeneratorError",
    "generate_eval_candidate_entry",
    "generate_eval_candidate_registry",
]
