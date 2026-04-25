"""Trace-diff miner for HOP harness candidates.

Compares two candidates by:

* their score artifacts (the five-objective deltas);
* their per-case trace artifacts (completeness + output hash);
* their FAQ outputs (where present).

Produces a ``hop_harness_trace_diff`` artifact that classifies each
shared eval case as ``regression``, ``improvement``, ``stable_pass``, or
``stable_fail`` and surfaces:

- **shared changes** — eval cases that move *together* in the same
  direction (a likely systematic effect of the candidate's mutation);
- **isolated changes** — single-case moves (likely incidental);
- **conflicting signals** — totals where regressions and improvements
  coexist (the candidate trades one failure mode for another).

The emitted artifact is the structured input the failure-analysis
module consumes when authoring causal hypotheses.

The miner is **read-only**: it never writes to the experience store and
never invokes the evaluator. The optimization loop or CLI is
responsible for persistence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


class TraceDiffError(Exception):
    """Raised when a trace diff cannot be computed (bad inputs)."""


@dataclass(frozen=True)
class TraceDiffInputs:
    """Bundle the artifacts the miner consumes for a single comparison.

    The miner expects already-validated payloads. The optimization loop
    and CLI front-ends validate at load time.
    """

    baseline_score: Mapping[str, Any]
    candidate_score: Mapping[str, Any]
    baseline_traces: tuple[Mapping[str, Any], ...]
    candidate_traces: tuple[Mapping[str, Any], ...]


def _index_traces_by_case(
    traces: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for trace in traces:
        case_id = trace.get("eval_case_id")
        if not isinstance(case_id, str):
            continue
        # Two traces for the same case_id should not exist within a single
        # run; if they do (concurrent re-run), keep the first.
        out.setdefault(case_id, trace)
    return out


def _index_breakdown_by_case(
    score: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for entry in score.get("breakdown", []) or []:
        case_id = entry.get("eval_case_id")
        if isinstance(case_id, str):
            out[case_id] = entry
    return out


def _classify(
    *, baseline_passed: bool, candidate_passed: bool
) -> str:
    if baseline_passed and candidate_passed:
        return "stable_pass"
    if not baseline_passed and not candidate_passed:
        return "stable_fail"
    if baseline_passed and not candidate_passed:
        return "regression"
    return "improvement"


def _score_delta(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, float]:
    keys = ("score", "cost", "latency_ms", "trace_completeness", "eval_coverage")
    return {key: float(candidate[key]) - float(baseline[key]) for key in keys}


def _detect_shared_changes(
    case_diffs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify groups of >=2 cases that moved in the same direction.

    Each group is a list of eval_case_ids that share the same kind of
    move (regression or improvement). With small case counts this is
    just "all regressions / all improvements"; we materialize both into
    the artifact so consumers can inspect them.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for entry in case_diffs:
        kind = entry["kind"]
        if kind in ("regression", "improvement"):
            groups[kind].append(entry["eval_case_id"])
    out: list[dict[str, Any]] = []
    for kind, cases in groups.items():
        if len(cases) >= 2:
            out.append(
                {
                    "kind": kind,
                    "eval_case_ids": sorted(cases),
                }
            )
    return out


def _detect_isolated_changes(
    case_diffs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify single-case moves (regression/improvement of count 1)."""
    counts: dict[str, list[str]] = defaultdict(list)
    for entry in case_diffs:
        counts[entry["kind"]].append(entry["eval_case_id"])
    out: list[dict[str, Any]] = []
    for kind in ("regression", "improvement"):
        cases = counts.get(kind, [])
        if len(cases) == 1:
            out.append({"kind": kind, "eval_case_id": cases[0]})
    return out


def _detect_conflicting(
    case_diffs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    regressions = sum(1 for c in case_diffs if c["kind"] == "regression")
    improvements = sum(1 for c in case_diffs if c["kind"] == "improvement")
    if regressions > 0 and improvements > 0:
        return [
            {
                "description": (
                    "candidate trades regressions for improvements: "
                    f"-{regressions} +{improvements}"
                ),
                "regression_count": regressions,
                "improvement_count": improvements,
            }
        ]
    return []


def compute_trace_diff(
    inputs: TraceDiffInputs,
    *,
    diff_id: str | None = None,
    trace_id: str = "hop_trace_diff",
) -> dict[str, Any]:
    """Compute a structured trace-diff artifact."""
    if not isinstance(inputs, TraceDiffInputs):
        raise TraceDiffError("hop_trace_diff_invalid_inputs")

    baseline_score = inputs.baseline_score
    candidate_score = inputs.candidate_score
    if baseline_score.get("eval_set_id") != candidate_score.get("eval_set_id"):
        raise TraceDiffError("hop_trace_diff_eval_set_mismatch")
    if baseline_score.get("eval_set_version") != candidate_score.get("eval_set_version"):
        raise TraceDiffError("hop_trace_diff_eval_set_version_mismatch")

    baseline_breakdown = _index_breakdown_by_case(baseline_score)
    candidate_breakdown = _index_breakdown_by_case(candidate_score)

    baseline_traces = _index_traces_by_case(inputs.baseline_traces)
    candidate_traces = _index_traces_by_case(inputs.candidate_traces)

    shared_case_ids = sorted(
        set(baseline_breakdown.keys()) & set(candidate_breakdown.keys())
    )

    case_diffs: list[dict[str, Any]] = []
    for case_id in shared_case_ids:
        b_entry = baseline_breakdown[case_id]
        c_entry = candidate_breakdown[case_id]
        b_passed = bool(b_entry.get("passed"))
        c_passed = bool(c_entry.get("passed"))
        b_trace = baseline_traces.get(case_id)
        c_trace = candidate_traces.get(case_id)
        case_diffs.append(
            {
                "eval_case_id": case_id,
                "baseline_passed": b_passed,
                "candidate_passed": c_passed,
                "kind": _classify(
                    baseline_passed=b_passed, candidate_passed=c_passed
                ),
                "baseline_failure_reason": b_entry.get("failure_reason"),
                "candidate_failure_reason": c_entry.get("failure_reason"),
                "baseline_trace_complete": (
                    bool(b_trace.get("complete")) if b_trace else None
                ),
                "candidate_trace_complete": (
                    bool(c_trace.get("complete")) if c_trace else None
                ),
                "baseline_output_hash": (b_trace.get("output_hash") if b_trace else None),
                "candidate_output_hash": (c_trace.get("output_hash") if c_trace else None),
            }
        )

    if diff_id is None:
        diff_id = (
            f"diff_{baseline_score['candidate_id']}_to_{candidate_score['candidate_id']}"
        )

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_trace_diff",
        "schema_ref": "hop/harness_trace_diff.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary=trace_id,
            related=[
                baseline_score["run_id"],
                candidate_score["run_id"],
            ],
        ),
        "diff_id": diff_id,
        "baseline_candidate_id": baseline_score["candidate_id"],
        "candidate_id": candidate_score["candidate_id"],
        "baseline_run_id": baseline_score["run_id"],
        "candidate_run_id": candidate_score["run_id"],
        "generated_at": datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "score_delta": _score_delta(baseline_score, candidate_score),
        "case_diffs": case_diffs,
        "shared_changes": _detect_shared_changes(case_diffs),
        "isolated_changes": _detect_isolated_changes(case_diffs),
        "conflicting_signals": _detect_conflicting(case_diffs),
    }
    finalize_artifact(payload, id_prefix="hop_trace_diff_")
    validate_hop_artifact(payload, "hop_harness_trace_diff")
    return payload
