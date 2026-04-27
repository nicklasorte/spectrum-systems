"""
EvalGate — spectrum_systems/modules/transcript_pipeline/eval_gate.py

CPL-03 — Deterministic, fail-closed eval gate over a transcript_artifact +
context_bundle pair. Produces two governed artifacts:

  * ``eval_summary`` — structured per-eval results and an overall_status
    (pass | fail). Aggregated from five required eval names:
        schema_conformance, trace_completeness, referential_integrity,
        replay_consistency, coverage.
  * ``gate_evidence`` — wraps the eval_summary and reports a structured
    gate_status (passed_gate | failed_gate | conditional_gate | missing_gate).
    The artifact carries evidence only; canonical routing remains with the
    appropriate canonical owner.

Hard rules (CPL-03):
- NO LLM. NO routing logic. NO authority vocabulary.
- Pure function returns payloads WITHOUT ``content_hash``; the PQX harness owns
  registration and hash minting. Use ``run_eval_gate_via_pqx`` for the only
  sanctioned governed entrypoint.
- Fail-closed: missing or malformed inputs raise ``EvalGateError``; an absent
  eval surfaces overall_status=fail and gate_status=missing_gate; any failed
  eval surfaces gate_status=failed_gate.
- Deterministic: same inputs => identical eval_results, identical artifact ids,
  identical hashes (modulo trace and created_at, which are excluded from the
  artifact ``content_hash``).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
)
from spectrum_systems.modules.runtime.hash_utils import compute_content_hash

PRODUCED_BY = "transcript_eval_gate"

EVAL_SUMMARY_ARTIFACT_TYPE = "eval_summary"
EVAL_SUMMARY_SCHEMA_REF = "transcript_pipeline/eval_summary"
EVAL_SUMMARY_SCHEMA_VERSION = "1.0.0"

GATE_EVIDENCE_ARTIFACT_TYPE = "gate_evidence"
GATE_EVIDENCE_SCHEMA_REF = "transcript_pipeline/gate_evidence"
GATE_EVIDENCE_SCHEMA_VERSION = "1.0.0"

EVAL_NAME_SCHEMA = "schema_conformance"
EVAL_NAME_TRACE = "trace_completeness"
EVAL_NAME_REFERENTIAL = "referential_integrity"
EVAL_NAME_REPLAY = "replay_consistency"
EVAL_NAME_COVERAGE = "coverage"

REQUIRED_EVAL_NAMES: Tuple[str, ...] = (
    EVAL_NAME_SCHEMA,
    EVAL_NAME_TRACE,
    EVAL_NAME_REFERENTIAL,
    EVAL_NAME_REPLAY,
    EVAL_NAME_COVERAGE,
)

GATE_STATUS_PASSED = "passed_gate"
GATE_STATUS_FAILED = "failed_gate"
GATE_STATUS_CONDITIONAL = "conditional_gate"
GATE_STATUS_MISSING = "missing_gate"

STATUS_PASS = "pass"
STATUS_FAIL = "fail"

_TXA_ID_RE = re.compile(r"^TXA-[A-Z0-9_-]+$")
_CTX_ID_RE = re.compile(r"^CTX-[A-Z0-9_-]+$")
_TRACE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_SPAN_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_TURN_ID_RE = re.compile(r"^T-[0-9]{4,}$")


class EvalGateError(RuntimeError):
    """Raised when the eval gate cannot run deterministically.

    This is reserved for inputs that are structurally unusable — e.g. wrong
    artifact_type, non-mapping inputs, missing critical envelope fields. When
    the gate CAN run, even a wholly failing run still produces an eval_summary
    and gate_evidence pair (with gate_status=failed_gate or missing_gate).
    """

    def __init__(self, message: str, reason_code: str, target_artifact_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.target_artifact_id = target_artifact_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reason_code": self.reason_code,
            "target_artifact_id": self.target_artifact_id,
        }


# ---------------------------------------------------------------------------
# Time + identity helpers
# ---------------------------------------------------------------------------


def _utc_iso(clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> str:
    return clock().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _short_fingerprint(payload: Any) -> str:
    """Deterministic 12-char uppercase fingerprint over a JSON-canonical payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()


def _derive_eval_summary_id(
    evaluated_artifact_ids: Sequence[str],
    eval_results: Sequence[Mapping[str, Any]],
) -> str:
    fingerprint = _short_fingerprint(
        {
            "evaluated_artifact_ids": list(evaluated_artifact_ids),
            "eval_results": [
                {
                    "eval_name": r["eval_name"],
                    "status": r["status"],
                    "reason_codes": list(r.get("reason_codes", [])),
                }
                for r in eval_results
            ],
        }
    )
    return f"EVS-{fingerprint}"


def _derive_gate_evidence_id(
    target_artifact_ids: Sequence[str],
    gate_status: str,
    eval_summary_id: str,
) -> str:
    fingerprint = _short_fingerprint(
        {
            "target_artifact_ids": list(target_artifact_ids),
            "gate_status": gate_status,
            "eval_summary_id": eval_summary_id,
        }
    )
    return f"GTE-{fingerprint}"


# ---------------------------------------------------------------------------
# Eval primitives — each returns (status, reason_codes, detail)
# ---------------------------------------------------------------------------


def _eval_schema_conformance(
    transcript: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    reason_codes: List[str] = []

    if transcript.get("artifact_type") != "transcript_artifact":
        reason_codes.append("TRANSCRIPT_ARTIFACT_TYPE_MISMATCH")
    if transcript.get("schema_ref") != "transcript_pipeline/transcript_artifact":
        reason_codes.append("TRANSCRIPT_SCHEMA_REF_MISMATCH")
    if not isinstance(transcript.get("artifact_id"), str) or not _TXA_ID_RE.match(transcript.get("artifact_id", "")):
        reason_codes.append("TRANSCRIPT_ARTIFACT_ID_INVALID")

    if bundle.get("artifact_type") != "context_bundle":
        reason_codes.append("BUNDLE_ARTIFACT_TYPE_MISMATCH")
    if bundle.get("schema_ref") != "transcript_pipeline/context_bundle":
        reason_codes.append("BUNDLE_SCHEMA_REF_MISMATCH")
    if not isinstance(bundle.get("artifact_id"), str) or not _CTX_ID_RE.match(bundle.get("artifact_id", "")):
        reason_codes.append("BUNDLE_ARTIFACT_ID_INVALID")
    if bundle.get("source_artifact_id") != transcript.get("artifact_id"):
        reason_codes.append("BUNDLE_SOURCE_LINK_MISMATCH")

    # Full schema validation through the artifact store loader.
    try:
        from spectrum_systems.modules.runtime.artifact_store import (
            _load_schema,
            _validate_schema,
        )
        for label, artifact in (("TRANSCRIPT", transcript), ("BUNDLE", bundle)):
            schema_ref = artifact.get("schema_ref", "")
            if not isinstance(schema_ref, str) or not schema_ref.startswith("transcript_pipeline/"):
                reason_codes.append(f"{label}_INVALID_SCHEMA_REF")
                continue
            schema = _load_schema(schema_ref)
            try:
                _validate_schema(dict(artifact), schema)
            except ArtifactStoreError as exc:
                reason_codes.append(f"{label}_SCHEMA_VALIDATION_FAILED")
    except ArtifactStoreError as exc:
        reason_codes.append("SCHEMA_LOADER_FAILED")

    # Verify content_hash if present (artifacts already registered in PQX path).
    for label, artifact in (("TRANSCRIPT", transcript), ("BUNDLE", bundle)):
        provided = artifact.get("content_hash")
        if provided is None:
            continue
        try:
            expected = compute_content_hash(dict(artifact))
        except Exception:
            reason_codes.append(f"{label}_CONTENT_HASH_UNCOMPUTABLE")
            continue
        if provided != expected:
            reason_codes.append(f"{label}_CONTENT_HASH_MISMATCH")

    return _result(EVAL_NAME_SCHEMA, reason_codes, target_id=bundle.get("artifact_id"))


def _eval_trace_completeness(
    transcript: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    reason_codes: List[str] = []

    for label, artifact in (("TRANSCRIPT", transcript), ("BUNDLE", bundle)):
        trace = artifact.get("trace")
        if not isinstance(trace, Mapping):
            reason_codes.append(f"{label}_TRACE_MISSING")
            continue
        trace_id = trace.get("trace_id", "")
        span_id = trace.get("span_id", "")
        if not isinstance(trace_id, str) or not _TRACE_ID_RE.match(trace_id):
            reason_codes.append(f"{label}_TRACE_ID_INVALID")
        if not isinstance(span_id, str) or not _SPAN_ID_RE.match(span_id):
            reason_codes.append(f"{label}_SPAN_ID_INVALID")

    return _result(EVAL_NAME_TRACE, reason_codes, target_id=bundle.get("artifact_id"))


def _eval_referential_integrity(
    transcript: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    reason_codes: List[str] = []

    speaker_turns = transcript.get("speaker_turns")
    segments = bundle.get("segments")

    if not isinstance(speaker_turns, list) or not speaker_turns:
        reason_codes.append("TRANSCRIPT_SPEAKER_TURNS_MISSING")
        return _result(EVAL_NAME_REFERENTIAL, reason_codes, target_id=bundle.get("artifact_id"))
    if not isinstance(segments, list) or not segments:
        reason_codes.append("BUNDLE_SEGMENTS_MISSING")
        return _result(EVAL_NAME_REFERENTIAL, reason_codes, target_id=bundle.get("artifact_id"))

    turn_index: Dict[str, Mapping[str, Any]] = {}
    for turn in speaker_turns:
        if not isinstance(turn, Mapping):
            reason_codes.append("TRANSCRIPT_TURN_MALFORMED")
            return _result(EVAL_NAME_REFERENTIAL, reason_codes, target_id=bundle.get("artifact_id"))
        tid = turn.get("turn_id")
        if not isinstance(tid, str) or not _TURN_ID_RE.match(tid):
            reason_codes.append("TRANSCRIPT_TURN_ID_INVALID")
            return _result(EVAL_NAME_REFERENTIAL, reason_codes, target_id=bundle.get("artifact_id"))
        if tid in turn_index:
            reason_codes.append("TRANSCRIPT_DUPLICATE_TURN_ID")
            return _result(EVAL_NAME_REFERENTIAL, reason_codes, target_id=bundle.get("artifact_id"))
        turn_index[tid] = turn

    seen_segment_ids: set[str] = set()
    for idx, seg in enumerate(segments):
        if not isinstance(seg, Mapping):
            reason_codes.append("BUNDLE_SEGMENT_MALFORMED")
            continue
        sid = seg.get("segment_id")
        if not isinstance(sid, str):
            reason_codes.append("BUNDLE_SEGMENT_ID_INVALID")
            continue
        if sid in seen_segment_ids:
            reason_codes.append("BUNDLE_DUPLICATE_SEGMENT_ID")
        seen_segment_ids.add(sid)

        source_turn_id = seg.get("source_turn_id")
        if source_turn_id not in turn_index:
            reason_codes.append("ORPHAN_SEGMENT")
            continue

        # 1:1 alignment: segment[i] must match turn at the same ordinal position.
        if idx >= len(speaker_turns):
            reason_codes.append("BUNDLE_SEGMENT_OUT_OF_RANGE")
            continue
        expected_turn = speaker_turns[idx]
        if (
            seg.get("source_turn_id") != expected_turn.get("turn_id")
            or seg.get("speaker") != expected_turn.get("speaker")
            or seg.get("text") != expected_turn.get("text")
            or seg.get("line_index") != expected_turn.get("line_index")
        ):
            reason_codes.append("SEGMENT_TURN_DRIFT")

    return _result(EVAL_NAME_REFERENTIAL, reason_codes, target_id=bundle.get("artifact_id"))


def _eval_replay_consistency(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    reason_codes: List[str] = []

    segments = bundle.get("segments")
    provided_manifest = bundle.get("manifest_hash")

    if not isinstance(segments, list) or not segments:
        reason_codes.append("BUNDLE_SEGMENTS_MISSING")
        return _result(EVAL_NAME_REPLAY, reason_codes, target_id=bundle.get("artifact_id"))
    if not isinstance(provided_manifest, str) or not provided_manifest.startswith("sha256:"):
        reason_codes.append("BUNDLE_MANIFEST_HASH_MISSING")
        return _result(EVAL_NAME_REPLAY, reason_codes, target_id=bundle.get("artifact_id"))

    # Re-derive the manifest deterministically using the same canonicalisation
    # as context_bundle_assembler._compute_manifest_hash. Re-implemented here
    # rather than imported to keep the eval gate free of cross-module coupling
    # to the assembler's private helpers.
    canonical_segments: List[Dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, Mapping):
            reason_codes.append("BUNDLE_SEGMENT_MALFORMED")
            return _result(EVAL_NAME_REPLAY, reason_codes, target_id=bundle.get("artifact_id"))
        canonical_segments.append(
            {
                "segment_id": seg.get("segment_id"),
                "speaker": seg.get("speaker"),
                "text": seg.get("text"),
                "source_turn_id": seg.get("source_turn_id"),
                "line_index": seg.get("line_index"),
            }
        )
    canonical = json.dumps(
        canonical_segments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if expected != provided_manifest:
        reason_codes.append("REPLAY_MANIFEST_HASH_MISMATCH")

    return _result(EVAL_NAME_REPLAY, reason_codes, target_id=bundle.get("artifact_id"))


def _eval_coverage(
    transcript: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    reason_codes: List[str] = []
    speaker_turns = transcript.get("speaker_turns")
    segments = bundle.get("segments")

    if not isinstance(speaker_turns, list):
        reason_codes.append("TRANSCRIPT_SPEAKER_TURNS_MISSING")
    if not isinstance(segments, list):
        reason_codes.append("BUNDLE_SEGMENTS_MISSING")
    if reason_codes:
        return _result(EVAL_NAME_COVERAGE, reason_codes, target_id=bundle.get("artifact_id"))

    if len(segments) != len(speaker_turns):
        reason_codes.append("COVERAGE_COUNT_MISMATCH")

    return _result(EVAL_NAME_COVERAGE, reason_codes, target_id=bundle.get("artifact_id"))


def _result(
    eval_name: str,
    reason_codes: Sequence[str],
    *,
    target_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Materialise a single eval_result dict — fail-closed if reason_codes non-empty."""
    status = STATUS_PASS if not reason_codes else STATUS_FAIL
    payload: Dict[str, Any] = {
        "eval_name": eval_name,
        "status": status,
        "reason_codes": list(reason_codes),
    }
    if target_id:
        payload["evaluated_artifact_id"] = target_id
    return payload


# ---------------------------------------------------------------------------
# Input validation (raises before any eval runs)
# ---------------------------------------------------------------------------


def _require_input_envelopes(
    transcript_artifact: Any,
    context_bundle: Any,
) -> Tuple[str, str]:
    if not isinstance(transcript_artifact, Mapping):
        raise EvalGateError(
            "transcript_artifact must be a mapping",
            reason_code="INVALID_TRANSCRIPT_INPUT_TYPE",
        )
    if not isinstance(context_bundle, Mapping):
        raise EvalGateError(
            "context_bundle must be a mapping",
            reason_code="INVALID_CONTEXT_BUNDLE_INPUT_TYPE",
        )

    txa_id = transcript_artifact.get("artifact_id")
    ctx_id = context_bundle.get("artifact_id")

    if transcript_artifact.get("artifact_type") != "transcript_artifact":
        raise EvalGateError(
            f"Expected transcript_artifact, got {transcript_artifact.get('artifact_type')!r}",
            reason_code="INVALID_TRANSCRIPT_ARTIFACT_TYPE",
            target_artifact_id=str(txa_id) if txa_id is not None else None,
        )
    if context_bundle.get("artifact_type") != "context_bundle":
        raise EvalGateError(
            f"Expected context_bundle, got {context_bundle.get('artifact_type')!r}",
            reason_code="INVALID_CONTEXT_BUNDLE_ARTIFACT_TYPE",
            target_artifact_id=str(ctx_id) if ctx_id is not None else None,
        )
    if not isinstance(txa_id, str) or not _TXA_ID_RE.match(txa_id):
        raise EvalGateError(
            f"transcript_artifact.artifact_id is invalid: {txa_id!r}",
            reason_code="INVALID_TRANSCRIPT_ARTIFACT_ID",
            target_artifact_id=str(txa_id) if txa_id is not None else None,
        )
    if not isinstance(ctx_id, str) or not _CTX_ID_RE.match(ctx_id):
        raise EvalGateError(
            f"context_bundle.artifact_id is invalid: {ctx_id!r}",
            reason_code="INVALID_CONTEXT_BUNDLE_ARTIFACT_ID",
            target_artifact_id=str(ctx_id) if ctx_id is not None else None,
        )

    return txa_id, ctx_id


# ---------------------------------------------------------------------------
# Aggregation + gate logic
# ---------------------------------------------------------------------------


def _aggregate_overall_status(
    eval_results: Sequence[Mapping[str, Any]],
) -> Tuple[str, List[str], List[str]]:
    """Aggregate eval_results into (overall_status, missing_eval_names, reason_codes)."""
    present_names = {r["eval_name"] for r in eval_results}
    missing = [name for name in REQUIRED_EVAL_NAMES if name not in present_names]
    failed = [r for r in eval_results if r.get("status") != STATUS_PASS]

    reason_codes: List[str] = []
    if missing:
        reason_codes.append("MISSING_REQUIRED_EVALS")
    if failed:
        reason_codes.append("EVAL_CASE_FAILED")

    overall_status = STATUS_FAIL if (missing or failed) else STATUS_PASS
    return overall_status, missing, reason_codes


def _gate_status_from_summary(summary: Mapping[str, Any]) -> str:
    """Fail-closed gate logic.

    missing eval        -> missing_gate
    any eval fails      -> failed_gate
    all pass            -> passed_gate
    indeterminate state -> conditional_gate (defaults to NOT routable)
    """
    missing = summary.get("missing_eval_names") or []
    if missing:
        return GATE_STATUS_MISSING

    eval_results = summary.get("eval_results") or []
    statuses = {r.get("status") for r in eval_results}

    if any(status == STATUS_FAIL for status in statuses):
        return GATE_STATUS_FAILED
    if statuses == {STATUS_PASS}:
        return GATE_STATUS_PASSED
    # Anything that is neither cleanly pass nor cleanly fail is conditional.
    # NOT routable by the schema-level routable convenience flag.
    return GATE_STATUS_CONDITIONAL


# ---------------------------------------------------------------------------
# Public deterministic entrypoint
# ---------------------------------------------------------------------------


def evaluate_transcript_context(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    *,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    run_id: Optional[str] = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the CPL-03 eval gate over (transcript_artifact, context_bundle).

    Returns
    -------
    (eval_summary_payload, gate_evidence_payload):
        Both payloads are returned WITHOUT ``content_hash``. The PQX harness /
        artifact store mints the hash and registers each artifact. The two
        payloads are linked: ``gate_evidence_payload['eval_summary_id']``
        equals ``eval_summary_payload['artifact_id']``.

    Raises
    ------
    EvalGateError
        On structurally unusable inputs (wrong artifact_type, non-mapping,
        invalid artifact_id format, invalid trace identifiers).

    Notes
    -----
    All five required evals run unconditionally. A failed eval surfaces in
    eval_results with reason_codes; the overall_status and gate_status reflect
    the aggregate. A genuinely missing eval entry surfaces as gate_status =
    missing_gate. fail-closed contract: there is no path that yields
    passed_gate when any eval is missing or failing.
    """
    txa_id, ctx_id = _require_input_envelopes(transcript_artifact, context_bundle)

    effective_trace_id = trace_id if trace_id is not None else "0" * 32
    effective_span_id = span_id if span_id is not None else "0" * 16
    if not _TRACE_ID_RE.match(effective_trace_id):
        raise EvalGateError(
            "trace_id must be a 32-char lowercase hex string",
            reason_code="INVALID_TRACE_ID",
            target_artifact_id=ctx_id,
        )
    if not _SPAN_ID_RE.match(effective_span_id):
        raise EvalGateError(
            "span_id must be a 16-char lowercase hex string",
            reason_code="INVALID_SPAN_ID",
            target_artifact_id=ctx_id,
        )

    # Run every required eval. Order is canonical and matches REQUIRED_EVAL_NAMES.
    eval_results: List[Dict[str, Any]] = [
        _eval_schema_conformance(transcript_artifact, context_bundle),
        _eval_trace_completeness(transcript_artifact, context_bundle),
        _eval_referential_integrity(transcript_artifact, context_bundle),
        _eval_replay_consistency(context_bundle),
        _eval_coverage(transcript_artifact, context_bundle),
    ]

    overall_status, missing_eval_names, summary_reason_codes = _aggregate_overall_status(eval_results)

    evaluated_artifact_ids = [txa_id, ctx_id]
    eval_summary_id = _derive_eval_summary_id(evaluated_artifact_ids, eval_results)

    created_at = _utc_iso(clock)
    summary_provenance: Dict[str, Any] = {
        "produced_by": PRODUCED_BY,
        "input_artifact_ids": evaluated_artifact_ids,
    }
    if run_id:
        summary_provenance["run_id"] = run_id

    eval_summary_payload: Dict[str, Any] = {
        "artifact_id": eval_summary_id,
        "artifact_type": EVAL_SUMMARY_ARTIFACT_TYPE,
        "schema_ref": EVAL_SUMMARY_SCHEMA_REF,
        "schema_version": EVAL_SUMMARY_SCHEMA_VERSION,
        "trace": {"trace_id": effective_trace_id, "span_id": effective_span_id},
        "provenance": summary_provenance,
        "created_at": created_at,
        "evaluated_artifact_ids": evaluated_artifact_ids,
        "eval_results": eval_results,
        "overall_status": overall_status,
        "missing_eval_names": missing_eval_names,
        "reason_codes": summary_reason_codes,
    }

    gate_status = _gate_status_from_summary(eval_summary_payload)
    gate_reason_codes = list(summary_reason_codes)
    for r in eval_results:
        if r.get("status") == STATUS_FAIL:
            gate_reason_codes.extend(r.get("reason_codes", []))
    # Stable, de-duplicated reason_codes preserving order of first appearance.
    seen: set[str] = set()
    deduped: List[str] = []
    for code in gate_reason_codes:
        if code not in seen:
            seen.add(code)
            deduped.append(code)

    target_artifact_ids = evaluated_artifact_ids
    gate_evidence_id = _derive_gate_evidence_id(target_artifact_ids, gate_status, eval_summary_id)

    gate_provenance: Dict[str, Any] = {
        "produced_by": PRODUCED_BY,
        "input_artifact_ids": [eval_summary_id, *target_artifact_ids],
    }
    if run_id:
        gate_provenance["run_id"] = run_id

    gate_evidence_payload: Dict[str, Any] = {
        "artifact_id": gate_evidence_id,
        "artifact_type": GATE_EVIDENCE_ARTIFACT_TYPE,
        "schema_ref": GATE_EVIDENCE_SCHEMA_REF,
        "schema_version": GATE_EVIDENCE_SCHEMA_VERSION,
        "trace": {"trace_id": effective_trace_id, "span_id": effective_span_id},
        "provenance": gate_provenance,
        "created_at": created_at,
        "target_artifact_ids": target_artifact_ids,
        "gate_status": gate_status,
        "eval_summary_id": eval_summary_id,
        "reason_codes": deduped,
        "routable": gate_status == GATE_STATUS_PASSED,
    }

    return eval_summary_payload, gate_evidence_payload


# ---------------------------------------------------------------------------
# Governed entrypoint — runs both artifacts through the PQX step harness
# ---------------------------------------------------------------------------


def run_eval_gate_via_pqx(
    transcript_artifact: Mapping[str, Any],
    context_bundle: Mapping[str, Any],
    artifact_store: ArtifactStore,
    *,
    parent_trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    summary_step_name: str = "eval_gate_summary",
    evidence_step_name: str = "eval_gate_evidence",
) -> Dict[str, Any]:
    """Run the CPL-03 eval gate through the PQX step harness.

    Two governed steps execute in sequence:

    1. ``eval_gate_summary``  — registers the eval_summary artifact.
    2. ``eval_gate_evidence`` — registers the gate_evidence artifact, with
       ``input_artifact_ids`` referencing the eval_summary id.

    Both steps share the same trace (parent_trace_id, or a freshly generated
    trace_id from step 1 inherited by step 2). Each step emits its own
    pqx_execution_record. There is no path that registers a gate_evidence
    artifact without first registering its corresponding eval_summary.

    Returns
    -------
    Dict with keys:
        eval_summary:  {execution_record, output_artifact}
        gate_evidence: {execution_record, output_artifact}

    Raises
    ------
    PQXExecutionError
        If either step fails. The exception carries the failing step's
        execution_record and reason_codes. The other step's record is left in
        the returned dict only when both steps succeed.
    """
    from spectrum_systems.modules.orchestration.pqx_step_harness import run_pqx_step

    txa_id = transcript_artifact.get("artifact_id") if isinstance(transcript_artifact, Mapping) else None
    ctx_id = context_bundle.get("artifact_id") if isinstance(context_bundle, Mapping) else None
    seed_input_ids: List[str] = [aid for aid in (txa_id, ctx_id) if isinstance(aid, str)]

    # Step 1 — eval_summary. The pure function is invoked with the harness-supplied
    # trace_id / span_id. We discard the gate_evidence payload here and re-derive it
    # in step 2 so each step produces exactly one artifact.
    def _summary_execution(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
        eval_summary_payload, _ = evaluate_transcript_context(
            inputs["transcript_artifact"],
            inputs["context_bundle"],
            trace_id=trace_id,
            span_id=span_id,
            run_id=inputs.get("run_id"),
        )
        return eval_summary_payload

    summary_result = run_pqx_step(
        summary_step_name,
        {
            "transcript_artifact": transcript_artifact,
            "context_bundle": context_bundle,
            "input_artifact_ids": seed_input_ids,
            "run_id": run_id,
        },
        _summary_execution,
        artifact_store,
        parent_trace_id=parent_trace_id,
        expected_output_type=EVAL_SUMMARY_ARTIFACT_TYPE,
    )

    # Step 2 — gate_evidence. Inherit trace from step 1 so both artifacts share it.
    summary_artifact = summary_result["output_artifact"]
    inherited_trace_id = summary_artifact["trace"]["trace_id"]

    def _evidence_execution(inputs: Dict[str, Any], trace_id: str, span_id: str) -> Dict[str, Any]:
        _, gate_evidence_payload = evaluate_transcript_context(
            inputs["transcript_artifact"],
            inputs["context_bundle"],
            trace_id=trace_id,
            span_id=span_id,
            run_id=inputs.get("run_id"),
        )
        # The eval_summary_id derived inside step 2 must match the one registered in
        # step 1 because evaluate_transcript_context is deterministic. Verify this
        # invariant explicitly so a drift (e.g., from non-deterministic input mutation
        # between steps) halts progression rather than producing inconsistent evidence.
        if gate_evidence_payload["eval_summary_id"] != inputs["registered_eval_summary_id"]:
            raise EvalGateError(
                "Re-derived eval_summary_id drifted from the registered eval_summary",
                reason_code="EVAL_SUMMARY_ID_DRIFT",
                target_artifact_id=gate_evidence_payload.get("artifact_id"),
            )
        return gate_evidence_payload

    evidence_result = run_pqx_step(
        evidence_step_name,
        {
            "transcript_artifact": transcript_artifact,
            "context_bundle": context_bundle,
            "registered_eval_summary_id": summary_artifact["artifact_id"],
            "input_artifact_ids": [summary_artifact["artifact_id"], *seed_input_ids],
            "run_id": run_id,
        },
        _evidence_execution,
        artifact_store,
        parent_trace_id=inherited_trace_id,
        expected_output_type=GATE_EVIDENCE_ARTIFACT_TYPE,
    )

    return {
        "eval_summary": summary_result,
        "gate_evidence": evidence_result,
    }


__all__ = [
    "EvalGateError",
    "evaluate_transcript_context",
    "run_eval_gate_via_pqx",
    "PRODUCED_BY",
    "EVAL_SUMMARY_ARTIFACT_TYPE",
    "EVAL_SUMMARY_SCHEMA_REF",
    "EVAL_SUMMARY_SCHEMA_VERSION",
    "GATE_EVIDENCE_ARTIFACT_TYPE",
    "GATE_EVIDENCE_SCHEMA_REF",
    "GATE_EVIDENCE_SCHEMA_VERSION",
    "REQUIRED_EVAL_NAMES",
    "EVAL_NAME_SCHEMA",
    "EVAL_NAME_TRACE",
    "EVAL_NAME_REFERENTIAL",
    "EVAL_NAME_REPLAY",
    "EVAL_NAME_COVERAGE",
    "GATE_STATUS_PASSED",
    "GATE_STATUS_FAILED",
    "GATE_STATUS_CONDITIONAL",
    "GATE_STATUS_MISSING",
    "STATUS_PASS",
    "STATUS_FAIL",
]
