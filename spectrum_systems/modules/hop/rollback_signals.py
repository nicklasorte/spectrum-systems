"""Advisory rollback-signal builder for the harness feedback surface.

REL is the canonical release/rollback owner. This module merely packages
evidence (failure hypotheses, score artifact ids, prior promotion-decision
ids) into a structured ``hop_harness_rollback_signal`` artifact for REL
to act on.

The signal is informational only. Nothing here reverts, restores, or
quarantines anything; those actions remain with the canonical release
owner.
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


class RollbackSignalError(Exception):
    """Raised on infrastructure errors inside the rollback-signal builder."""


# Backwards-compatible alias retained for callers; not used in new code paths.
RollbackError = RollbackSignalError


_VALID_RECOMMENDATIONS = ("revert", "quarantine")
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
class RollbackSignalRequest:
    """Inputs the caller hands to the signal builder.

    ``recommended_action`` names the action REL would perform on its end if
    it accepts the signal; this module never performs that action itself.
    """

    subject_candidate_id: str
    recommended_action: str
    reason: str
    previous_promoted_candidate_id: str | None = None
    evidence: tuple[Mapping[str, Any], ...] = ()


# Backwards-compatible alias for prior name.
RollbackRequest = RollbackSignalRequest


def build_rollback_signal(
    request: RollbackSignalRequest, *, trace_id: str = "hop_rollback_signal"
) -> dict[str, Any]:
    """Build a finalized rollback-signal artifact.

    Validates ``recommended_action`` and ``reason`` against the closed
    enum, requires at least one evidence item, and forbids self-referential
    signals (a candidate cannot list itself as the previous promoted
    candidate).
    """
    if request.recommended_action not in _VALID_RECOMMENDATIONS:
        raise RollbackSignalError(
            f"hop_rollback_signal_invalid_action:{request.recommended_action}"
        )
    if request.reason not in _VALID_REASONS:
        raise RollbackSignalError(
            f"hop_rollback_signal_invalid_reason:{request.reason}"
        )
    if (
        request.previous_promoted_candidate_id is not None
        and request.previous_promoted_candidate_id == request.subject_candidate_id
    ):
        raise RollbackSignalError(
            f"hop_rollback_signal_invalid_self_reference:{request.subject_candidate_id}"
        )
    if not request.evidence:
        raise RollbackSignalError("hop_rollback_signal_evidence_required")

    evidence_items: list[dict[str, Any]] = []
    for item in request.evidence:
        kind = item.get("kind")
        detail = item.get("detail")
        if not isinstance(kind, str) or not kind:
            raise RollbackSignalError("hop_rollback_signal_invalid_evidence:kind")
        if not isinstance(detail, str) or not detail:
            raise RollbackSignalError("hop_rollback_signal_invalid_evidence:detail")
        evidence_items.append({"kind": kind, "detail": detail})

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_rollback_signal",
        "schema_ref": "hop/harness_rollback_signal.schema.json",
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
        "signal_id": (
            f"signal_{request.recommended_action}_{request.subject_candidate_id}"
        ),
        "subject_candidate_id": request.subject_candidate_id,
        "previous_promoted_candidate_id": request.previous_promoted_candidate_id,
        "recommended_action": request.recommended_action,
        "reason": request.reason,
        "evidence": evidence_items,
        "advisory_only": True,
        "delegates_to": "REL",
        "recorded_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_rb_signal_")
    validate_hop_artifact(payload, "hop_harness_rollback_signal")
    return payload


# Backwards-compatible alias.
build_rollback_record = build_rollback_signal


def _find_existing_signal(
    store: ExperienceStore, signal_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(artifact_type="hop_harness_rollback_signal"):
        fields = rec.get("fields", {}) or {}
        if fields.get("signal_id") == signal_id:
            try:
                return store.read_artifact(
                    "hop_harness_rollback_signal", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def emit_rollback_signal(
    request: RollbackSignalRequest,
    *,
    store: ExperienceStore,
    trace_id: str = "hop_rollback_signal",
) -> dict[str, Any]:
    """Build, validate, and persist a rollback signal.

    Idempotent on identical ``RollbackSignalRequest``: a prior signal with
    the same logical ``signal_id`` is returned unchanged. The wall-clock
    timestamp is captured only on the first call.
    """
    logical_id = (
        f"signal_{request.recommended_action}_{request.subject_candidate_id}"
    )
    existing = _find_existing_signal(store, logical_id)
    if existing is not None:
        return existing
    record = build_rollback_signal(request, trace_id=trace_id)
    try:
        store.write_artifact(record)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return record
        raise
    return record


# Backwards-compatible alias.
emit_rollback = emit_rollback_signal


def has_quarantine_signal(store: ExperienceStore, candidate_id: str) -> bool:
    """Has a ``quarantine``-recommendation signal been recorded?"""
    for rec in store.iter_index(artifact_type="hop_harness_rollback_signal"):
        fields = rec.get("fields", {}) or {}
        if (
            fields.get("subject_candidate_id") == candidate_id
            and fields.get("recommended_action") == "quarantine"
        ):
            return True
    return False


# Backwards-compatible alias.
is_quarantined = has_quarantine_signal


def list_rollback_signals(
    store: ExperienceStore,
    *,
    subject_candidate_id: str | None = None,
    recommended_action: str | None = None,
) -> Iterable[Mapping[str, Any]]:
    for rec in store.iter_index(artifact_type="hop_harness_rollback_signal"):
        fields = rec.get("fields", {}) or {}
        if subject_candidate_id and fields.get("subject_candidate_id") != subject_candidate_id:
            continue
        if recommended_action and fields.get("recommended_action") != recommended_action:
            continue
        try:
            yield store.read_artifact(
                "hop_harness_rollback_signal", rec["artifact_id"]
            )
        except HopStoreError:
            continue


# Backwards-compatible alias.
list_rollbacks = list_rollback_signals
