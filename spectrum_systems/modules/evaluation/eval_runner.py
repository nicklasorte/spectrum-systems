"""
Evaluation Runner — spectrum_systems/modules/evaluation/eval_runner.py

End-to-end evaluation orchestrator for the meeting-minutes → working-paper
pipeline.  Runs golden test cases through ``multi_pass_reasoning``, compares
outputs to expected results, verifies grounding, and records structured
evaluation results.

Design principles
-----------------
- No silent failures: every error is classified and recorded.
- Deterministic mode: when ``deterministic=True``, the runner enforces
  ``temperature=0``, fixed seeds, and stable prompt versions.
- Latency budgets are tracked and flagged (but not hard-failed by default).
- Schema validation is enforced; schema violations are automatic FAILs.
- No external dependencies beyond the Python standard library.

Public API
----------
EvalResult
    Structured result for a single golden case evaluation run.

EvalRunner
    Orchestrates case execution and result recording.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.evaluation.golden_dataset import GoldenCase, GoldenDataset
from spectrum_systems.modules.evaluation.grounding import GroundingVerifier, DocumentGroundingResult
from spectrum_systems.modules.evaluation.comparison import compare_structural, compare_semantic, ComparisonResult
from spectrum_systems.modules.evaluation.error_taxonomy import EvalError, ErrorType, classify_error
from spectrum_systems.modules.evaluation.regression import RegressionHarness, BaselineRecord


# ---------------------------------------------------------------------------
# Latency budgets (milliseconds)
# ---------------------------------------------------------------------------

DEFAULT_LATENCY_BUDGETS: Dict[str, int] = {
    "extraction": 2000,
    "reasoning": 4000,
    "adversarial": 6000,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LatencySummary:
    """Per-pass and total latency information.

    Attributes
    ----------
    per_pass_latency:
        Mapping of ``pass_type -> latency_ms``.
    total_latency_ms:
        Sum of all per-pass latencies.
    budget_violations:
        Pass types that exceeded their configured latency budget.
    """

    per_pass_latency: Dict[str, int] = field(default_factory=dict)
    total_latency_ms: int = 0
    budget_violations: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Structured result for a single golden case evaluation run.

    Attributes
    ----------
    case_id:
        Golden case identifier.
    pass_fail:
        Overall pass/fail determination.  ``True`` = pass.
    structural_score:
        F1 score from structural comparison (0.0–1.0).
    semantic_score:
        F1 score from semantic comparison (0.0–1.0).
    grounding_score:
        Fraction of claims that are grounded (0.0–1.0).
    latency_summary:
        Per-pass and total latency information.
    error_types:
        List of classified ``EvalError`` instances for all failures.
    pass_chain_record:
        Raw pass chain record returned by the reasoning engine, if available.
    schema_valid:
        Whether all pass outputs passed schema validation.
    regression_detected:
        Whether a score regression beyond threshold was detected.
    evaluated_at:
        ISO-8601 timestamp of this evaluation run.
    """

    case_id: str
    pass_fail: bool
    structural_score: float
    semantic_score: float
    grounding_score: float
    latency_summary: LatencySummary
    error_types: List[EvalError] = field(default_factory=list)
    pass_chain_record: Optional[Dict[str, Any]] = None
    schema_valid: bool = True
    regression_detected: bool = False
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    human_feedback_overrides: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "case_id": self.case_id,
            "pass_fail": self.pass_fail,
            "structural_score": self.structural_score,
            "semantic_score": self.semantic_score,
            "grounding_score": self.grounding_score,
            "latency_summary": {
                "per_pass_latency": self.latency_summary.per_pass_latency,
                "total_latency_ms": self.latency_summary.total_latency_ms,
                "budget_violations": self.latency_summary.budget_violations,
            },
            "error_types": [
                {
                    "error_type": e.error_type.value,
                    "message": e.message,
                    "pass_id": e.pass_id,
                    "details": e.details,
                }
                for e in self.error_types
            ],
            "schema_valid": self.schema_valid,
            "regression_detected": self.regression_detected,
            "evaluated_at": self.evaluated_at,
            "human_feedback_overrides": self.human_feedback_overrides,
        }


# ---------------------------------------------------------------------------
# EvalRunner
# ---------------------------------------------------------------------------

class EvalRunner:
    """Orchestrates evaluation of golden cases against the reasoning pipeline.

    Parameters
    ----------
    reasoning_engine:
        Object that provides ``run(transcript, context) -> dict`` returning a
        pass chain record.  Must be injected; the runner does not import
        ``multi_pass_reasoning`` directly so it remains testable with stubs.
    grounding_verifier:
        ``GroundingVerifier`` instance.  A default instance is created if not
        provided.
    regression_harness:
        ``RegressionHarness`` instance.  If ``None``, regression checking is
        skipped.
    latency_budgets:
        Per-pass-type latency budgets in milliseconds.
    deterministic:
        When ``True``, passes ``temperature=0`` and ``seed=0`` in the engine
        config, and verifies that pass results carry stable prompt versions.
    output_dir:
        Directory where ``eval_results.json`` is written.
    """

    def __init__(
        self,
        reasoning_engine: Any,
        grounding_verifier: Optional[GroundingVerifier] = None,
        regression_harness: Optional[RegressionHarness] = None,
        latency_budgets: Optional[Dict[str, int]] = None,
        deterministic: bool = False,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._engine = reasoning_engine
        self._grounding = grounding_verifier or GroundingVerifier()
        self._regression = regression_harness
        self._latency_budgets = latency_budgets or dict(DEFAULT_LATENCY_BUDGETS)
        self._deterministic = deterministic
        self._output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_case(self, case: GoldenCase) -> EvalResult:
        """Run evaluation for a single golden case.

        Steps
        -----
        1. Build engine config (deterministic flags if enabled).
        2. Invoke the reasoning engine with the transcript.
        3. Capture all pass outputs and latencies.
        4. Validate pass outputs against schemas.
        5. Compare outputs to expected golden outputs.
        6. Run grounding verification on synthesized sections.
        7. Check regression against stored baseline.
        8. Build and return ``EvalResult``.

        Parameters
        ----------
        case:
            Golden test case.

        Returns
        -------
        EvalResult
        """
        errors: List[EvalError] = []
        schema_valid = True

        # -- Step 1: Build engine config ----------------------------------
        engine_config: Dict[str, Any] = {}
        if self._deterministic:
            engine_config["temperature"] = 0
            engine_config["seed"] = 0

        # -- Step 2: Invoke engine ----------------------------------------
        start_ms = _now_ms()
        try:
            pass_chain_record = self._engine.run(
                transcript=case.transcript,
                config=engine_config,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(EvalError(
                error_type=ErrorType.extraction_error,
                message=f"Reasoning engine raised an exception: {exc}",
                details={"exception": str(exc)},
            ))
            return EvalResult(
                case_id=case.case_id,
                pass_fail=False,
                structural_score=0.0,
                semantic_score=0.0,
                grounding_score=0.0,
                latency_summary=LatencySummary(total_latency_ms=_now_ms() - start_ms),
                error_types=errors,
                schema_valid=False,
            )

        total_ms = _now_ms() - start_ms

        # -- Step 3: Collect pass outputs and latencies -------------------
        pass_results: List[Dict[str, Any]] = pass_chain_record.get("pass_results", [])
        per_pass_latency: Dict[str, int] = {}
        budget_violations: List[str] = []

        for pr in pass_results:
            pt = pr.get("pass_type", "unknown")
            lat = pr.get("latency_ms") or 0
            per_pass_latency[pt] = per_pass_latency.get(pt, 0) + lat
            # Check latency budget
            budget_key = _latency_budget_key(pt)
            budget = self._latency_budgets.get(budget_key)
            if budget is not None and lat > budget:
                budget_violations.append(pt)

        latency_summary = LatencySummary(
            per_pass_latency=per_pass_latency,
            total_latency_ms=total_ms,
            budget_violations=budget_violations,
        )

        # -- Step 4: Schema validation ------------------------------------
        for pr in pass_results:
            sv = pr.get("schema_validation", {})
            if sv.get("status") == "failed":
                schema_valid = False
                errors.append(classify_error({
                    "pass_type": pr.get("pass_type", ""),
                    "pass_id": pr.get("pass_id"),
                    "schema_errors": sv.get("errors", []),
                    "message": f"Schema validation failed for pass '{pr.get('pass_type')}'",
                }))

        # -- Step 5: Compare outputs --------------------------------------
        actual_outputs = self._extract_actual_outputs(pass_chain_record)
        expected = case.expected_outputs()

        structural_scores: List[float] = []
        semantic_scores: List[float] = []

        for key in ("decisions", "action_items", "gaps", "contradictions"):
            exp_list = expected.get(key, [])
            act_list = actual_outputs.get(key, [])
            s_result = compare_structural(exp_list, act_list)
            sem_result = compare_semantic(exp_list, act_list)
            structural_scores.append(s_result.f1_score)
            semantic_scores.append(sem_result.f1_score)

            # Tag missing items as extraction errors
            for missing_item in s_result.missing:
                errors.append(classify_error({
                    "pass_type": _output_key_to_pass_type(key),
                    "message": f"Missing {key} item: {_truncate(str(missing_item))}",
                }))

        structural_score = _mean(structural_scores)
        semantic_score = _mean(semantic_scores)

        # -- Step 6: Grounding verification -------------------------------
        intermediate_artifacts = pass_chain_record.get("intermediate_artifacts", {})
        # Also build ref map from pass_results
        for pr in pass_results:
            ref = pr.get("output_ref")
            if ref and pr.get("_raw_output") is not None:
                intermediate_artifacts[ref] = pr["_raw_output"]

        synthesized_doc = actual_outputs.get("working_paper_sections_doc", {})
        grounding_result: DocumentGroundingResult = self._grounding.verify_document(
            synthesized_doc, intermediate_artifacts
        )
        grounding_score = grounding_result.grounding_score

        for cr in grounding_result.claim_results:
            if not cr.grounded:
                errors.append(classify_error({
                    "missing_refs": cr.missing_refs,
                    "mismatched_refs": cr.mismatched_refs,
                    "upstream_pass_refs": cr.missing_refs + cr.mismatched_refs,
                    "message": f"Ungrounded claim: {_truncate(cr.claim_text)}",
                }))

        # -- Step 7: Regression check -------------------------------------
        regression_detected = False
        if self._regression is not None:
            reg = self._regression.compare(
                case_id=case.case_id,
                structural_score=structural_score,
                semantic_score=semantic_score,
                grounding_score=grounding_score,
            )
            regression_detected = reg.regression_detected
            if regression_detected:
                for delta in reg.score_deltas:
                    if delta.is_regression:
                        errors.append(classify_error({
                            "regression": True,
                            "message": (
                                f"Regression in '{delta.dimension}': "
                                f"baseline={delta.baseline:.3f}, "
                                f"current={delta.current:.3f}, "
                                f"drop={-delta.delta:.3f} > threshold={delta.threshold:.3f}"
                            ),
                        }))

        # -- Step 8: Build result -----------------------------------------
        pass_fail = (
            schema_valid
            and not regression_detected
            and structural_score > 0.0
            and grounding_score >= 1.0  # all claims must be grounded
            and not any(
                e.error_type in (ErrorType.hallucination, ErrorType.grounding_failure)
                for e in errors
            )
        )

        return EvalResult(
            case_id=case.case_id,
            pass_fail=pass_fail,
            structural_score=structural_score,
            semantic_score=semantic_score,
            grounding_score=grounding_score,
            latency_summary=latency_summary,
            error_types=errors,
            pass_chain_record=pass_chain_record,
            schema_valid=schema_valid,
            regression_detected=regression_detected,
        )

    def run_all_cases(self, dataset: GoldenDataset) -> List[EvalResult]:
        """Run evaluation for all cases in a dataset.

        Parameters
        ----------
        dataset:
            ``GoldenDataset`` instance.

        Returns
        -------
        list[EvalResult]
            Results in the same order as ``dataset.cases``.
        """
        results: List[EvalResult] = []
        for case in dataset.cases:
            result = self.run_case(case)
            results.append(result)
        return results

    def write_report(self, results: List[EvalResult], output_path: Optional[Path] = None) -> Path:
        """Write a JSON evaluation report.

        Parameters
        ----------
        results:
            List of ``EvalResult`` instances.
        output_path:
            Destination path.  Defaults to ``{output_dir}/eval_results.json``.

        Returns
        -------
        Path
            The path the report was written to.
        """
        if output_path is None:
            if self._output_dir is None:
                raise EvalRunnerError("No output_dir configured and no output_path provided.")
            output_path = self._output_dir / "eval_results.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        total = len(results)
        passed = sum(1 for r in results if r.pass_fail)
        report = {
            "summary": {
                "total_cases": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total if total > 0 else 0.0,
            },
            "results": [r.to_dict() for r in results],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return output_path

    def apply_feedback_overrides(
        self,
        eval_result: "EvalResult",
        feedback_records: List[Dict[str, Any]],
    ) -> "EvalResult":
        """Inject human feedback overrides into an existing evaluation result.

        Feedback is recorded additively alongside the automated evaluation
        result — system outputs are never silently replaced.  The override
        list in ``EvalResult.human_feedback_overrides`` captures where the
        human reviewer disagrees with the system, providing a traceable audit
        trail for downstream learning systems (AU, AV, AW, AZ).

        Parameters
        ----------
        eval_result:
            The ``EvalResult`` produced by ``run_case``.
        feedback_records:
            List of feedback record dicts (from ``HumanFeedbackRecord.to_dict()``).
            Each record must include at least:

            - ``feedback_id`` (str)
            - ``target_id`` (str) — the claim or section reviewed
            - ``action`` (str) — reviewer disposition
            - ``failure_type`` (str) — AU-aligned failure classification
            - ``severity`` (str)
            - ``original_text`` (str)
            - ``edited_text`` (str | None)

        Returns
        -------
        EvalResult
            A new ``EvalResult`` with the ``human_feedback_overrides`` field
            populated.  All other fields are unchanged.

        Notes
        -----
        This method does NOT modify the original ``eval_result`` object.
        """
        from dataclasses import replace as _dc_replace

        overrides: List[Dict[str, Any]] = []
        for fb in feedback_records:
            overrides.append({
                "feedback_id": fb.get("feedback_id"),
                "target_id": fb.get("target_id"),
                "action": fb.get("action"),
                "failure_type": fb.get("failure_type"),
                "severity": fb.get("severity"),
                "original_text": fb.get("original_text"),
                "edited_text": fb.get("edited_text"),
                "human_disagrees_with_system": fb.get("action") not in ("accept",),
            })

        return _dc_replace(eval_result, human_feedback_overrides=overrides)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_actual_outputs(self, pass_chain_record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured outputs from a pass chain record.

        Looks for output in ``intermediate_artifacts`` keyed by artifact refs
        from pass results.
        """
        outputs: Dict[str, Any] = {}
        intermediates: Dict[str, Any] = pass_chain_record.get("intermediate_artifacts", {})
        pass_results: List[Dict[str, Any]] = pass_chain_record.get("pass_results", [])

        for pr in pass_results:
            pt = pr.get("pass_type", "")
            raw = pr.get("_raw_output") or intermediates.get(pr.get("output_ref", ""), {})
            if not isinstance(raw, dict):
                continue

            if pt == "decision_extraction":
                outputs["decisions"] = raw.get("decisions", [])
            elif pt == "transcript_extraction":
                outputs["action_items"] = raw.get("action_items", [])
            elif pt == "gap_detection":
                outputs["gaps"] = raw.get("gaps", [])
            elif pt == "contradiction_detection":
                outputs["contradictions"] = raw.get("contradictions", [])
            elif pt == "synthesis":
                # Build a document structure for grounding verification
                sections = raw.get("sections", [])
                outputs["working_paper_sections"] = sections
                outputs["working_paper_sections_doc"] = raw

        return outputs


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class EvalRunnerError(Exception):
    """Raised for configuration or runtime errors in the eval runner."""


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _truncate(text: str, max_len: int = 120) -> str:
    return text[:max_len] + "…" if len(text) > max_len else text


def _output_key_to_pass_type(key: str) -> str:
    return {
        "decisions": "decision_extraction",
        "action_items": "transcript_extraction",
        "gaps": "gap_detection",
        "contradictions": "contradiction_detection",
    }.get(key, key)


def _latency_budget_key(pass_type: str) -> str:
    """Map a pass type to its latency budget category."""
    if "adversarial" in pass_type:
        return "adversarial"
    if pass_type in ("decision_extraction", "contradiction_detection", "gap_detection"):
        return "reasoning"
    return "extraction"
