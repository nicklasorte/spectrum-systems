"""HOP advisory promotion gate (Phase 2).

The promotion gate evaluates whether a candidate is *recommended* for
promotion. It NEVER promotes — it emits a single
``hop_harness_promotion_decision`` artifact whose ``decision`` field
is one of ``allow / warn / block`` and whose ``advisory_only`` flag is
permanently ``true``. Final authority is the external control plane.

Required checks (fail-closed):

- ``search_score_threshold`` — search-eval score >= configured floor.
- ``heldout_score_threshold`` — held-out-eval score >= configured floor.
- ``trace_completeness`` — both runs' traces complete on every case.
- ``no_blocking_failures`` — zero failure hypotheses with
  ``blocks_promotion=true`` for the candidate.
- ``candidate_admitted`` — candidate artifact is readable from the store.
- ``search_set_disjoint_from_heldout`` — eval_set_ids must not match.

Any check that cannot be evaluated produces ``passed=false`` and forces
``decision=block``. There is no path that produces ``allow`` while a
required check fails.
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


class PromotionGateError(Exception):
    """Raised on infrastructure errors inside the gate itself."""


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class PromotionGateConfig:
    """Configuration for the promotion gate.

    The defaults are deliberately strict: a candidate that does not pass
    every case in either eval set is, at best, ``warn``. ``block`` is
    the default outcome for any check that cannot be evaluated.
    """

    search_score_threshold: float = 1.0
    heldout_score_threshold: float = 1.0
    min_trace_completeness: float = 1.0


@dataclass(frozen=True)
class PromotionGateInputs:
    candidate_id: str
    search_score: Mapping[str, Any]
    heldout_score: Mapping[str, Any]
    blocking_failures: tuple[Mapping[str, Any], ...] = ()


def _check_search_score_threshold(
    inputs: PromotionGateInputs, cfg: PromotionGateConfig
) -> tuple[bool, str]:
    score = float(inputs.search_score.get("score", -1))
    threshold = cfg.search_score_threshold
    if score >= threshold:
        return True, f"search_score={score:.4f}>=threshold={threshold:.4f}"
    return False, f"search_score={score:.4f}<threshold={threshold:.4f}"


def _check_heldout_score_threshold(
    inputs: PromotionGateInputs, cfg: PromotionGateConfig
) -> tuple[bool, str]:
    score = float(inputs.heldout_score.get("score", -1))
    threshold = cfg.heldout_score_threshold
    if score >= threshold:
        return True, f"heldout_score={score:.4f}>=threshold={threshold:.4f}"
    return False, f"heldout_score={score:.4f}<threshold={threshold:.4f}"


def _check_trace_completeness(
    inputs: PromotionGateInputs, cfg: PromotionGateConfig
) -> tuple[bool, str]:
    s = float(inputs.search_score.get("trace_completeness", 0.0))
    h = float(inputs.heldout_score.get("trace_completeness", 0.0))
    minimum = cfg.min_trace_completeness
    if s >= minimum and h >= minimum:
        return True, f"search={s:.4f}>=minimum={minimum:.4f},heldout={h:.4f}>=minimum={minimum:.4f}"
    return False, f"search={s:.4f},heldout={h:.4f},minimum={minimum:.4f}"


def _check_no_blocking_failures(
    inputs: PromotionGateInputs, _: PromotionGateConfig
) -> tuple[bool, str]:
    blocking = [
        f for f in inputs.blocking_failures
        if bool(f.get("blocks_promotion"))
    ]
    if not blocking:
        return True, "no_blocking_failures"
    ids = ",".join(str(f.get("hypothesis_id", "?")) for f in blocking[:8])
    return False, f"blocking_failures={len(blocking)}:{ids}"


def _check_candidate_admitted(
    inputs: PromotionGateInputs, _: PromotionGateConfig, *, store: ExperienceStore
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
    inputs: PromotionGateInputs, _: PromotionGateConfig
) -> tuple[bool, str]:
    s_id = str(inputs.search_score.get("eval_set_id", ""))
    h_id = str(inputs.heldout_score.get("eval_set_id", ""))
    if not s_id or not h_id:
        return False, f"missing_eval_set_id:search={s_id!r},heldout={h_id!r}"
    if s_id == h_id:
        return False, f"search_eq_heldout:{s_id}"
    return True, f"search={s_id},heldout={h_id}"


def _check_candidate_not_quarantined(
    inputs: PromotionGateInputs, _: PromotionGateConfig, *, store: ExperienceStore
) -> tuple[bool, str]:
    """A candidate with a quarantine signal must never reach decision=allow."""
    for rec in store.iter_index(artifact_type="hop_harness_rollback_signal"):
        fields = rec.get("fields", {}) or {}
        if (
            fields.get("subject_candidate_id") == inputs.candidate_id
            and fields.get("recommended_action") == "quarantine"
        ):
            return False, f"quarantine_signal_present:{rec.get('artifact_id')}"
    return True, "no_quarantine_signal"


def _check_scores_admitted(
    inputs: PromotionGateInputs, _: PromotionGateConfig, *, store: ExperienceStore
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


def evaluate_promotion(
    *,
    inputs: PromotionGateInputs,
    store: ExperienceStore,
    config: PromotionGateConfig | None = None,
    trace_id: str = "hop_promotion_gate",
) -> dict[str, Any]:
    """Evaluate a candidate and return a finalized promotion-decision payload.

    The return value is the *artifact*, not a Python object — callers may
    persist it via ``store.write_artifact``.
    """
    cfg = config or PromotionGateConfig()
    if not isinstance(inputs.search_score, Mapping):
        raise PromotionGateError("hop_promotion_gate_invalid_search_score")
    if not isinstance(inputs.heldout_score, Mapping):
        raise PromotionGateError("hop_promotion_gate_invalid_heldout_score")
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
    p, d = _check_no_blocking_failures(inputs, cfg)
    _record("no_blocking_failures", p, d)

    all_passed = all(item["passed"] for item in rationale)
    decision = "allow" if all_passed else "block"

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_promotion_decision",
        "schema_ref": "hop/harness_promotion_decision.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[inputs.candidate_id],
        ),
        "decision_id": f"promo_{inputs.candidate_id}_{int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000)}",
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
        "blocking_failure_count": sum(
            1 for f in inputs.blocking_failures if bool(f.get("blocks_promotion"))
        ),
        "decision": decision,
        "rationale": rationale,
        "advisory_only": True,
        "evaluated_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_promo_")
    validate_hop_artifact(payload, "hop_harness_promotion_decision")
    return payload


def list_blocking_failures_for_candidate(
    store: ExperienceStore, candidate_id: str
) -> tuple[Mapping[str, Any], ...]:
    """Read blocking failure hypotheses for a candidate from the store.

    Returns the tuple of failure payloads with ``blocks_promotion=true``.
    Callers can pass this directly into ``PromotionGateInputs``.
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


def _logical_decision_id(inputs: PromotionGateInputs) -> str:
    return (
        f"promo_{inputs.candidate_id}"
        f"_search_{inputs.search_score['artifact_id']}"
        f"_heldout_{inputs.heldout_score['artifact_id']}"
    )


def _find_existing_decision(
    store: ExperienceStore, decision_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(artifact_type="hop_harness_promotion_decision"):
        fields = rec.get("fields", {}) or {}
        if fields.get("decision_id") == decision_id:
            try:
                return store.read_artifact(
                    "hop_harness_promotion_decision", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def evaluate_and_persist(
    *,
    inputs: PromotionGateInputs,
    store: ExperienceStore,
    config: PromotionGateConfig | None = None,
    trace_id: str = "hop_promotion_gate",
) -> dict[str, Any]:
    """Convenience: evaluate, validate, and persist the decision artifact.

    Idempotent on identical inputs: a prior decision with the same logical
    ``decision_id`` (derived from the candidate + search/held-out artifact
    ids) is returned unchanged. The wall-clock-bearing artifact is created
    only on first call.
    """
    logical_id = _logical_decision_id(inputs)
    existing = _find_existing_decision(store, logical_id)
    if existing is not None:
        return existing
    decision = evaluate_promotion(
        inputs=inputs, store=store, config=config, trace_id=trace_id
    )
    decision["decision_id"] = logical_id
    finalize_artifact(decision, id_prefix="hop_promo_")
    validate_hop_artifact(decision, "hop_harness_promotion_decision")
    try:
        store.write_artifact(decision)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return decision
        raise
    return decision


def iter_blocking_decisions(
    store: ExperienceStore, *, candidate_id: str | None = None
) -> Iterable[Mapping[str, Any]]:
    for rec in store.iter_index(artifact_type="hop_harness_promotion_decision"):
        fields = rec.get("fields", {}) or {}
        if fields.get("decision") != "block":
            continue
        if candidate_id and fields.get("candidate_id") != candidate_id:
            continue
        try:
            yield store.read_artifact(
                "hop_harness_promotion_decision", rec["artifact_id"]
            )
        except HopStoreError:
            continue
