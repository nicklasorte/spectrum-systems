"""HOP advisory rollback / quarantine artifacts (Phase 2).

This module emits **advisory** rollback records. HOP itself never reverts a
deployed harness — the external control plane and SEL execute the action.
HOP's job is to:

- declare which candidate is the subject of the rollback;
- declare the prior promoted candidate (if any) it intends to restore;
- attach evidence (failure hypotheses, score artifacts, promotion decisions);
- emit a single ``hop_harness_rollback_record`` artifact.

The module also exposes a structural ``revert_promotion_marker`` helper that
records the rollback against the experience store so subsequent promotion
gates can refuse to re-promote a quarantined candidate without operator
review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.experience_store import (
    ExperienceStore,
    HopStoreError,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


class RollbackError(Exception):
    """Raised on infrastructure errors inside the rollback module."""


_VALID_ACTIONS = ("revert", "quarantine")
_VALID_REASONS = (
    "regression_detected",
    "blocking_failure_detected",
    "trace_incomplete",
    "control_plane_directive",
    "operator_request",
    "promotion_gate_block",
)


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class RollbackRequest:
    subject_candidate_id: str
    action: str
    reason: str
    previous_promoted_candidate_id: str | None = None
    evidence: tuple[Mapping[str, Any], ...] = ()


def build_rollback_record(
    request: RollbackRequest, *, trace_id: str = "hop_rollback"
) -> dict[str, Any]:
    """Build a finalized rollback-record artifact.

    Validates ``action`` and ``reason`` against the closed enum, requires at
    least one evidence item, and forbids self-referential rollback (a
    candidate cannot list itself as the previous promoted candidate).
    """
    if request.action not in _VALID_ACTIONS:
        raise RollbackError(f"hop_rollback_invalid_action:{request.action}")
    if request.reason not in _VALID_REASONS:
        raise RollbackError(f"hop_rollback_invalid_reason:{request.reason}")
    if (
        request.previous_promoted_candidate_id is not None
        and request.previous_promoted_candidate_id == request.subject_candidate_id
    ):
        raise RollbackError(
            f"hop_rollback_invalid_self_reference:{request.subject_candidate_id}"
        )
    if not request.evidence:
        raise RollbackError("hop_rollback_evidence_required")

    evidence_items: list[dict[str, Any]] = []
    for item in request.evidence:
        kind = item.get("kind")
        detail = item.get("detail")
        if not isinstance(kind, str) or not kind:
            raise RollbackError("hop_rollback_invalid_evidence:kind")
        if not isinstance(detail, str) or not detail:
            raise RollbackError("hop_rollback_invalid_evidence:detail")
        evidence_items.append({"kind": kind, "detail": detail})

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_rollback_record",
        "schema_ref": "hop/harness_rollback_record.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[request.subject_candidate_id]
            + (
                [request.previous_promoted_candidate_id]
                if request.previous_promoted_candidate_id
                else []
            ),
        ),
        "rollback_id": f"rollback_{request.action}_{request.subject_candidate_id}",
        "subject_candidate_id": request.subject_candidate_id,
        "previous_promoted_candidate_id": request.previous_promoted_candidate_id,
        "action": request.action,
        "reason": request.reason,
        "evidence": evidence_items,
        "advisory_only": True,
        "recorded_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_rollback_")
    validate_hop_artifact(payload, "hop_harness_rollback_record")
    return payload


def _find_existing_rollback(
    store: ExperienceStore, rollback_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(artifact_type="hop_harness_rollback_record"):
        fields = rec.get("fields", {}) or {}
        if fields.get("rollback_id") == rollback_id:
            try:
                return store.read_artifact(
                    "hop_harness_rollback_record", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def emit_rollback(
    request: RollbackRequest,
    *,
    store: ExperienceStore,
    trace_id: str = "hop_rollback",
) -> dict[str, Any]:
    """Emit a rollback record and persist it.

    Idempotent on identical ``RollbackRequest``: a prior record with the
    same logical ``rollback_id`` is returned unchanged. The wall-clock
    timestamp is captured only on the first call.
    """
    logical_id = f"rollback_{request.action}_{request.subject_candidate_id}"
    existing = _find_existing_rollback(store, logical_id)
    if existing is not None:
        return existing
    record = build_rollback_record(request, trace_id=trace_id)
    try:
        store.write_artifact(record)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return record
        raise
    return record


def is_quarantined(store: ExperienceStore, candidate_id: str) -> bool:
    """Has a ``quarantine`` rollback been emitted for this candidate?"""
    for rec in store.iter_index(artifact_type="hop_harness_rollback_record"):
        fields = rec.get("fields", {}) or {}
        if (
            fields.get("subject_candidate_id") == candidate_id
            and fields.get("action") == "quarantine"
        ):
            return True
    return False


def list_rollbacks(
    store: ExperienceStore,
    *,
    subject_candidate_id: str | None = None,
    action: str | None = None,
) -> Iterable[Mapping[str, Any]]:
    for rec in store.iter_index(artifact_type="hop_harness_rollback_record"):
        fields = rec.get("fields", {}) or {}
        if subject_candidate_id and fields.get("subject_candidate_id") != subject_candidate_id:
            continue
        if action and fields.get("action") != action:
            continue
        try:
            yield store.read_artifact(
                "hop_harness_rollback_record", rec["artifact_id"]
            )
        except HopStoreError:
            continue
