"""
Regression Harness — spectrum_systems/modules/regression/harness.py

Governed regression harness that prevents silent degradation when prompts,
model adapters, scoring logic, or pass-chain behaviour change.

Design principles
-----------------
- Regression checks are deterministic when deterministic mode is enabled.
- No silent regressions.
- Hard gates for critical dimensions, softer warnings for secondary dimensions.
- Pass-level attribution is used wherever feasible.
- Baselines are governed artifacts with explicit metadata.
- Reports explain WHAT regressed, WHERE, and BY HOW MUCH.
- No external dependencies beyond the Python standard library.

Public API
----------
RegressionPolicy
    Loaded policy configuration.

RegressionReport
    In-memory regression report.

RegressionHarness
    Orchestrates comparison, gate evaluation, and report generation.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.regression.gates import evaluate_policy_gates
from spectrum_systems.modules.regression.attribution import (
    attribute_regressions_to_passes,
    compute_pass_regression_summary,
    identify_worst_passes,
)
from spectrum_systems.modules.regression.recommendations import generate_recommendations


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_POLICY_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "regression_policy.schema.json"
)

_REPORT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "regression_report.schema.json"
)

_DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "regression_policy.json"
)


# ---------------------------------------------------------------------------
# RegressionPolicy
# ---------------------------------------------------------------------------


class RegressionPolicy:
    """Loaded, validated regression policy.

    Parameters
    ----------
    data:
        Raw policy dict (already loaded from JSON).
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    # --- Required fields as properties ----------------------------------

    @property
    def policy_id(self) -> str:
        return self._data["policy_id"]

    @property
    def version(self) -> str:
        return self._data["version"]

    @property
    def description(self) -> str:
        return self._data["description"]

    @property
    def thresholds(self) -> Dict[str, Any]:
        return self._data["thresholds"]

    @property
    def hard_fail_dimensions(self) -> Dict[str, bool]:
        return self._data["hard_fail_dimensions"]

    @property
    def minimum_sample_sizes(self) -> Dict[str, int]:
        return self._data["minimum_sample_sizes"]

    @property
    def scope(self) -> Dict[str, Any]:
        return self._data["scope"]

    @property
    def deterministic_required(self) -> bool:
        return bool(self._data.get("deterministic_required", False))

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "RegressionPolicy":
        """Load a policy from a JSON file.

        Parameters
        ----------
        path:
            Path to the policy JSON.  Defaults to
            ``config/regression_policy.json``.
        """
        policy_path = path or _DEFAULT_POLICY_PATH
        try:
            data = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RegressionPolicyError(
                f"Policy file not found: {policy_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RegressionPolicyError(
                f"Invalid JSON in policy file {policy_path}: {exc}"
            ) from exc
        return cls(data)


# ---------------------------------------------------------------------------
# RegressionReport
# ---------------------------------------------------------------------------


class RegressionReport:
    """In-memory regression report.

    Attributes
    ----------
    data:
        Raw dict conforming to regression_report.schema.json.
    overall_pass:
        True if there are no hard failures.
    hard_failures:
        Number of hard-fail dimensions.
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    @property
    def overall_pass(self) -> bool:
        return bool(self._data["summary"]["overall_pass"])

    @property
    def hard_failures(self) -> int:
        return int(self._data["summary"]["hard_failures"])

    @property
    def warnings(self) -> int:
        return int(self._data["summary"]["warnings"])

    @property
    def report_id(self) -> str:
        return self._data["report_id"]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def write(self, path: Path) -> None:
        """Write the report as JSON to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    def validate_against_schema(self) -> List[str]:
        """Validate this report against the governed schema.

        Returns
        -------
        list of str
            Validation error strings.  Empty list = valid.
        """
        return _validate_json_schema(self._data, _REPORT_SCHEMA_PATH)


# ---------------------------------------------------------------------------
# RegressionHarness
# ---------------------------------------------------------------------------


class RegressionHarness:
    """Orchestrates regression comparison, gate evaluation, and report generation.

    Parameters
    ----------
    policy:
        ``RegressionPolicy`` instance.  If ``None``, the default policy is
        loaded from ``config/regression_policy.json``.
    """

    def __init__(self, policy: Optional[RegressionPolicy] = None) -> None:
        self._policy = policy or RegressionPolicy.load()

    @property
    def policy(self) -> RegressionPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare_eval_runs(
        self,
        baseline_eval_results: List[Dict[str, Any]],
        candidate_eval_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compare two sets of eval result dicts aggregate-level and per-case.

        Parameters
        ----------
        baseline_eval_results:
            List of stable EvalResult dicts from the baseline run.
        candidate_eval_results:
            List of stable EvalResult dicts from the candidate run.

        Returns
        -------
        dict
            Keys: aggregates (per-dimension baseline/candidate averages),
            per_case (case-level deltas), cases_compared (int).
        """
        min_cases = self._policy.minimum_sample_sizes["cases"]
        if len(baseline_eval_results) < min_cases or len(candidate_eval_results) < min_cases:
            return {
                "aggregates": _zero_aggregates(insufficient_data=True),
                "per_case": [],
                "cases_compared": min(len(baseline_eval_results), len(candidate_eval_results)),
                "insufficient_data": True,
            }

        base_by_case = {r["case_id"]: r for r in baseline_eval_results}
        matched_cases = [r for r in candidate_eval_results if r["case_id"] in base_by_case]

        agg = _compute_aggregates(
            [base_by_case[r["case_id"]] for r in matched_cases],
            matched_cases,
        )
        per_case = _compute_per_case(
            [base_by_case[r["case_id"]] for r in matched_cases],
            matched_cases,
        )

        return {
            "aggregates": agg,
            "per_case": per_case,
            "cases_compared": len(matched_cases),
            "insufficient_data": len(matched_cases) < min_cases,
        }

    def compare_observability_runs(
        self,
        baseline_records: List[Dict[str, Any]],
        candidate_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compare two sets of observability record dicts.

        Returns aggregate latency and human-disagreement comparisons plus
        pass-level attribution.

        Parameters
        ----------
        baseline_records:
            List of stable ObservabilityRecord dicts from the baseline run.
        candidate_records:
            List of stable ObservabilityRecord dicts from the candidate run.

        Returns
        -------
        dict
            Keys: latency_ms (baseline/candidate), human_disagreement_rate,
            pass_attribution, passes_compared (int).
        """
        min_records = self._policy.minimum_sample_sizes["per_pass_records"]

        if not baseline_records or not candidate_records:
            return {
                "latency_ms": {"baseline": 0.0, "candidate": 0.0, "insufficient_data": True},
                "human_disagreement_rate": {"baseline": 0.0, "candidate": 0.0, "insufficient_data": True},
                "pass_attribution": {},
                "passes_compared": 0,
                "insufficient_data": True,
            }

        base_lat = _mean([r.get("latency_ms", 0) for r in baseline_records])
        cand_lat = _mean([r.get("latency_ms", 0) for r in candidate_records])

        base_hd = _mean([1.0 if r.get("human_disagrees") else 0.0 for r in baseline_records])
        cand_hd = _mean([1.0 if r.get("human_disagrees") else 0.0 for r in candidate_records])

        # Pass-level attribution
        attribution = attribute_regressions_to_passes(
            baseline_records,
            candidate_records,
        )

        passes_compared = min(len(baseline_records), len(candidate_records))
        lat_insufficient = passes_compared < min_records
        hd_insufficient = passes_compared < min_records

        return {
            "latency_ms": {
                "baseline": base_lat,
                "candidate": cand_lat,
                "insufficient_data": lat_insufficient,
            },
            "human_disagreement_rate": {
                "baseline": base_hd,
                "candidate": cand_hd,
                "insufficient_data": hd_insufficient,
            },
            "pass_attribution": attribution,
            "passes_compared": passes_compared,
            "insufficient_data": lat_insufficient,
        }

    def merge_comparison_results(
        self,
        eval_comparison: Dict[str, Any],
        observability_comparison: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge eval and observability comparison results into a unified comparison dict.

        This is the dict consumed by ``evaluate_policy_gates``.
        """
        agg = eval_comparison.get("aggregates", {})
        insufficient_eval = eval_comparison.get("insufficient_data", False)

        merged: Dict[str, Any] = {
            "structural_score": {
                "baseline": agg.get("baseline_structural_score", 0.0),
                "candidate": agg.get("candidate_structural_score", 0.0),
                "insufficient_data": insufficient_eval or agg.get("insufficient_data", False),
            },
            "semantic_score": {
                "baseline": agg.get("baseline_semantic_score", 0.0),
                "candidate": agg.get("candidate_semantic_score", 0.0),
                "insufficient_data": insufficient_eval or agg.get("insufficient_data", False),
            },
            "grounding_score": {
                "baseline": agg.get("baseline_grounding_score", 0.0),
                "candidate": agg.get("candidate_grounding_score", 0.0),
                "insufficient_data": insufficient_eval or agg.get("insufficient_data", False),
            },
            "latency_ms": observability_comparison.get("latency_ms", {
                "baseline": 0.0, "candidate": 0.0, "insufficient_data": True,
            }),
            "human_disagreement_rate": observability_comparison.get("human_disagreement_rate", {
                "baseline": 0.0, "candidate": 0.0, "insufficient_data": True,
            }),
        }
        return merged

    def generate_report(
        self,
        *,
        baseline_id: str,
        candidate_id: str,
        eval_comparison: Optional[Dict[str, Any]] = None,
        observability_comparison: Optional[Dict[str, Any]] = None,
        candidate_deterministic: Optional[bool] = None,
    ) -> RegressionReport:
        """Generate a full governed regression report.

        Parameters
        ----------
        baseline_id:
            Name/ID of the baseline.
        candidate_id:
            Name/ID of the candidate run.
        eval_comparison:
            Output of ``compare_eval_runs``.  If None, a zero comparison
            with ``insufficient_data=True`` is used.
        observability_comparison:
            Output of ``compare_observability_runs``.  If None, zero is used.
        candidate_deterministic:
            Whether the candidate run was deterministic.  Used to check
            ``deterministic_required`` policy gate.

        Returns
        -------
        RegressionReport
        """
        if eval_comparison is None:
            eval_comparison = {
                "aggregates": _zero_aggregates(insufficient_data=True),
                "per_case": [],
                "cases_compared": 0,
                "insufficient_data": True,
            }
        if observability_comparison is None:
            observability_comparison = {
                "latency_ms": {"baseline": 0.0, "candidate": 0.0, "insufficient_data": True},
                "human_disagreement_rate": {"baseline": 0.0, "candidate": 0.0, "insufficient_data": True},
                "pass_attribution": {},
                "passes_compared": 0,
                "insufficient_data": True,
            }

        merged = self.merge_comparison_results(eval_comparison, observability_comparison)

        # Determinism gate
        determinism_fail = False
        if self._policy.deterministic_required and candidate_deterministic is False:
            determinism_fail = True

        gate_results = evaluate_policy_gates(merged, self._policy)
        gate_results["determinism_fail"] = determinism_fail

        if determinism_fail:
            gate_results["hard_failures"] += 1
            gate_results["overall_pass"] = False

        # Build dimension_results for report schema
        dim_res = gate_results["dimension_results"]
        dimension_results = {
            "structural_score": _format_dim_result(dim_res.get("structural_score", {})),
            "semantic_score": _format_dim_result(dim_res.get("semantic_score", {})),
            "grounding_score": _format_dim_result(dim_res.get("grounding_score", {})),
            "latency": _format_dim_result(dim_res.get("latency", {})),
            "human_disagreement": _format_dim_result(dim_res.get("human_disagreement", {})),
        }

        # Build worst regressions
        worst_regressions = _build_worst_regressions(
            eval_comparison,
            observability_comparison,
            gate_results,
        )

        # Build report dict
        report_dict: Dict[str, Any] = {
            "report_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "baseline_id": baseline_id,
            "candidate_id": candidate_id,
            "policy_id": self._policy.policy_id,
            "summary": {
                "overall_pass": gate_results["overall_pass"],
                "hard_failures": gate_results["hard_failures"],
                "warnings": gate_results["warnings"],
                "cases_compared": eval_comparison.get("cases_compared", 0),
                "passes_compared": observability_comparison.get("passes_compared", 0),
            },
            "dimension_results": dimension_results,
            "worst_regressions": worst_regressions,
            "recommendations": [],
        }

        # Generate recommendations
        report_dict["recommendations"] = generate_recommendations(report_dict)

        return RegressionReport(report_dict)

    def validate_report_against_schema(self, report: RegressionReport) -> List[str]:
        """Convenience wrapper: validate report against governed schema."""
        return report.validate_against_schema()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def eval_result_to_dict(eval_result: Any) -> Dict[str, Any]:
    """Convert an EvalResult (or existing dict) to a stable dict.

    Stable means:
    - Keys are always in the same order (sort_keys applied on serialisation).
    - The dict is JSON-serialisable without extra transformation.

    Parameters
    ----------
    eval_result:
        An ``EvalResult`` dataclass instance or an already-serialised dict.
    """
    if isinstance(eval_result, dict):
        return eval_result
    # EvalResult dataclass
    return eval_result.to_dict()


def observability_record_to_dict(record: Any) -> Dict[str, Any]:
    """Convert an ObservabilityRecord (or existing dict) to a stable flat dict.

    Handles both:
    - ``ObservabilityRecord`` instances (converts via attributes).
    - Already-serialised nested schema dicts (normalised to flat format).
    - Already-flat dicts (returned as-is).

    The returned flat dict uses direct top-level keys for all fields,
    which is the format expected by regression attribution and comparison
    logic.

    Parameters
    ----------
    record:
        An ``ObservabilityRecord`` instance or an already-serialised dict.
    """
    if isinstance(record, dict):
        # If already flat (has pass_type at top level), return as-is
        if "pass_type" in record and "context" not in record:
            return record
        # Nested schema dict — normalise to flat
        return _flatten_obs_record_dict(record)
    # ObservabilityRecord instance — read from attributes directly
    return {
        "record_id": getattr(record, "record_id", ""),
        "timestamp": getattr(record, "timestamp", ""),
        "artifact_id": getattr(record, "artifact_id", ""),
        "artifact_type": getattr(record, "artifact_type", ""),
        "pipeline_stage": getattr(record, "pipeline_stage", ""),
        "pass_id": getattr(record, "pass_id", ""),
        "pass_type": getattr(record, "pass_type", ""),
        "structural_score": getattr(record, "structural_score", 0.0),
        "semantic_score": getattr(record, "semantic_score", 0.0),
        "grounding_score": getattr(record, "grounding_score", 0.0),
        "latency_ms": getattr(record, "latency_ms", 0),
        "schema_valid": getattr(record, "schema_valid", True),
        "grounding_passed": getattr(record, "grounding_passed", True),
        "regression_passed": getattr(record, "regression_passed", True),
        "human_disagrees": getattr(record, "human_disagrees", False),
        "error_types": getattr(record, "error_types", []),
        "failure_count": getattr(record, "failure_count", 0),
        "case_id": getattr(record, "case_id", None),
        "tokens_used": getattr(record, "tokens_used", None),
    }


def _flatten_obs_record_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise an ``ObservabilityRecord.to_dict()`` nested dict to a flat dict."""
    ctx = data.get("context", {})
    pi = data.get("pass_info", {})
    metrics = data.get("metrics", {})
    flags = data.get("flags", {})
    es = data.get("error_summary", {})
    return {
        "record_id": data.get("record_id", ""),
        "timestamp": data.get("timestamp", ""),
        "artifact_id": ctx.get("artifact_id", ""),
        "artifact_type": ctx.get("artifact_type", ""),
        "pipeline_stage": ctx.get("pipeline_stage", ""),
        "case_id": ctx.get("case_id"),
        "pass_id": pi.get("pass_id", ""),
        "pass_type": pi.get("pass_type", ""),
        "structural_score": metrics.get("structural_score", 0.0),
        "semantic_score": metrics.get("semantic_score", 0.0),
        "grounding_score": metrics.get("grounding_score", 0.0),
        "latency_ms": metrics.get("latency_ms", 0),
        "tokens_used": metrics.get("tokens_used"),
        "schema_valid": flags.get("schema_valid", True),
        "grounding_passed": flags.get("grounding_passed", True),
        "regression_passed": flags.get("regression_passed", True),
        "human_disagrees": flags.get("human_disagrees", False),
        "error_types": es.get("error_types", []),
        "failure_count": es.get("failure_count", 0),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _zero_aggregates(*, insufficient_data: bool = False) -> Dict[str, Any]:
    return {
        "baseline_structural_score": 0.0,
        "candidate_structural_score": 0.0,
        "baseline_semantic_score": 0.0,
        "candidate_semantic_score": 0.0,
        "baseline_grounding_score": 0.0,
        "candidate_grounding_score": 0.0,
        "insufficient_data": insufficient_data,
    }


def _compute_aggregates(
    baseline_list: List[Dict[str, Any]],
    candidate_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "baseline_structural_score": _mean([r.get("structural_score", 0.0) for r in baseline_list]),
        "candidate_structural_score": _mean([r.get("structural_score", 0.0) for r in candidate_list]),
        "baseline_semantic_score": _mean([r.get("semantic_score", 0.0) for r in baseline_list]),
        "candidate_semantic_score": _mean([r.get("semantic_score", 0.0) for r in candidate_list]),
        "baseline_grounding_score": _mean([r.get("grounding_score", 0.0) for r in baseline_list]),
        "candidate_grounding_score": _mean([r.get("grounding_score", 0.0) for r in candidate_list]),
        "insufficient_data": False,
    }


def _compute_per_case(
    baseline_list: List[Dict[str, Any]],
    candidate_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    per_case = []
    for base, cand in zip(baseline_list, candidate_list):
        case_id = base.get("case_id", "")
        per_case.append({
            "case_id": case_id,
            "structural_score_delta": cand.get("structural_score", 0.0) - base.get("structural_score", 0.0),
            "semantic_score_delta": cand.get("semantic_score", 0.0) - base.get("semantic_score", 0.0),
            "grounding_score_delta": cand.get("grounding_score", 0.0) - base.get("grounding_score", 0.0),
            "baseline_structural_score": base.get("structural_score", 0.0),
            "candidate_structural_score": cand.get("structural_score", 0.0),
            "baseline_semantic_score": base.get("semantic_score", 0.0),
            "candidate_semantic_score": cand.get("semantic_score", 0.0),
            "baseline_grounding_score": base.get("grounding_score", 0.0),
            "candidate_grounding_score": cand.get("grounding_score", 0.0),
        })
    return per_case


def _format_dim_result(dim: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure dimension result has all required schema fields."""
    return {
        "baseline_value": float(dim.get("baseline_value", 0.0)),
        "candidate_value": float(dim.get("candidate_value", 0.0)),
        "delta": float(dim.get("delta", 0.0)),
        "threshold": float(dim.get("threshold", 0.0)),
        "passed": bool(dim.get("passed", True)),
        "severity": dim.get("severity", "info"),
        "insufficient_data": bool(dim.get("insufficient_data", False)),
    }


def _build_worst_regressions(
    eval_comparison: Dict[str, Any],
    observability_comparison: Dict[str, Any],
    gate_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build worst_regressions list from per-case and pass-attribution data."""
    entries: List[Dict[str, Any]] = []

    # Per-case regressions (score dimensions)
    per_case = eval_comparison.get("per_case", [])
    dim_results = gate_results.get("dimension_results", {})

    for case in per_case:
        for dim_key, delta_key in [
            ("structural_score", "structural_score_delta"),
            ("semantic_score", "semantic_score_delta"),
            ("grounding_score", "grounding_score_delta"),
        ]:
            delta = case.get(delta_key, 0.0)
            if delta < 0:
                severity = dim_results.get(dim_key, {}).get("severity", "info")
                entries.append({
                    "case_id": case.get("case_id"),
                    "dimension": dim_key,
                    "baseline_value": case.get(f"baseline_{dim_key}", 0.0),
                    "candidate_value": case.get(f"candidate_{dim_key}", 0.0),
                    "delta": delta,
                    "severity": severity,
                    "explanation": (
                        f"{dim_key} dropped by {abs(delta):.4f} for case '{case.get('case_id')}'"
                    ),
                })

    # Pass-level attributions
    pass_attr = observability_comparison.get("pass_attribution", {})
    pass_entries = pass_attr.get("pass_attributions", {})
    for pass_type, attr_list in pass_entries.items():
        for entry in attr_list:
            delta = entry.get("delta", 0.0)
            if delta < 0:
                dim = entry.get("dimension", "")
                severity = dim_results.get(dim, {}).get("severity", "info") if dim in dim_results else "info"
                entries.append({
                    "case_id": entry.get("case_id"),
                    "pass_type": pass_type,
                    "dimension": dim,
                    "baseline_value": entry.get("baseline_value", 0.0),
                    "candidate_value": entry.get("candidate_value", 0.0),
                    "delta": delta,
                    "severity": severity,
                    "explanation": (
                        f"{pass_type} {dim} dropped by {abs(delta):.4f}"
                        + (f" for case '{entry.get('case_id')}'" if entry.get("case_id") else "")
                    ),
                })

    # Sort worst-first by absolute delta (most negative first)
    entries.sort(key=lambda x: x["delta"])
    return entries[:20]  # cap at 20 worst entries


def _validate_json_schema(data: Dict[str, Any], schema_path: Path) -> List[str]:
    """Validate *data* against a JSON Schema file.

    Returns a list of error strings.  Empty = valid.
    Uses ``jsonschema`` if available; returns a notice otherwise.
    """
    try:
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        return [f"{list(e.path)}: {e.message}" for e in errors]
    except ImportError:
        return ["jsonschema not installed; schema validation skipped"]
    except FileNotFoundError:
        return [f"Schema file not found: {schema_path}"]
    except Exception as exc:
        return [f"Schema validation error: {exc}"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RegressionPolicyError(Exception):
    """Raised when a regression policy cannot be loaded or is invalid."""
