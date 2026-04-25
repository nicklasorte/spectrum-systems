"""
Pipeline Eval Runner — spectrum_systems/modules/evaluation/pipeline_eval_runner.py

Baseline eval runner for the transcript-to-study pipeline (PRE-4).
Implements three canonical eval types required before any pipeline output may be trusted:

  schema_conformance    — artifact passes schema validation
  replay_consistency    — same inputs produce same content_hash
  trace_completeness    — trace_id and span_id present and well-formed

Rules:
- missing eval → FAIL (fail-closed)
- indeterminate result → FAIL (fail-closed)
- all required eval types must pass before a block is cleared
- no free-text evaluation results — all outcomes are structured
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)

_TRACE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_SPAN_ID_RE = re.compile(r"^[a-f0-9]{16}$")

REQUIRED_EVAL_TYPES = frozenset(["schema_conformance", "replay_consistency", "trace_completeness"])


class EvalStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    # indeterminate is treated as FAIL — fail-closed


class EvalBlockedError(RuntimeError):
    """Raised when an eval gate blocks progression. Carries reason_codes."""

    def __init__(self, message: str, reason_codes: List[str], eval_summary: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes
        self.eval_summary = eval_summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_codes": self.reason_codes,
            "eval_summary": self.eval_summary,
        }


@dataclass
class EvalCaseResult:
    """Result for a single eval case execution."""

    eval_type: str
    artifact_id: str
    status: EvalStatus
    reason_codes: List[str] = field(default_factory=list)
    detail: Optional[str] = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_type": self.eval_type,
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "reason_codes": self.reason_codes,
            "detail": self.detail,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class EvalSummary:
    """Aggregated result for all eval cases run against an artifact."""

    artifact_id: str
    overall_status: EvalStatus
    case_results: List[EvalCaseResult] = field(default_factory=list)
    missing_eval_types: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "overall_status": self.overall_status.value,
            "case_results": [r.to_dict() for r in self.case_results],
            "missing_eval_types": self.missing_eval_types,
            "reason_codes": self.reason_codes,
            "evaluated_at": self.evaluated_at,
        }


def run_eval_case(
    eval_type: str,
    artifact: Dict[str, Any],
    *,
    replay_inputs: Optional[Dict[str, Any]] = None,
    replay_fn: Optional[Any] = None,
) -> EvalCaseResult:
    """Run a single eval case against an artifact.

    Parameters
    ----------
    eval_type:
        One of: 'schema_conformance', 'replay_consistency', 'trace_completeness'.
    artifact:
        The artifact dict to evaluate.
    replay_inputs:
        For 'replay_consistency': the original inputs used to produce the artifact.
    replay_fn:
        For 'replay_consistency': callable(inputs) -> artifact dict for replay.

    Returns
    -------
    EvalCaseResult with status PASS or FAIL.
    """
    artifact_id = artifact.get("artifact_id", "<unknown>")

    if eval_type not in REQUIRED_EVAL_TYPES:
        return EvalCaseResult(
            eval_type=eval_type,
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["UNKNOWN_EVAL_TYPE"],
            detail=f"Unrecognized eval_type: {eval_type!r}. Must be one of {sorted(REQUIRED_EVAL_TYPES)}",
        )

    if eval_type == "schema_conformance":
        return _eval_schema_conformance(artifact)

    if eval_type == "trace_completeness":
        return _eval_trace_completeness(artifact)

    if eval_type == "replay_consistency":
        return _eval_replay_consistency(artifact, replay_inputs=replay_inputs, replay_fn=replay_fn)

    return EvalCaseResult(
        eval_type=eval_type,
        artifact_id=artifact_id,
        status=EvalStatus.FAIL,
        reason_codes=["UNHANDLED_EVAL_TYPE"],
        detail="Eval type not implemented",
    )


def _eval_schema_conformance(artifact: Dict[str, Any]) -> EvalCaseResult:
    artifact_id = artifact.get("artifact_id", "<unknown>")

    for field_name in ("artifact_id", "schema_ref", "content_hash", "trace", "provenance"):
        if field_name not in artifact:
            return EvalCaseResult(
                eval_type="schema_conformance",
                artifact_id=artifact_id,
                status=EvalStatus.FAIL,
                reason_codes=["MISSING_REQUIRED_FIELD"],
                detail=f"Required field missing: {field_name!r}",
            )

    schema_ref = artifact.get("schema_ref", "")
    if not isinstance(schema_ref, str) or not schema_ref.startswith("transcript_pipeline/"):
        return EvalCaseResult(
            eval_type="schema_conformance",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["INVALID_SCHEMA_REF"],
            detail=f"schema_ref must start with 'transcript_pipeline/', got: {schema_ref!r}",
        )

    try:
        from spectrum_systems.modules.runtime.artifact_store import _load_schema, _validate_schema
        schema = _load_schema(schema_ref)
        _validate_schema(artifact, schema)
    except ArtifactStoreError as exc:
        return EvalCaseResult(
            eval_type="schema_conformance",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=[exc.reason_code, "SCHEMA_CONFORMANCE_FAILED"],
            detail=str(exc),
        )

    expected_hash = compute_content_hash(artifact)
    provided_hash = artifact.get("content_hash", "")
    if provided_hash != expected_hash:
        return EvalCaseResult(
            eval_type="schema_conformance",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["CONTENT_HASH_MISMATCH"],
            detail=f"content_hash mismatch: provided={provided_hash!r}, expected={expected_hash!r}",
        )

    return EvalCaseResult(
        eval_type="schema_conformance",
        artifact_id=artifact_id,
        status=EvalStatus.PASS,
        reason_codes=[],
        detail="All schema conformance checks passed including content_hash",
    )


def _eval_trace_completeness(artifact: Dict[str, Any]) -> EvalCaseResult:
    artifact_id = artifact.get("artifact_id", "<unknown>")

    trace = artifact.get("trace")
    if not isinstance(trace, dict):
        return EvalCaseResult(
            eval_type="trace_completeness",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["MISSING_TRACE"],
            detail="Artifact is missing 'trace' object",
        )

    trace_id = trace.get("trace_id", "")
    if not _TRACE_ID_RE.match(str(trace_id)):
        return EvalCaseResult(
            eval_type="trace_completeness",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["INVALID_TRACE_ID"],
            detail=f"trace_id must be 32 lowercase hex chars, got: {trace_id!r}",
        )

    span_id = trace.get("span_id", "")
    if not _SPAN_ID_RE.match(str(span_id)):
        return EvalCaseResult(
            eval_type="trace_completeness",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["INVALID_SPAN_ID"],
            detail=f"span_id must be 16 lowercase hex chars, got: {span_id!r}",
        )

    return EvalCaseResult(
        eval_type="trace_completeness",
        artifact_id=artifact_id,
        status=EvalStatus.PASS,
        reason_codes=[],
        detail="trace_id and span_id present and well-formed",
    )


def _eval_replay_consistency(
    artifact: Dict[str, Any],
    *,
    replay_inputs: Optional[Dict[str, Any]],
    replay_fn: Optional[Any],
) -> EvalCaseResult:
    """Verify replay produces the same content_hash as the original artifact.

    CONTRACT: replay_fn MUST be deterministic. Given the same replay_inputs, it must
    always produce a functionally equivalent artifact (same content, same hash).
    Passing a non-deterministic replay_fn violates this contract and renders the
    eval result meaningless. Callers are responsible for ensuring determinism.
    """
    artifact_id = artifact.get("artifact_id", "<unknown>")

    if replay_inputs is None or replay_fn is None:
        return EvalCaseResult(
            eval_type="replay_consistency",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["REPLAY_INPUTS_MISSING"],
            detail="replay_inputs and replay_fn are required for replay_consistency eval",
        )

    try:
        replayed = replay_fn(replay_inputs)
    except Exception as exc:
        return EvalCaseResult(
            eval_type="replay_consistency",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["REPLAY_EXECUTION_FAILED"],
            detail=f"Replay function raised: {type(exc).__name__}: {exc}",
        )

    if not isinstance(replayed, dict):
        return EvalCaseResult(
            eval_type="replay_consistency",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["REPLAY_INVALID_OUTPUT"],
            detail="Replay function returned non-dict output",
        )

    original_hash = compute_content_hash(artifact)
    replayed_hash = compute_content_hash(replayed)

    if original_hash != replayed_hash:
        return EvalCaseResult(
            eval_type="replay_consistency",
            artifact_id=artifact_id,
            status=EvalStatus.FAIL,
            reason_codes=["REPLAY_HASH_MISMATCH"],
            detail=f"Content hash mismatch: original={original_hash}, replayed={replayed_hash}",
        )

    return EvalCaseResult(
        eval_type="replay_consistency",
        artifact_id=artifact_id,
        status=EvalStatus.PASS,
        reason_codes=[],
        detail="Replay produced identical content_hash",
    )


def aggregate_eval_summary(
    artifact_id: str,
    case_results: List[EvalCaseResult],
) -> EvalSummary:
    """Aggregate individual eval case results into a summary.

    Fail-closed: missing required eval types → FAIL.
    Any individual FAIL → overall FAIL.
    """
    present_types = {r.eval_type for r in case_results}
    missing = sorted(REQUIRED_EVAL_TYPES - present_types)

    reason_codes: List[str] = []
    if missing:
        reason_codes.append("MISSING_REQUIRED_EVALS")

    failed = [r for r in case_results if r.status != EvalStatus.PASS]
    if failed:
        reason_codes.append("EVAL_CASE_FAILED")

    if missing or failed:
        overall = EvalStatus.FAIL
    else:
        overall = EvalStatus.PASS

    return EvalSummary(
        artifact_id=artifact_id,
        overall_status=overall,
        case_results=case_results,
        missing_eval_types=missing,
        reason_codes=reason_codes,
    )


def enforce_eval_gate(summary: EvalSummary) -> None:
    """Block progression if eval summary is not PASS.

    Raises EvalBlockedError with reason_codes if not all evals pass.
    Missing evals → BLOCK. Any failure → BLOCK. Indeterminate → BLOCK.
    """
    if summary.overall_status != EvalStatus.PASS:
        detail_parts = []
        if summary.missing_eval_types:
            detail_parts.append(f"Missing eval types: {summary.missing_eval_types}")
        failed = [r for r in summary.case_results if r.status != EvalStatus.PASS]
        if failed:
            detail_parts.append(f"Failed evals: {[r.eval_type for r in failed]}")

        raise EvalBlockedError(
            f"Eval gate BLOCKED for artifact {summary.artifact_id}: " + "; ".join(detail_parts),
            reason_codes=summary.reason_codes or ["EVAL_GATE_BLOCKED"],
            eval_summary=summary.to_dict(),
        )


__all__ = [
    "EvalStatus",
    "EvalCaseResult",
    "EvalSummary",
    "EvalBlockedError",
    "REQUIRED_EVAL_TYPES",
    "run_eval_case",
    "aggregate_eval_summary",
    "enforce_eval_gate",
]
