"""HOP evaluator.

Runs a validated candidate against an eval set and emits:

- one ``hop_harness_trace`` per case (always — even on failure);
- one ``hop_harness_score`` summarizing the run;
- one ``hop_harness_run`` envelope tying everything together;
- ``hop_harness_failure_hypothesis`` artifacts for any per-case anomaly.

The evaluator NEVER:

- modifies the candidate payload;
- proposes new candidates;
- mutates eval cases;
- emits a free-form recommendation.

Pass criteria are enum-bound (``structural``, ``expected_qa_pairs``,
``rejection_expected``). Any case that yields a malformed FAQ output produces
an explicit ``malformed_artifact`` failure hypothesis and is counted as a
failed case for that run.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import (
    canonical_json,
    finalize_artifact,
    make_trace,
)
from spectrum_systems.modules.hop.experience_store import ExperienceStore, HopStoreError
from spectrum_systems.modules.hop.sandbox import execute_candidate
from spectrum_systems.modules.hop.schemas import (
    HopSchemaError,
    validate_hop_artifact,
)


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash_obj(obj: Any) -> str:
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class EvalSet:
    """An immutable, versioned eval set."""

    eval_set_id: str
    eval_set_version: str
    cases: tuple[Mapping[str, Any], ...]

    @property
    def case_count(self) -> int:
        return len(self.cases)

    def case_ids(self) -> list[str]:
        return [c["eval_case_id"] for c in self.cases]


@dataclass
class CaseResult:
    eval_case_id: str
    passed: bool
    score: float
    latency_ms: float
    failure_reason: str | None
    trace_payload: dict[str, Any]
    failure_payloads: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# pass-criteria judges
# ---------------------------------------------------------------------------

def _judge_structural(faq: Mapping[str, Any], rules: Mapping[str, Any]) -> tuple[bool, str | None]:
    items = faq.get("items", [])
    min_qa = rules.get("min_qa_pairs")
    max_qa = rules.get("max_qa_pairs")
    if isinstance(min_qa, int) and len(items) < min_qa:
        return False, f"items_below_min:{len(items)}<{min_qa}"
    if isinstance(max_qa, int) and len(items) > max_qa:
        return False, f"items_above_max:{len(items)}>{max_qa}"
    forbidden = rules.get("forbidden_substrings_in_answers", []) or []
    for item in items:
        ans = item.get("answer", "")
        for s in forbidden:
            if s in ans:
                return False, f"forbidden_substring:{s}"
    return True, None


def _judge_expected_qa(faq: Mapping[str, Any], rules: Mapping[str, Any]) -> tuple[bool, str | None]:
    ok, reason = _judge_structural(faq, rules)
    if not ok:
        return ok, reason

    items = faq.get("items", [])
    expected_questions = rules.get("expected_questions_substrings", []) or []
    for q_sub in expected_questions:
        if not any(q_sub in item.get("question", "") for item in items):
            return False, f"missing_expected_question:{q_sub}"

    expected_pairs = rules.get("expected_answer_substrings_per_question", []) or []
    for pair in expected_pairs:
        q_sub = pair["question_substring"]
        a_sub = pair["answer_substring"]
        match = next(
            (item for item in items if q_sub in item.get("question", "")),
            None,
        )
        if match is None:
            return False, f"missing_expected_question:{q_sub}"
        if a_sub not in match.get("answer", ""):
            return False, f"missing_expected_answer:{q_sub}->{a_sub}"
    return True, None


def _judge_rejection(faq: Mapping[str, Any], rules: Mapping[str, Any]) -> tuple[bool, str | None]:
    expect_rejection = bool(rules.get("expect_rejection", False))
    items = faq.get("items", [])
    if expect_rejection and items:
        return False, f"unexpected_items_under_rejection_expected:{len(items)}"
    if not expect_rejection and not items:
        return False, "expected_items_but_got_zero"
    return True, None


_JUDGES: dict[str, Callable[[Mapping[str, Any], Mapping[str, Any]], tuple[bool, str | None]]] = {
    "structural": _judge_structural,
    "expected_qa_pairs": _judge_expected_qa,
    "rejection_expected": _judge_rejection,
}


# ---------------------------------------------------------------------------
# evaluator core
# ---------------------------------------------------------------------------

def _build_failure(
    *,
    candidate_id: str,
    run_id: str,
    failure_class: str,
    eval_case_id: str | None,
    detail: str,
    trace_id: str,
    severity: str = "reject",
) -> dict[str, Any]:
    evidence = [{"kind": "snippet", "detail": detail}]
    if eval_case_id:
        evidence.append({"kind": "eval_case_id", "detail": eval_case_id})
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "hypothesis_id": f"e_{failure_class}_{run_id}_{eval_case_id or 'run'}",
        "candidate_id": candidate_id,
        "run_id": run_id,
        "stage": "evaluation",
        "failure_class": failure_class,
        "severity": severity,
        "evidence": evidence,
        "detected_at": _utcnow(),
        "blocks_promotion": severity == "reject",
    }
    finalize_artifact(payload, id_prefix="hop_failure_")
    return payload


def _execute_one_case(
    *,
    candidate_payload: Mapping[str, Any],
    case: Mapping[str, Any],
    candidate_id: str,
    run_id: str,
    trace_id: str,
) -> CaseResult:
    eval_case_id = case["eval_case_id"]
    started_at = _utcnow()
    started_perf = time.perf_counter()
    steps: list[dict[str, Any]] = []
    failure_payloads: list[dict[str, Any]] = []
    trace_complete = True
    incomplete_reason: str | None = None
    output_hash: str | None = None
    failure_reason: str | None = None
    passed = False
    score = 0.0

    try:
        steps.append(
            {
                "step_id": "step_load_input",
                "op": "load_input",
                "started_at": started_at,
                "completed_at": _utcnow(),
                "input_hash": _hash_obj(case["input"]),
                "output_hash": None,
                "note": None,
            }
        )

        transform_started = _utcnow()
        try:
            sandbox_result = execute_candidate(
                candidate_payload=candidate_payload,
                harness_input=case["input"],
            )
            if not sandbox_result.ok:
                raise RuntimeError(f"{sandbox_result.violation_type}:{sandbox_result.detail}")
            faq = sandbox_result.output
        except Exception as exc:  # candidate raised
            detail = f"{type(exc).__name__}:{exc}"
            failure_class = "sandbox_violation" if "sandbox_violation" in detail else "runtime_error"
            transform_completed = _utcnow()
            steps.append(
                {
                    "step_id": "step_transform",
                    "op": "transform",
                    "started_at": transform_started,
                    "completed_at": transform_completed,
                    "input_hash": _hash_obj(case["input"]),
                    "output_hash": None,
                    "note": f"{failure_class}:{detail}",
                }
            )
            failure_payloads.append(
                _build_failure(
                    candidate_id=candidate_id,
                    run_id=run_id,
                    failure_class=failure_class,
                    eval_case_id=eval_case_id,
                    detail=detail,
                    trace_id=trace_id,
                )
            )
            failure_reason = failure_class
            trace_complete = False
            incomplete_reason = failure_class
        else:
            transform_completed = _utcnow()
            output_hash = _hash_obj(faq)
            steps.append(
                {
                    "step_id": "step_transform",
                    "op": "transform",
                    "started_at": transform_started,
                    "completed_at": transform_completed,
                    "input_hash": _hash_obj(case["input"]),
                    "output_hash": output_hash,
                    "note": None,
                }
            )

            validate_started = _utcnow()
            try:
                validate_hop_artifact(faq, "hop_harness_faq_output")
            except HopSchemaError as exc:
                validate_completed = _utcnow()
                steps.append(
                    {
                        "step_id": "step_validate_output",
                        "op": "validate_output",
                        "started_at": validate_started,
                        "completed_at": validate_completed,
                        "input_hash": output_hash,
                        "output_hash": None,
                        "note": f"schema_violation:{exc}",
                    }
                )
                failure_payloads.append(
                    _build_failure(
                        candidate_id=candidate_id,
                        run_id=run_id,
                        failure_class="malformed_artifact",
                        eval_case_id=eval_case_id,
                        detail=str(exc),
                        trace_id=trace_id,
                    )
                )
                failure_reason = "malformed_artifact"
            else:
                validate_completed = _utcnow()
                steps.append(
                    {
                        "step_id": "step_validate_output",
                        "op": "validate_output",
                        "started_at": validate_started,
                        "completed_at": validate_completed,
                        "input_hash": output_hash,
                        "output_hash": output_hash,
                        "note": None,
                    }
                )

                judge_name = case["pass_criteria"]["judge"]
                judge = _JUDGES.get(judge_name)
                if judge is None:
                    failure_payloads.append(
                        _build_failure(
                            candidate_id=candidate_id,
                            run_id=run_id,
                            failure_class="unknown_eval_case",
                            eval_case_id=eval_case_id,
                            detail=f"unknown_judge:{judge_name}",
                            trace_id=trace_id,
                        )
                    )
                    failure_reason = "unknown_judge"
                else:
                    rules = case["pass_criteria"].get("rules", {}) or {}
                    passed, reason = judge(faq, rules)
                    if passed:
                        score = 1.0
                    else:
                        failure_reason = reason
    finally:
        completed_at = _utcnow()
        elapsed_ms = (time.perf_counter() - started_perf) * 1000

    if failure_payloads:
        trace_complete = False
        if incomplete_reason is None:
            incomplete_reason = failure_payloads[0]["failure_class"]

    trace_payload: dict[str, Any] = {
        "artifact_type": "hop_harness_trace",
        "schema_ref": "hop/harness_trace.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id, related=[run_id, eval_case_id]),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_case_id": eval_case_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "complete": trace_complete,
        "input_hash": _hash_obj(case["input"]),
        "output_hash": output_hash,
        "steps": steps,
        "incomplete_reason": incomplete_reason,
    }
    finalize_artifact(trace_payload, id_prefix="hop_trace_")

    return CaseResult(
        eval_case_id=eval_case_id,
        passed=passed,
        score=score,
        latency_ms=elapsed_ms,
        failure_reason=failure_reason,
        trace_payload=trace_payload,
        failure_payloads=failure_payloads,
    )


def evaluate_candidate(
    *,
    candidate_payload: Mapping[str, Any],
    eval_set: EvalSet,
    store: ExperienceStore | None = None,
    trace_id: str = "hop_evaluator",
    cost_estimator: Callable[[Mapping[str, Any]], float] | None = None,
) -> dict[str, Any]:
    """Run ``candidate`` against ``eval_set``.

    If ``store`` is provided the run / score / trace / failure artifacts are
    persisted via the store. The function returns a dict with the produced
    artifacts so callers can act without re-reading them from disk.
    """
    if not isinstance(candidate_payload, dict):
        raise TypeError("hop_evaluator_invalid_candidate:not_dict")
    validate_hop_artifact(candidate_payload, "hop_harness_candidate")
    if not isinstance(eval_set, EvalSet):
        raise TypeError("hop_evaluator_invalid_eval_set")
    if eval_set.case_count == 0:
        raise ValueError("hop_evaluator_empty_eval_set")
    for case in eval_set.cases:
        validate_hop_artifact(case, "hop_harness_eval_case")

    candidate_id = candidate_payload["candidate_id"]
    run_id = "run_" + candidate_id + "_" + datetime.now(tz=timezone.utc).strftime("%Y%m%dt%H%M%S%f")

    started_at = _utcnow()
    started_perf = time.perf_counter()
    case_results: list[CaseResult] = []
    for case in eval_set.cases:
        case_results.append(
            _execute_one_case(
                candidate_payload=candidate_payload,
                case=case,
                candidate_id=candidate_id,
                run_id=run_id,
                trace_id=trace_id,
            )
        )
    completed_at = _utcnow()
    total_latency_ms = (time.perf_counter() - started_perf) * 1000

    pass_count = sum(1 for r in case_results if r.passed)
    fail_count = sum(1 for r in case_results if not r.passed)
    score = pass_count / eval_set.case_count if eval_set.case_count else 0.0
    trace_complete_count = sum(1 for r in case_results if r.trace_payload.get("complete"))
    trace_completeness = trace_complete_count / eval_set.case_count if eval_set.case_count else 0.0
    eval_coverage = len(case_results) / eval_set.case_count if eval_set.case_count else 0.0

    if cost_estimator is not None:
        cost = float(cost_estimator(candidate_payload))
    else:
        cost = float(len(candidate_payload.get("code_source", "").encode("utf-8")))

    trace_artifact_ids = [r.trace_payload["artifact_id"] for r in case_results]

    score_payload: dict[str, Any] = {
        "artifact_type": "hop_harness_score",
        "schema_ref": "hop/harness_score.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id, related=[run_id]),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_set_id": eval_set.eval_set_id,
        "eval_set_version": eval_set.eval_set_version,
        "score": score,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "case_count": eval_set.case_count,
        "aggregate_method": "pass_rate",
        "breakdown": [
            {
                "eval_case_id": r.eval_case_id,
                "passed": r.passed,
                "score": r.score,
                "latency_ms": r.latency_ms,
                "failure_reason": r.failure_reason,
            }
            for r in case_results
        ],
        "cost": cost,
        "latency_ms": total_latency_ms,
        "trace_completeness": trace_completeness,
        "eval_coverage": eval_coverage,
        "created_at": _utcnow(),
    }
    finalize_artifact(score_payload, id_prefix="hop_score_")

    run_payload: dict[str, Any] = {
        "artifact_type": "hop_harness_run",
        "schema_ref": "hop/harness_run.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id, related=[run_id]),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_set_id": eval_set.eval_set_id,
        "eval_set_version": eval_set.eval_set_version,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": "completed",
        "case_count": eval_set.case_count,
        "trace_artifact_ids": trace_artifact_ids,
        "score_artifact_id": score_payload["artifact_id"],
        "failure_reason": None,
        "rejection_reason": None,
    }
    finalize_artifact(run_payload, id_prefix="hop_run_")

    failure_payloads: list[dict[str, Any]] = []
    for r in case_results:
        failure_payloads.extend(r.failure_payloads)

    if store is not None:
        for r in case_results:
            store.write_artifact(r.trace_payload)
        store.write_artifact(score_payload)
        store.write_artifact(run_payload)
        for fp in failure_payloads:
            try:
                store.write_artifact(fp)
            except HopStoreError:
                # Idempotent retry-protection: duplicates are ignored, but
                # any other error must surface.
                raise

    return {
        "run": run_payload,
        "score": score_payload,
        "traces": [r.trace_payload for r in case_results],
        "failures": failure_payloads,
    }


def load_eval_set_from_files(
    *,
    eval_set_id: str,
    eval_set_version: str,
    case_paths: Iterable[str],
) -> EvalSet:
    """Load and validate eval cases from disk into an immutable EvalSet."""
    cases: list[Mapping[str, Any]] = []
    for path in case_paths:
        payload = json.loads(open(path, encoding="utf-8").read())
        validate_hop_artifact(payload, "hop_harness_eval_case")
        _verify_eval_case_content_hash(payload, source=str(path))
        cases.append(payload)
    if not cases:
        raise ValueError("hop_evaluator_empty_eval_set")
    return EvalSet(
        eval_set_id=eval_set_id,
        eval_set_version=eval_set_version,
        cases=tuple(cases),
    )


def _verify_eval_case_content_hash(payload: Mapping[str, Any], *, source: str) -> None:
    from spectrum_systems.modules.hop.artifacts import compute_content_hash

    expected = payload.get("content_hash")
    recomputed = compute_content_hash(payload)
    if expected != recomputed:
        raise ValueError(
            f"hop_evaluator_tampered_case:{source}:expected={expected}:recomputed={recomputed}"
        )


def load_eval_set_from_manifest(manifest_path: str) -> EvalSet:
    """Load and verify an eval set against its manifest.

    Verification:
    - each case file validates against ``hop_harness_eval_case``;
    - each case's recorded ``content_hash`` matches the recomputed hash;
    - each case's recorded hash matches the manifest entry.

    Any mismatch fails closed with ``ValueError``.
    """
    from pathlib import Path

    manifest_path_obj = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path_obj.read_text(encoding="utf-8"))
    eval_set_id = manifest.get("eval_set_id")
    eval_set_version = manifest.get("eval_set_version")
    case_entries = manifest.get("cases") or []
    if not isinstance(eval_set_id, str) or not eval_set_id:
        raise ValueError("hop_evaluator_invalid_manifest:eval_set_id")
    if not isinstance(eval_set_version, str) or not eval_set_version:
        raise ValueError("hop_evaluator_invalid_manifest:eval_set_version")
    if not case_entries:
        raise ValueError("hop_evaluator_empty_eval_set")

    base_dir = manifest_path_obj.parent
    cases: list[Mapping[str, Any]] = []
    for entry in case_entries:
        rel_path = entry.get("path")
        manifest_hash = entry.get("content_hash")
        if not isinstance(rel_path, str) or not isinstance(manifest_hash, str):
            raise ValueError(
                f"hop_evaluator_invalid_manifest_entry:{json.dumps(entry, sort_keys=True)}"
            )
        case_path = (base_dir / rel_path).resolve()
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        validate_hop_artifact(payload, "hop_harness_eval_case")
        _verify_eval_case_content_hash(payload, source=str(case_path))
        if payload.get("content_hash") != manifest_hash:
            raise ValueError(
                "hop_evaluator_tampered_manifest:"
                f"{rel_path}:manifest={manifest_hash}:case={payload.get('content_hash')}"
            )
        cases.append(payload)

    return EvalSet(
        eval_set_id=eval_set_id,
        eval_set_version=eval_set_version,
        cases=tuple(cases),
    )
