"""Advisory release-readiness signal builder for the harness feedback surface.

REL is the canonical release/rollback owner. This module merely packages
evaluator evidence (search-eval score, held-out score, trace completeness,
risk-failure hypotheses, quarantine signals) into a structured
``hop_harness_release_readiness_signal`` artifact for REL/CDE/control
owners to consult. The signal carries no execution authority.

The ``readiness_signal`` field carries one of three advisory values:

- ``ready_signal`` — every required check passed; no risks observed.
- ``warn_signal`` — readiness check ran but produced a non-fatal caveat.
- ``risk_signal`` — at least one required check failed; do not act on
  this candidate without further review.

Required checks (fail-closed):

- ``search_score_threshold`` — search-eval score >= configured floor.
- ``heldout_score_threshold`` — held-out-eval score >= configured floor.
- ``trace_completeness`` — both runs' traces complete on every case.
- ``no_risk_failures`` — zero failure hypotheses with
  ``blocks_promotion=true`` for the candidate.
- ``candidate_admitted`` — candidate artifact is readable from the store.
- ``search_set_disjoint_from_heldout`` — eval_set_ids must not match.
- ``candidate_not_quarantined`` — no ``quarantine`` rollback signal.
- ``scores_admitted`` — both score artifacts live in the store.

Any check that cannot be evaluated forces ``readiness_signal=risk_signal``.
There is no path that produces ``ready_signal`` while a required check
fails. The signal is informational only; release/rollback authority
remains with REL.
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


_READY = "ready_signal"
_WARN = "warn_signal"
_RISK = "risk_signal"


class ReadinessSignalError(Exception):
    """Raised on infrastructure errors inside the readiness builder."""


# Backwards-compatible alias.
PromotionGateError = ReadinessSignalError


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class ReadinessSignalConfig:
    """Configuration for the readiness builder.

    The defaults are deliberately strict: a candidate that does not pass
    every case in either eval set yields a non-ready signal. The
    fail-closed default for any check that cannot be evaluated is
    ``risk_signal``.
    """

    search_score_threshold: float = 1.0
    heldout_score_threshold: float = 1.0
    min_trace_completeness: float = 1.0


# Backwards-compatible alias.
PromotionGateConfig = ReadinessSignalConfig


@dataclass(frozen=True)
class ReadinessSignalInputs:
    candidate_id: str
    search_score: Mapping[str, Any]
    heldout_score: Mapping[str, Any]
    risk_failures: tuple[Mapping[str, Any], ...] = ()


# Backwards-compatible alias.
PromotionGateInputs = ReadinessSignalInputs


def _check_search_score_threshold(
    inputs: ReadinessSignalInputs, cfg: ReadinessSignalConfig
) -> tuple[bool, str]:
    score = float(inputs.search_score.get("score", -1))
    threshold = cfg.search_score_threshold
    if score >= threshold:
        return True, f"search_score={score:.4f}>=threshold={threshold:.4f}"
    return False, f"search_score={score:.4f}<threshold={threshold:.4f}"


def _check_heldout_score_threshold(
    inputs: ReadinessSignalInputs, cfg: ReadinessSignalConfig
) -> tuple[bool, str]:
    score = float(inputs.heldout_score.get("score", -1))
    threshold = cfg.heldout_score_threshold
    if score >= threshold:
        return True, f"heldout_score={score:.4f}>=threshold={threshold:.4f}"
    return False, f"heldout_score={score:.4f}<threshold={threshold:.4f}"


def _check_trace_completeness(
    inputs: ReadinessSignalInputs, cfg: ReadinessSignalConfig
) -> tuple[bool, str]:
    s = float(inputs.search_score.get("trace_completeness", 0.0))
    h = float(inputs.heldout_score.get("trace_completeness", 0.0))
    minimum = cfg.min_trace_completeness
    if s >= minimum and h >= minimum:
        return True, f"search={s:.4f}>=minimum={minimum:.4f},heldout={h:.4f}>=minimum={minimum:.4f}"
    return False, f"search={s:.4f},heldout={h:.4f},minimum={minimum:.4f}"


def _check_no_risk_failures(
    inputs: ReadinessSignalInputs, _: ReadinessSignalConfig
) -> tuple[bool, str]:
    risks = [
        f for f in inputs.risk_failures
        if bool(f.get("blocks_promotion"))
    ]
    if not risks:
        return True, "no_risk_failures"
    ids = ",".join(str(f.get("hypothesis_id", "?")) for f in risks[:8])
    return False, f"risk_failures={len(risks)}:{ids}"


def _check_candidate_admitted(
    inputs: ReadinessSignalInputs, _: ReadinessSignalConfig, *, store: ExperienceStore
) -> tuple[bool, str]:
    """Must be able to read the candidate from the store."""
    found = False
    for rec in store.list_candidates():
        fields = rec.get("fields", {}) or {}
        if fields.get("candidate_id") == inputs.candidate_id:
            found = True
            break
    if found:
        return True, f"candidate_id={inputs.candidate_id}_admitted"
    return False, f"candidate_id={inputs.candidate_id}_not_admitted"


def _check_search_disjoint_from_heldout(
    inputs: ReadinessSignalInputs, _: ReadinessSignalConfig
) -> tuple[bool, str]:
    s_id = str(inputs.search_score.get("eval_set_id", ""))
    h_id = str(inputs.heldout_score.get("eval_set_id", ""))
    if not s_id or not h_id:
        return False, f"missing_eval_set_id:search={s_id!r},heldout={h_id!r}"
    if s_id == h_id:
        return False, f"search_eq_heldout:{s_id}"
    return True, f"search={s_id},heldout={h_id}"


def _check_candidate_not_quarantined(
    inputs: ReadinessSignalInputs, _: ReadinessSignalConfig, *, store: ExperienceStore
) -> tuple[bool, str]:
    """A candidate with a quarantine signal must never reach ready_signal."""
    for rec in store.iter_index(artifact_type="hop_harness_rollback_signal"):
        fields = rec.get("fields", {}) or {}
        if (
            fields.get("subject_candidate_id") == inputs.candidate_id
            and fields.get("recommended_action") == "quarantine"
        ):
            return False, f"quarantine_signal_present:{rec.get('artifact_id')}"
    return True, "no_quarantine_signal"


def _check_scores_admitted(
    inputs: ReadinessSignalInputs, _: ReadinessSignalConfig, *, store: ExperienceStore
) -> tuple[bool, str]:
    """Both score artifacts must be admitted to the store.

    Without this check, a caller could synthesise an in-memory score
    artifact that was never produced by the evaluator and thus never
    exercised the sandbox.
    """
    s_id = inputs.search_score.get("artifact_id")
    h_id = inputs.heldout_score.get("artifact_id")
    if not isinstance(s_id, str) or not isinstance(h_id, str):
        return False, "missing_artifact_id"
    seen_search = False
    seen_heldout = False
    for rec in store.iter_index(artifact_type="hop_harness_score"):
        a_id = rec.get("artifact_id")
        if a_id == s_id:
            seen_search = True
        if a_id == h_id:
            seen_heldout = True
        if seen_search and seen_heldout:
            break
    if seen_search and seen_heldout:
        return True, f"both_admitted:search={s_id},heldout={h_id}"
    return False, (
        f"not_admitted:search_seen={seen_search},heldout_seen={seen_heldout}"
    )


def evaluate_release_readiness(
    *,
    inputs: ReadinessSignalInputs,
    store: ExperienceStore,
    config: ReadinessSignalConfig | None = None,
    trace_id: str = "hop_release_readiness",
) -> dict[str, Any]:
    """Evaluate a candidate and return a finalized readiness-signal payload.

    The return value is the *artifact*, not a Python object — callers may
    persist it via ``store.write_artifact``.
    """
    cfg = config or ReadinessSignalConfig()
    if not isinstance(inputs.search_score, Mapping):
        raise ReadinessSignalError("hop_release_readiness_invalid_search_score")
    if not isinstance(inputs.heldout_score, Mapping):
        raise ReadinessSignalError("hop_release_readiness_invalid_heldout_score")
    validate_hop_artifact(dict(inputs.search_score), "hop_harness_score")
    validate_hop_artifact(dict(inputs.heldout_score), "hop_harness_score")

    rationale: list[dict[str, Any]] = []

    def _record(check: str, passed: bool, detail: str) -> None:
        rationale.append({"check": check, "passed": passed, "detail": detail})

    p, d = _check_candidate_admitted(inputs, cfg, store=store)
    _record("candidate_admitted", p, d)
    p, d = _check_scores_admitted(inputs, cfg, store=store)
    _record("scores_admitted", p, d)
    p, d = _check_candidate_not_quarantined(inputs, cfg, store=store)
    _record("candidate_not_quarantined", p, d)
    p, d = _check_search_disjoint_from_heldout(inputs, cfg)
    _record("search_set_disjoint_from_heldout", p, d)
    p, d = _check_search_score_threshold(inputs, cfg)
    _record("search_score_threshold", p, d)
    p, d = _check_heldout_score_threshold(inputs, cfg)
    _record("heldout_score_threshold", p, d)
    p, d = _check_trace_completeness(inputs, cfg)
    _record("trace_completeness", p, d)
    p, d = _check_no_risk_failures(inputs, cfg)
    _record("no_risk_failures", p, d)

    all_passed = all(item["passed"] for item in rationale)
    readiness_signal = _READY if all_passed else _RISK

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_release_readiness_signal",
        "schema_ref": "hop/harness_release_readiness_signal.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[inputs.candidate_id],
        ),
        "signal_id": (
            f"signal_{inputs.candidate_id}_"
            f"{int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000)}"
        ),
        "candidate_id": inputs.candidate_id,
        "search_score_artifact_id": inputs.search_score["artifact_id"],
        "heldout_score_artifact_id": inputs.heldout_score["artifact_id"],
        "search_score": float(inputs.search_score.get("score", 0.0)),
        "heldout_score": float(inputs.heldout_score.get("score", 0.0)),
        "search_eval_set_id": str(inputs.search_score.get("eval_set_id", "")),
        "heldout_eval_set_id": str(inputs.heldout_score.get("eval_set_id", "")),
        "trace_completeness": min(
            float(inputs.search_score.get("trace_completeness", 0.0)),
            float(inputs.heldout_score.get("trace_completeness", 0.0)),
        ),
        "risk_failure_count": sum(
            1 for f in inputs.risk_failures if bool(f.get("blocks_promotion"))
        ),
        "readiness_signal": readiness_signal,
        "rationale": rationale,
        "advisory_only": True,
        "delegates_to": "REL",
        "evaluated_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_rs_signal_")
    validate_hop_artifact(payload, "hop_harness_release_readiness_signal")
    return payload


# Backwards-compatible alias.
evaluate_promotion = evaluate_release_readiness


def list_risk_failures_for_candidate(
    store: ExperienceStore, candidate_id: str
) -> tuple[Mapping[str, Any], ...]:
    """Read failure hypotheses with blocks_promotion=true for a candidate.

    Callers can pass the returned tuple directly into
    ``ReadinessSignalInputs.risk_failures``.
    """
    out: list[Mapping[str, Any]] = []
    for rec in store.list_failures(candidate_id=candidate_id):
        try:
            payload = store.read_artifact(
                "hop_harness_failure_hypothesis", rec["artifact_id"]
            )
        except HopStoreError:
            continue
        if bool(payload.get("blocks_promotion")):
            out.append(payload)
    return tuple(out)


# Backwards-compatible alias.
list_blocking_failures_for_candidate = list_risk_failures_for_candidate


def _logical_signal_id(inputs: ReadinessSignalInputs) -> str:
    return (
        f"signal_{inputs.candidate_id}"
        f"_search_{inputs.search_score['artifact_id']}"
        f"_heldout_{inputs.heldout_score['artifact_id']}"
    )


def _find_existing_signal(
    store: ExperienceStore, signal_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(
        artifact_type="hop_harness_release_readiness_signal"
    ):
        fields = rec.get("fields", {}) or {}
        if fields.get("signal_id") == signal_id:
            try:
                return store.read_artifact(
                    "hop_harness_release_readiness_signal", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def evaluate_and_persist(
    *,
    inputs: ReadinessSignalInputs,
    store: ExperienceStore,
    config: ReadinessSignalConfig | None = None,
    trace_id: str = "hop_release_readiness",
) -> dict[str, Any]:
    """Convenience: evaluate, validate, and persist the readiness signal.

    Idempotent on identical inputs: a prior signal with the same logical
    ``signal_id`` (derived from candidate + search/held-out artifact ids)
    is returned unchanged. The wall-clock-bearing artifact is created
    only on first call.
    """
    logical_id = _logical_signal_id(inputs)
    existing = _find_existing_signal(store, logical_id)
    if existing is not None:
        return existing
    signal = evaluate_release_readiness(
        inputs=inputs, store=store, config=config, trace_id=trace_id
    )
    signal["signal_id"] = logical_id
    finalize_artifact(signal, id_prefix="hop_rs_signal_")
    validate_hop_artifact(signal, "hop_harness_release_readiness_signal")
    try:
        store.write_artifact(signal)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return signal
        raise
    return signal


def iter_risk_signals(
    store: ExperienceStore, *, candidate_id: str | None = None
) -> Iterable[Mapping[str, Any]]:
    for rec in store.iter_index(
        artifact_type="hop_harness_release_readiness_signal"
    ):
        fields = rec.get("fields", {}) or {}
        if fields.get("readiness_signal") != _RISK:
            continue
        if candidate_id and fields.get("candidate_id") != candidate_id:
            continue
        try:
            yield store.read_artifact(
                "hop_harness_release_readiness_signal", rec["artifact_id"]
            )
        except HopStoreError:
            continue


# Backwards-compatible alias.
iter_blocking_decisions = iter_risk_signals
