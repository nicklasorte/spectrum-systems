"""Advisory bridge from the harness feedback surface to external owners.

This is the only module the harness uses to talk to external owners
(REL for release_signal/restoration_signal, CDE for closure_signal,
SEL for enforcement_signal). It packages a candidate's evidence into
a single ``hop_harness_control_advisory`` artifact and persists it.
The harness does not encode any release/advancement/control authority —
it merely emits the advisory, and the canonical owners consult it.

Design rules:

- The advisory is informational. ``advisory_only`` is permanently ``true``
  and ``delegates_to`` is non-empty.
- The advisory references existing artifact ids (release_readiness_signal,
  trial_summary, risk_failure ids) — it never inlines outcome logic.
- The bridge fails closed: if the referenced artifacts cannot be read,
  the bridge raises rather than silently producing a partial advisory.
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


class ControlIntegrationError(Exception):
    """Raised on infrastructure errors inside the bridge."""


_VALID_KINDS = ("readiness_evaluation", "rollback_signal_request", "trend_signal")


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class ControlAdvisoryRequest:
    subject_candidate_id: str
    summary_kind: str
    release_readiness_signal_artifact_id: str | None = None
    trial_summary_artifact_id: str | None = None
    risk_failure_artifact_ids: tuple[str, ...] = ()
    delegates_to: tuple[str, ...] = ("REL",)


def build_control_advisory(
    request: ControlAdvisoryRequest,
    *,
    store: ExperienceStore,
    trace_id: str = "hop_control_integration",
) -> dict[str, Any]:
    """Build and validate a control-advisory payload.

    The bridge verifies that any referenced artifact id resolves in the
    store; missing references raise rather than silently produce a
    partial advisory.
    """
    if request.summary_kind not in _VALID_KINDS:
        raise ControlIntegrationError(
            f"hop_control_integration_invalid_kind:{request.summary_kind}"
        )
    if not isinstance(request.subject_candidate_id, str) or not request.subject_candidate_id:
        raise ControlIntegrationError("hop_control_integration_invalid_subject")
    if not request.delegates_to:
        raise ControlIntegrationError("hop_control_integration_no_delegates")

    if request.release_readiness_signal_artifact_id:
        try:
            store.read_artifact(
                "hop_harness_release_readiness_signal",
                request.release_readiness_signal_artifact_id,
            )
        except HopStoreError as exc:
            raise ControlIntegrationError(
                f"hop_control_integration_missing_readiness_signal:{exc}"
            ) from exc

    if request.trial_summary_artifact_id:
        try:
            store.read_artifact(
                "hop_harness_trial_summary", request.trial_summary_artifact_id
            )
        except HopStoreError as exc:
            raise ControlIntegrationError(
                f"hop_control_integration_missing_trial_summary:{exc}"
            ) from exc

    for fid in request.risk_failure_artifact_ids:
        try:
            store.read_artifact("hop_harness_failure_hypothesis", fid)
        except HopStoreError as exc:
            raise ControlIntegrationError(
                f"hop_control_integration_missing_failure:{fid}:{exc}"
            ) from exc

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_control_advisory",
        "schema_ref": "hop/harness_control_advisory.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[request.subject_candidate_id],
        ),
        "advisory_id": (
            f"advisory_{request.summary_kind}_{request.subject_candidate_id}"
        ),
        "subject_candidate_id": request.subject_candidate_id,
        "summary_kind": request.summary_kind,
        "release_readiness_signal_artifact_id": request.release_readiness_signal_artifact_id,
        "trial_summary_artifact_id": request.trial_summary_artifact_id,
        "risk_failure_artifact_ids": list(request.risk_failure_artifact_ids),
        "advisory_only": True,
        "delegates_to": list(request.delegates_to),
        "emitted_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_advisory_")
    validate_hop_artifact(payload, "hop_harness_control_advisory")
    return payload


def _find_existing_advisory(
    store: ExperienceStore, advisory_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(artifact_type="hop_harness_control_advisory"):
        fields = rec.get("fields", {}) or {}
        if fields.get("advisory_id") == advisory_id:
            try:
                return store.read_artifact(
                    "hop_harness_control_advisory", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def emit_control_advisory(
    request: ControlAdvisoryRequest,
    *,
    store: ExperienceStore,
    trace_id: str = "hop_control_integration",
) -> dict[str, Any]:
    """Emit a control advisory. Idempotent on identical ``request``.

    A prior advisory with the same logical ``advisory_id`` is returned
    unchanged. Wall-clock fields are captured only on first call.
    """
    logical_id = (
        f"advisory_{request.summary_kind}_{request.subject_candidate_id}"
    )
    existing = _find_existing_advisory(store, logical_id)
    if existing is not None:
        return existing
    advisory = build_control_advisory(request, store=store, trace_id=trace_id)
    try:
        store.write_artifact(advisory)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return advisory
        raise
    return advisory


def list_advisories(
    store: ExperienceStore,
    *,
    subject_candidate_id: str | None = None,
    summary_kind: str | None = None,
) -> Iterable[Mapping[str, Any]]:
    for rec in store.iter_index(artifact_type="hop_harness_control_advisory"):
        fields = rec.get("fields", {}) or {}
        if subject_candidate_id and fields.get("subject_candidate_id") != subject_candidate_id:
            continue
        if summary_kind and fields.get("summary_kind") != summary_kind:
            continue
        try:
            yield store.read_artifact(
                "hop_harness_control_advisory", rec["artifact_id"]
            )
        except HopStoreError:
            continue
