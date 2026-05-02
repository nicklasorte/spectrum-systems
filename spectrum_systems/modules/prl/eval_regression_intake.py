"""F3L-04 — PRL eval-regression intake builder.

Promotes PRL eval candidates produced from CLP/PRL failures into a
governed, observation-only intake record so future EVL/CLP/APU paths
can detect that PRL eval candidates have been routed into regression
coverage intake. PRL retains classification and eval-candidate
authority only; final eval acceptance, coverage, and dataset semantics
remain with EVL per docs/architecture/system_registry.md.

The builder is deterministic and fail-closed: any inconsistent input
(present claim without eval_candidate_refs, partial/missing/unknown
without reason_codes) raises ``ValueError`` before the artifact is
returned. PR body prose cannot substitute for refs because the schema
requires file-backed eval_candidate_refs whenever intake_status is
``present``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import jsonschema

from spectrum_systems.utils.deterministic_id import deterministic_id

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
_SCHEMA_NAME = "prl_eval_regression_intake_record"


REASON_NO_FAILURES_DETECTED = "no_failures_detected"
REASON_NO_EVAL_CANDIDATES_FOR_FAILURE_PACKETS = (
    "no_eval_candidates_for_failure_packets"
)
REASON_UNKNOWN_FAILURE_REQUIRES_MANUAL_REVIEW = (
    "unknown_failure_class_requires_manual_review"
)
REASON_CANDIDATE_NOT_GATE_ELIGIBLE = "candidate_not_gate_eligible"
REASON_CANDIDATE_REF_MISSING_ON_DISK = "candidate_ref_missing_on_disk"


@dataclass(frozen=True)
class CandidateIntake:
    """Per-candidate intake metadata supplied by the PRL pipeline.

    ``ref`` is the candidate file path persisted by PRL (e.g.
    ``outputs/prl/eval_candidates/<id>.json``).
    """

    ref: str
    failure_class: str
    gate_eligible: bool


def _load_schema() -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{_SCHEMA_NAME}.schema.json"
    if not path.exists():
        raise FileNotFoundError(
            f"PRL eval-regression intake schema not found — fail-closed: {path}"
        )
    with path.open() as f:
        return json.load(f)


def _validate(artifact: dict[str, Any]) -> None:
    schema = _load_schema()
    try:
        jsonschema.validate(artifact, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"prl_eval_regression_intake_record schema validation failed: {exc.message}"
        ) from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _evidence_hash_payload(
    *,
    eval_candidate_refs: Sequence[str],
    accepted_candidate_refs: Sequence[str],
    rejected_candidate_refs: Sequence[str],
    source_failure_packet_refs: Sequence[str],
    prl_artifact_index_ref: str | None,
    intake_status: str,
    coverage_intent: str,
    reason_codes: Sequence[str],
) -> dict[str, Any]:
    return {
        "eval_candidate_refs": sorted(eval_candidate_refs),
        "accepted_candidate_refs": sorted(accepted_candidate_refs),
        "rejected_candidate_refs": sorted(rejected_candidate_refs),
        "source_failure_packet_refs": sorted(source_failure_packet_refs),
        "prl_artifact_index_ref": prl_artifact_index_ref,
        "intake_status": intake_status,
        "coverage_intent": coverage_intent,
        "reason_codes": sorted(reason_codes),
    }


def _compute_evidence_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256-" + hashlib.sha256(serialized).hexdigest()


def _classify_intake(
    *,
    candidates: Sequence[CandidateIntake],
    source_failure_packet_refs: Sequence[str],
) -> tuple[str, str, list[str], list[str], list[str]]:
    """Compute (intake_status, coverage_intent, reason_codes, accepted, rejected).

    Rules:
      - No failure packets and no candidates → status=missing,
        intent=not_applicable, reason=no_failures_detected.
      - Failure packets present but zero candidates → status=missing,
        intent=manual_review_required,
        reason=no_eval_candidates_for_failure_packets.
      - Candidates exist and at least one is gate-eligible (known
        failure class) → status=present, intent=regression_candidate.
        Any rejected candidates surface a reason code but do not
        downgrade status, since the accepted set carries regression
        intake evidence; rejected refs remain visible for replay.
      - Candidates exist but none are gate-eligible → status=partial,
        intent=manual_review_required,
        reason=unknown_failure_class_requires_manual_review (or
        candidate_not_gate_eligible if rejection was non-unknown).
    """
    accepted = sorted({c.ref for c in candidates if c.gate_eligible})
    rejected = sorted({c.ref for c in candidates if not c.gate_eligible})
    reason_codes: list[str] = []

    if not candidates and not source_failure_packet_refs:
        return "missing", "not_applicable", [REASON_NO_FAILURES_DETECTED], accepted, rejected

    if not candidates and source_failure_packet_refs:
        return (
            "missing",
            "manual_review_required",
            [REASON_NO_EVAL_CANDIDATES_FOR_FAILURE_PACKETS],
            accepted,
            rejected,
        )

    if accepted:
        if rejected:
            for c in candidates:
                if c.gate_eligible:
                    continue
                if c.failure_class == "unknown_failure":
                    reason_codes.append(
                        REASON_UNKNOWN_FAILURE_REQUIRES_MANUAL_REVIEW
                    )
                else:
                    reason_codes.append(REASON_CANDIDATE_NOT_GATE_ELIGIBLE)
        # Deduplicate reason codes deterministically.
        deduped = sorted(set(reason_codes))
        return "present", "regression_candidate", deduped, accepted, rejected

    # Candidates exist, none accepted.
    for c in candidates:
        if c.failure_class == "unknown_failure":
            reason_codes.append(REASON_UNKNOWN_FAILURE_REQUIRES_MANUAL_REVIEW)
        else:
            reason_codes.append(REASON_CANDIDATE_NOT_GATE_ELIGIBLE)
    deduped = sorted(set(reason_codes))
    return "partial", "manual_review_required", deduped, accepted, rejected


def build_eval_regression_intake_record(
    *,
    run_id: str,
    trace_id: str,
    candidates: Iterable[CandidateIntake],
    source_failure_packet_refs: Iterable[str],
    prl_artifact_index_ref: str | None,
    prl_gate_result_ref: str | None = None,
    gate_recommendation: str | None = None,
    extra_reason_codes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a validated ``prl_eval_regression_intake_record`` artifact.

    Fails closed if the resulting artifact does not validate against
    ``prl_eval_regression_intake_record.schema.json`` — for example,
    if intake_status is ``present`` but ``eval_candidate_refs`` is
    empty (no PR body prose substitution) or if a non-``present``
    status carries no reason codes.
    """
    cand_list = list(candidates)
    failure_packet_refs = sorted({str(r) for r in source_failure_packet_refs})
    eval_candidate_refs = sorted({c.ref for c in cand_list})

    intake_status, coverage_intent, reason_codes, accepted, rejected = (
        _classify_intake(
            candidates=cand_list,
            source_failure_packet_refs=failure_packet_refs,
        )
    )

    if extra_reason_codes:
        merged = sorted(set(reason_codes) | set(extra_reason_codes))
        reason_codes = merged

    hash_payload = _evidence_hash_payload(
        eval_candidate_refs=eval_candidate_refs,
        accepted_candidate_refs=accepted,
        rejected_candidate_refs=rejected,
        source_failure_packet_refs=failure_packet_refs,
        prl_artifact_index_ref=prl_artifact_index_ref,
        intake_status=intake_status,
        coverage_intent=coverage_intent,
        reason_codes=reason_codes,
    )
    evidence_hash = _compute_evidence_hash(hash_payload)

    artifact_id = deterministic_id(
        prefix="prl-eri",
        payload={
            "run_id": run_id,
            "intake_status": intake_status,
            "coverage_intent": coverage_intent,
            "eval_candidate_refs": eval_candidate_refs,
            "source_failure_packet_refs": failure_packet_refs,
            "prl_artifact_index_ref": prl_artifact_index_ref,
        },
        namespace="prl::eval_regression_intake",
    )

    artifact: dict[str, Any] = {
        "artifact_type": "prl_eval_regression_intake_record",
        "schema_version": "1.0.0",
        "id": artifact_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "generated_at": _now_iso(),
        "source_system": "PRL",
        "source_failure_packet_refs": failure_packet_refs,
        "eval_candidate_refs": eval_candidate_refs,
        "prl_artifact_index_ref": prl_artifact_index_ref,
        "prl_gate_result_ref": prl_gate_result_ref,
        "intake_status": intake_status,
        "candidate_count": len(eval_candidate_refs),
        "accepted_candidate_refs": accepted,
        "rejected_candidate_refs": rejected,
        "reason_codes": reason_codes,
        "coverage_intent": coverage_intent,
        "authority_scope": "observation_only",
        "evidence_hash": evidence_hash,
        "gate_recommendation": gate_recommendation,
    }
    _validate(artifact)
    return artifact
