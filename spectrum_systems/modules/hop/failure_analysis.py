"""Causal failure-hypothesis builder.

Consumes a :func:`trace_diff.compute_trace_diff` artifact plus the two
candidate payloads it compares, and emits a structured
``hop_harness_failure_hypothesis`` whose ``stage`` is ``causal_analysis``.

Hypothesis fields (in addition to the BATCH-1 surface):

- ``baseline_candidate_id`` — reference candidate the regression is
  measured against;
- ``observed_change`` — ``regression``, ``improvement``, or ``neutral``;
- ``diff_summary`` — added/removed line counts and changed payload
  fields;
- ``suspected_cause`` — short, structurally-derived label
  (e.g. ``shared_regression_in_adversarial_cases``); never a free-form
  LLM string;
- ``eval_deltas`` — per-case pass/fail deltas mirrored from the trace
  diff;
- ``trace_excerpts`` — bounded list of trace artifact ids and one-line
  human summaries (deterministic);
- ``confidence`` — a derived [0, 1] score: the fraction of shared
  changes vs total case diffs, clamped.

The module never invents evidence. Every field is sourced from the
trace diff or the candidate payloads themselves.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact

_MAX_EVAL_DELTAS = 64
_MAX_TRACE_EXCERPTS = 16
_MAX_DIFF_SUMMARY_CHARS = 4000


class FailureAnalysisError(Exception):
    """Raised when the analyzer cannot produce a valid hypothesis."""


@dataclass(frozen=True)
class HypothesisInputs:
    """Bundle the inputs the analyzer needs to author a single hypothesis."""

    baseline_candidate: Mapping[str, Any]
    candidate: Mapping[str, Any]
    trace_diff: Mapping[str, Any]


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _diff_summary(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    baseline_source = baseline.get("code_source") or ""
    candidate_source = candidate.get("code_source") or ""
    differ = difflib.unified_diff(
        baseline_source.splitlines(keepends=False),
        candidate_source.splitlines(keepends=False),
        n=1,
        lineterm="",
    )
    added = 0
    removed = 0
    summary_lines: list[str] = []
    for line in differ:
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
            summary_lines.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
            summary_lines.append(line)
    summary = "\n".join(summary_lines)
    if len(summary) > _MAX_DIFF_SUMMARY_CHARS:
        summary = summary[:_MAX_DIFF_SUMMARY_CHARS] + "\n...[truncated]"

    changed_fields: list[str] = []
    for key in sorted(set(baseline.keys()) | set(candidate.keys())):
        if key in ("artifact_id", "content_hash", "created_at", "trace"):
            continue
        if baseline.get(key) != candidate.get(key):
            changed_fields.append(key)

    return {
        "changed_fields": changed_fields,
        "added_lines": added,
        "removed_lines": removed,
        "summary": summary,
    }


def _classify_observed(score_delta: Mapping[str, Any]) -> str:
    score_change = float(score_delta.get("score", 0.0))
    if score_change > 0:
        return "improvement"
    if score_change < 0:
        return "regression"
    return "neutral"


def _suspected_cause(trace_diff: Mapping[str, Any], observed: str) -> str:
    shared = trace_diff.get("shared_changes") or []
    isolated = trace_diff.get("isolated_changes") or []
    conflicting = trace_diff.get("conflicting_signals") or []
    if conflicting:
        return "conflicting_signals_present"
    if shared:
        kinds = sorted({entry["kind"] for entry in shared})
        return "shared_" + "_and_".join(kinds)
    if isolated:
        kinds = sorted({entry["kind"] for entry in isolated})
        return "isolated_" + "_and_".join(kinds)
    if observed == "neutral":
        return "no_observable_per_case_movement"
    return f"unattributed_{observed}"


def _eval_deltas(
    trace_diff: Mapping[str, Any],
) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for entry in trace_diff.get("case_diffs", []):
        if entry.get("kind") in ("regression", "improvement"):
            deltas.append(
                {
                    "eval_case_id": entry["eval_case_id"],
                    "baseline_passed": entry["baseline_passed"],
                    "candidate_passed": entry["candidate_passed"],
                    "baseline_failure_reason": entry.get("baseline_failure_reason"),
                    "candidate_failure_reason": entry.get("candidate_failure_reason"),
                }
            )
        if len(deltas) >= _MAX_EVAL_DELTAS:
            break
    return deltas


def _trace_excerpts(
    trace_diff: Mapping[str, Any],
) -> list[dict[str, Any]]:
    excerpts: list[dict[str, Any]] = []
    for entry in trace_diff.get("case_diffs", []):
        if entry.get("kind") not in ("regression", "improvement"):
            continue
        b_hash = entry.get("baseline_output_hash") or "missing"
        c_hash = entry.get("candidate_output_hash") or "missing"
        b_complete = entry.get("baseline_trace_complete")
        c_complete = entry.get("candidate_trace_complete")
        summary = (
            f"kind={entry['kind']} "
            f"baseline_complete={b_complete} candidate_complete={c_complete} "
            f"baseline_output_hash={b_hash[:16]} candidate_output_hash={c_hash[:16]}"
        )
        excerpts.append(
            {
                "trace_artifact_id": (
                    entry.get("candidate_output_hash")
                    or entry.get("baseline_output_hash")
                    or "missing"
                ),
                "eval_case_id": entry["eval_case_id"],
                "summary": summary[:1024],
            }
        )
        if len(excerpts) >= _MAX_TRACE_EXCERPTS:
            break
    return excerpts


def _confidence(trace_diff: Mapping[str, Any]) -> float:
    case_diffs = trace_diff.get("case_diffs") or []
    moves = sum(1 for c in case_diffs if c.get("kind") in ("regression", "improvement"))
    if not moves:
        return 0.0
    shared = sum(len(g.get("eval_case_ids", [])) for g in trace_diff.get("shared_changes", []) or [])
    raw = shared / max(moves, 1)
    return max(0.0, min(1.0, raw))


def build_failure_hypothesis(
    inputs: HypothesisInputs,
    *,
    trace_id: str = "hop_failure_analysis",
) -> dict[str, Any]:
    """Author a structured causal-analysis failure hypothesis."""
    if not isinstance(inputs, HypothesisInputs):
        raise FailureAnalysisError("hop_failure_analysis_invalid_inputs")
    diff = inputs.trace_diff
    if diff.get("artifact_type") != "hop_harness_trace_diff":
        raise FailureAnalysisError("hop_failure_analysis_bad_diff_artifact")

    baseline_id = inputs.baseline_candidate.get("candidate_id")
    candidate_id = inputs.candidate.get("candidate_id")
    if not isinstance(baseline_id, str) or not isinstance(candidate_id, str):
        raise FailureAnalysisError("hop_failure_analysis_missing_candidate_ids")
    if diff.get("baseline_candidate_id") != baseline_id:
        raise FailureAnalysisError("hop_failure_analysis_baseline_mismatch")
    if diff.get("candidate_id") != candidate_id:
        raise FailureAnalysisError("hop_failure_analysis_candidate_mismatch")

    score_delta = diff.get("score_delta") or {}
    observed = _classify_observed(score_delta)

    failure_class_map = {
        "regression": "regression",
        "improvement": "improvement",
        "neutral": "neutral_change",
    }
    failure_class = failure_class_map[observed]

    severity_map = {
        "regression": "warn",
        "improvement": "info",
        "neutral_change": "info",
    }
    severity = severity_map[failure_class]
    release_block_signal = severity == "reject"

    diff_summary = _diff_summary(inputs.baseline_candidate, inputs.candidate)
    suspected_cause = _suspected_cause(diff, observed)
    eval_deltas = _eval_deltas(diff)
    trace_excerpts = _trace_excerpts(diff)
    confidence = _confidence(diff)

    evidence: list[dict[str, str]] = [
        {
            "kind": "comparison",
            "detail": (
                f"baseline_candidate_id={baseline_id} candidate_id={candidate_id} "
                f"observed={observed} "
                f"score_delta={score_delta.get('score', 0.0):+.4f}"
            ),
        },
        {
            "kind": "snippet",
            "detail": "suspected_cause=" + suspected_cause,
        },
    ]
    if diff_summary["summary"]:
        evidence.append(
            {
                "kind": "snippet",
                "detail": "diff_lines=" + diff_summary["summary"][:500],
            }
        )
    if eval_deltas:
        evidence.append(
            {
                "kind": "eval_case_id",
                "detail": ",".join(d["eval_case_id"] for d in eval_deltas[:8]),
            }
        )

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[diff.get("diff_id"), baseline_id, candidate_id],
        ),
        "hypothesis_id": f"causal_{candidate_id}_vs_{baseline_id}",
        "candidate_id": candidate_id,
        "run_id": diff.get("candidate_run_id"),
        "stage": "causal_analysis",
        "failure_class": failure_class,
        "severity": severity,
        "evidence": evidence,
        "detected_at": _utcnow(),
        "release_block_signal": release_block_signal,
        "baseline_candidate_id": baseline_id,
        "observed_change": observed,
        "diff_summary": diff_summary,
        "suspected_cause": suspected_cause,
        "eval_deltas": eval_deltas,
        "trace_excerpts": trace_excerpts,
        "confidence": confidence,
    }
    finalize_artifact(payload, id_prefix="hop_failure_")
    validate_hop_artifact(payload, "hop_harness_failure_hypothesis")
    return payload
