"""Governed durable judgment record emission for PQX blocked/resolved decisions."""

from __future__ import annotations

from typing import Iterable

from spectrum_systems.contracts import validate_artifact


class PQXJudgmentError(ValueError):
    """Raised when judgment record construction violates governance constraints."""


_ALLOWED_OUTCOMES = {"blocked", "resolved", "accepted", "resumed"}


def build_pqx_judgment_record(
    *,
    record_id: str,
    decision_type: str,
    outcome: str,
    reasons: Iterable[str],
    artifact_refs: Iterable[str],
    bundle_id: str,
    slice_id: str | None,
    run_id: str,
    trace_id: str,
    created_at: str,
    policy_refs: Iterable[str] | None = None,
) -> dict:
    if not record_id:
        raise PQXJudgmentError("record_id is required")
    if not decision_type:
        raise PQXJudgmentError("decision_type is required")
    if outcome not in _ALLOWED_OUTCOMES:
        raise PQXJudgmentError(f"unsupported outcome: {outcome}")

    normalized_reasons = [r for r in reasons if isinstance(r, str) and r]
    if not normalized_reasons:
        raise PQXJudgmentError("at least one decision reason is required")

    normalized_refs = [r for r in artifact_refs if isinstance(r, str) and r]
    if not normalized_refs:
        raise PQXJudgmentError("at least one upstream artifact reference is required")

    record = {
        "schema_version": "1.0.0",
        "record_id": record_id,
        "decision_type": decision_type,
        "outcome": outcome,
        "decision_basis": normalized_reasons,
        "upstream_artifact_refs": normalized_refs,
        "affected_bundle_id": bundle_id,
        "affected_slice_id": slice_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "policy_refs": [r for r in (policy_refs or []) if isinstance(r, str) and r],
        "created_at": created_at,
    }
    try:
        validate_artifact(record, "pqx_judgment_record")
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        raise PQXJudgmentError(f"invalid pqx_judgment_record artifact: {exc}") from exc
    return record
