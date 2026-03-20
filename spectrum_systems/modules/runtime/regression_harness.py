"""Replay Regression Harness (Prompt BR).

Converts persisted traces and replay decision analyses into a governed
regression harness that can be run in batch, used in CI, and used to detect
decision drift over time.

Design principles
-----------------
- Fail closed:  missing trace, missing analysis, invalid fixture, or schema
  validation failure all raise errors — no silent degradation.
- Schema-governed:  every suite manifest and run result is validated against
  the corresponding JSON Schema before use or return.
- Trace propagation:  ``trace_id`` is included in all log messages.
- Deterministic evaluation:  the same suite manifest always produces the same
  pass/fail verdict for a given set of replay analyses.

Data-flow
---------
    regression_suite_manifest (JSON file)
                │  load_regression_suite(path)
                ▼
    suite dict (schema-validated)
                │
    for each trace_entry in suite["traces"]:
                │  run_trace_regression(trace_entry)
                │      └─ run_replay_decision_analysis(trace_id)
                ▼
    per-trace analysis artifact
                │  evaluate_trace_pass_fail(trace_entry, analysis)
                ▼
    per-trace result dict
                │
    aggregate_regression_results(suite, per_trace_results)
                ▼
    regression_run_result (schema-validated artifact)

Public API
----------
load_regression_suite(path)                        → suite dict
validate_regression_suite(suite)                   → list[str]  (empty = valid)
run_trace_regression(trace_entry, ...)             → analysis dict
evaluate_trace_pass_fail(trace_entry, analysis)    → per-trace result dict
aggregate_regression_results(suite, results)       → run result dict
validate_regression_run_result(result)             → list[str]  (empty = valid)
run_regression_suite(path, ...)                    → regression_run_result dict
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.modules.runtime.replay_decision_engine import (
    ReplayDecisionError,
    run_replay_decision_analysis,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_SUITE_MANIFEST_SCHEMA_PATH = _SCHEMA_DIR / "regression_suite_manifest.schema.json"
_RUN_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "regression_run_result.schema.json"

# Consistency status values (mirror replay_decision_engine constants)
STATUS_CONSISTENT = "consistent"
STATUS_DRIFTED = "drifted"
STATUS_INDETERMINATE = "indeterminate"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class RegressionHarnessError(Exception):
    """Raised for any regression harness failure.  Fail-closed."""


class InvalidSuiteError(RegressionHarnessError):
    """Raised when a suite manifest fails schema validation."""


class MissingTraceError(RegressionHarnessError):
    """Raised when a trace required by the suite cannot be found or replayed."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_schema(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise RegressionHarnessError(f"Schema file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate_against_schema(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_regression_suite(path: str | Path) -> Dict[str, Any]:
    """Load and schema-validate a regression suite manifest from *path*.

    Parameters
    ----------
    path:
        Path to a ``regression_suite_manifest.schema.json``-conformant JSON
        file.

    Returns
    -------
    dict
        The validated suite manifest.

    Raises
    ------
    InvalidSuiteError
        If the file cannot be read or fails schema validation.
    """
    suite_path = Path(path)
    if not suite_path.is_file():
        raise InvalidSuiteError(f"Suite manifest file not found: {suite_path}")

    try:
        with suite_path.open(encoding="utf-8") as fh:
            suite = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidSuiteError(f"Failed to load suite manifest '{suite_path}': {exc}") from exc

    errors = validate_regression_suite(suite)
    if errors:
        raise InvalidSuiteError(
            f"Suite manifest '{suite_path}' failed schema validation: {errors}"
        )

    logger.info(
        "load_regression_suite: loaded suite_id=%s suite_name=%s traces=%d",
        suite.get("suite_id"),
        suite.get("suite_name"),
        len(suite.get("traces", [])),
    )
    return suite


def validate_regression_suite(suite: Any) -> List[str]:
    """Validate *suite* against the regression_suite_manifest JSON Schema.

    Parameters
    ----------
    suite:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the suite is valid.
    """
    schema = _load_schema(_SUITE_MANIFEST_SCHEMA_PATH)
    return _validate_against_schema(suite, schema)


def run_trace_regression(
    trace_entry: Dict[str, Any],
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute replay decision analysis for a single trace entry.

    Parameters
    ----------
    trace_entry:
        A single item from ``suite["traces"]``.
    base_dir:
        Override the trace store directory (primarily for testing).

    Returns
    -------
    dict
        A fully validated ``replay_decision_analysis`` artifact.

    Raises
    ------
    MissingTraceError
        If the trace cannot be found or replayed.
    RegressionHarnessError
        For any other analysis failure.
    """
    trace_id: str = trace_entry["trace_id"]
    logger.info("run_trace_regression: starting trace_id=%s", trace_id)

    try:
        analysis = run_replay_decision_analysis(trace_id, base_dir=base_dir)
    except ReplayDecisionError as exc:
        raise MissingTraceError(
            f"run_trace_regression: analysis failed for trace_id='{trace_id}': {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise RegressionHarnessError(
            f"run_trace_regression: unexpected failure ({type(exc).__name__}) "
            f"for trace_id='{trace_id}': {exc}"
        ) from exc

    logger.info(
        "run_trace_regression: analysis complete trace_id=%s analysis_id=%s "
        "decision_status=%s reproducibility_score=%.3f",
        trace_id,
        analysis.get("analysis_id"),
        analysis.get("decision_consistency", {}).get("status"),
        analysis.get("reproducibility_score", 0.0),
    )
    return analysis


def evaluate_trace_pass_fail(
    trace_entry: Dict[str, Any],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Determine whether a single trace passes or fails the regression criteria.

    A trace passes if and only if:
    1. The decision consistency status matches ``expected_decision_status``.
    2. The reproducibility score is >= ``minimum_reproducibility_score``.

    Parameters
    ----------
    trace_entry:
        A single item from ``suite["traces"]``.
    analysis:
        A ``replay_decision_analysis`` artifact returned by
        :func:`run_trace_regression`.

    Returns
    -------
    dict
        Per-trace result with keys: ``trace_id``, ``replay_result_id``,
        ``analysis_id``, ``decision_status``, ``reproducibility_score``,
        ``drift_type``, ``passed``, ``failure_reasons``.
    """
    trace_id: str = trace_entry["trace_id"]
    expected_status: str = trace_entry["expected_decision_status"]
    min_score: float = trace_entry["minimum_reproducibility_score"]

    consistency = analysis.get("decision_consistency", {})
    actual_status: str = consistency.get("status", STATUS_INDETERMINATE)
    score: float = float(analysis.get("reproducibility_score", 0.0))
    raw_drift_type = analysis.get("drift_type")
    drift_type: str = raw_drift_type if raw_drift_type is not None else ""

    failure_reasons: List[str] = []

    if actual_status != expected_status:
        failure_reasons.append(
            f"decision_status '{actual_status}' does not match expected '{expected_status}'"
        )

    if score < min_score:
        failure_reasons.append(
            f"reproducibility_score {score:.4f} is below minimum {min_score:.4f}"
        )

    passed = len(failure_reasons) == 0

    logger.info(
        "evaluate_trace_pass_fail: trace_id=%s analysis_id=%s drift_type=%s "
        "reproducibility_score=%.3f passed=%s",
        trace_id,
        analysis.get("analysis_id"),
        drift_type or "none",
        score,
        passed,
    )

    return {
        "trace_id": trace_id,
        "replay_result_id": analysis.get("replay_result_id", ""),
        "analysis_id": analysis.get("analysis_id", ""),
        "decision_status": actual_status,
        "reproducibility_score": score,
        "drift_type": drift_type,
        "passed": passed,
        "failure_reasons": failure_reasons,
    }


def aggregate_regression_results(
    suite: Dict[str, Any],
    per_trace_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate per-trace results into a regression run result artifact.

    Parameters
    ----------
    suite:
        The validated suite manifest dict.
    per_trace_results:
        List of per-trace result dicts from :func:`evaluate_trace_pass_fail`.

    Returns
    -------
    dict
        A ``regression_run_result`` artifact (not yet schema-validated).
    """
    total = len(per_trace_results)
    passed = sum(1 for r in per_trace_results if r["passed"])
    failed = total - passed
    pass_rate = passed / total if total > 0 else 0.0
    overall_status = "pass" if failed == 0 else "fail"

    # Compute drift counts
    drift_counts: Dict[str, int] = {}
    for r in per_trace_results:
        dt = r.get("drift_type") or ""
        if dt:
            drift_counts[dt] = drift_counts.get(dt, 0) + 1

    # Compute average reproducibility score
    if total > 0:
        avg_score = sum(r["reproducibility_score"] for r in per_trace_results) / total
    else:
        avg_score = 0.0

    run_result = {
        "run_id": _new_id(),
        "suite_id": suite["suite_id"],
        "created_at": _now_iso(),
        "total_traces": total,
        "passed_traces": passed,
        "failed_traces": failed,
        "pass_rate": pass_rate,
        "overall_status": overall_status,
        "results": per_trace_results,
        "summary": {
            "drift_counts": drift_counts,
            "average_reproducibility_score": avg_score,
        },
    }

    logger.info(
        "aggregate_regression_results: suite_id=%s run_id=%s total=%d passed=%d "
        "failed=%d pass_rate=%.3f overall_status=%s drift_counts=%s "
        "average_reproducibility_score=%.3f",
        suite["suite_id"],
        run_result["run_id"],
        total,
        passed,
        failed,
        pass_rate,
        overall_status,
        drift_counts,
        avg_score,
    )

    return run_result


def validate_regression_run_result(result: Any) -> List[str]:
    """Validate *result* against the regression_run_result JSON Schema.

    Parameters
    ----------
    result:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the result is valid.
    """
    schema = _load_schema(_RUN_RESULT_SCHEMA_PATH)
    return _validate_against_schema(result, schema)


def run_regression_suite(
    path: str | Path,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute a complete regression suite and return the schema-validated result.

    This is the primary entry point for the regression harness.

    Parameters
    ----------
    path:
        Path to the regression suite manifest JSON file.
    base_dir:
        Override the trace store directory (primarily for testing).

    Returns
    -------
    dict
        A fully validated ``regression_run_result`` artifact.

    Raises
    ------
    InvalidSuiteError
        If the suite manifest is invalid.
    MissingTraceError
        If a required trace cannot be found or replayed.
    RegressionHarnessError
        For any other harness failure.
    """
    suite = load_regression_suite(path)
    suite_id = suite["suite_id"]
    traces = suite["traces"]

    logger.info(
        "run_regression_suite: starting suite_id=%s traces=%d",
        suite_id,
        len(traces),
    )

    per_trace_results: List[Dict[str, Any]] = []
    for trace_entry in traces:
        trace_id = trace_entry["trace_id"]
        try:
            analysis = run_trace_regression(trace_entry, base_dir=base_dir)
        except MissingTraceError:
            raise
        except RegressionHarnessError:
            raise

        result = evaluate_trace_pass_fail(trace_entry, analysis)
        per_trace_results.append(result)

    run_result = aggregate_regression_results(suite, per_trace_results)

    errors = validate_regression_run_result(run_result)
    if errors:
        raise RegressionHarnessError(
            f"run_regression_suite: run result failed schema validation: {errors}"
        )

    logger.info(
        "run_regression_suite: complete suite_id=%s overall_status=%s",
        suite_id,
        run_result["overall_status"],
    )

    return run_result
