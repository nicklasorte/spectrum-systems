"""Replay Regression Harness (SRE-04).

Deterministically compares canonical baseline replay_result artifacts against
current replay_result artifacts and emits a governed regression_result artifact.

Fail-closed boundaries
----------------------
- Missing baseline/current artifact path blocks execution.
- Invalid JSON or schema-invalid replay_result blocks execution.
- Incompatible artifact type blocks execution.
- Broken lineage/trace prerequisites block execution.
- Ambiguous or incomplete required fields block execution.

Mismatches do not block execution; they are artifactized into the run result.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_SUITE_MANIFEST_SCHEMA_PATH = _SCHEMA_DIR / "regression_suite_manifest.schema.json"
_RUN_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "regression_run_result.schema.json"
_REPLAY_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "replay_result.schema.json"

logger = logging.getLogger(__name__)

_COMPARISON_FIELDS = (
    "trace_id",
    "input_artifact_reference",
    "original_decision_reference",
    "original_enforcement_reference",
    "replay_decision",
    "replay_enforcement_action",
    "replay_final_status",
    "original_enforcement_action",
    "original_final_status",
    "consistency_status",
    "drift_detected",
    "provenance.source_artifact_type",
    "provenance.source_artifact_id",
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class RegressionHarnessError(Exception):
    """Raised for any regression harness failure. Fail-closed."""


class InvalidSuiteError(RegressionHarnessError):
    """Raised when a suite manifest fails schema validation."""


class MissingTraceError(RegressionHarnessError):
    """Raised when baseline/current replay traces cannot be resolved."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_schema(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise RegressionHarnessError(f"Schema file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate_against_schema(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _load_json_file(path: Path, label: str) -> Dict[str, Any]:
    if not path.is_file():
        raise MissingTraceError(f"{label} artifact file not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise RegressionHarnessError(f"Failed to load {label} artifact '{path}': {exc}") from exc
    if not isinstance(payload, dict):
        raise RegressionHarnessError(f"{label} artifact must be a JSON object: {path}")
    return payload


def _get_nested(obj: Dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _ensure_replay_result_prereqs(artifact: Dict[str, Any], label: str) -> None:
    replay_schema = _load_schema(_REPLAY_RESULT_SCHEMA_PATH)
    errors = _validate_against_schema(artifact, replay_schema)
    if errors:
        raise RegressionHarnessError(f"{label} replay_result schema validation failed: {errors}")

    if artifact.get("artifact_type") != "replay_result":
        raise RegressionHarnessError(
            f"{label} artifact_type must be 'replay_result', got '{artifact.get('artifact_type')}'"
        )

    trace_id = artifact.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        raise MissingTraceError(f"{label} replay_result missing trace_id")

    provenance = artifact.get("provenance") or {}
    for field in ("source_artifact_type", "source_artifact_id"):
        if not isinstance(provenance.get(field), str) or not provenance.get(field):
            raise RegressionHarnessError(f"{label} malformed provenance.{field}")


def _comparison_digest(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_regression_suite(path: str | Path) -> Dict[str, Any]:
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
    return suite


def validate_regression_suite(suite: Any) -> List[str]:
    schema = _load_schema(_SUITE_MANIFEST_SCHEMA_PATH)
    return _validate_against_schema(suite, schema)


def run_trace_regression(trace_entry: Dict[str, Any]) -> Dict[str, Any]:
    trace_id = trace_entry["trace_id"]
    baseline_path = Path(trace_entry["baseline_replay_result_path"])
    current_path = Path(trace_entry["current_replay_result_path"])

    baseline = _load_json_file(baseline_path, "baseline")
    current = _load_json_file(current_path, "current")

    _ensure_replay_result_prereqs(baseline, "baseline")
    _ensure_replay_result_prereqs(current, "current")

    if baseline.get("trace_id") != trace_id or current.get("trace_id") != trace_id:
        raise MissingTraceError(
            "trace_id mismatch between suite and replay artifacts "
            f"[suite={trace_id}, baseline={baseline.get('trace_id')}, current={current.get('trace_id')}]"
        )

    mismatches: List[Dict[str, Any]] = []
    for field in _COMPARISON_FIELDS:
        b_val = _get_nested(baseline, field)
        c_val = _get_nested(current, field)
        if b_val != c_val:
            mismatches.append({"field": field, "baseline_value": b_val, "current_value": c_val})

    passed = len(mismatches) == 0
    digest_payload = {
        "trace_id": trace_id,
        "baseline_id": baseline.get("replay_id"),
        "current_id": current.get("replay_id"),
        "mismatches": mismatches,
    }

    return {
        "trace_id": trace_id,
        "replay_result_id": current.get("replay_id", ""),
        "baseline_replay_result_id": baseline.get("replay_id", ""),
        "current_replay_result_id": current.get("replay_id", ""),
        "baseline_trace_id": baseline.get("trace_id", ""),
        "current_trace_id": current.get("trace_id", ""),
        "baseline_reference": f"replay_result:{baseline.get('replay_id', '')}",
        "current_reference": f"replay_result:{current.get('replay_id', '')}",
        "analysis_id": _comparison_digest(digest_payload),
        "decision_status": "consistent" if passed else "drifted",
        "reproducibility_score": 1.0 if passed else 0.0,
        "drift_type": "" if passed else "REGRESSION_MISMATCH",
        "passed": passed,
        "failure_reasons": [] if passed else ["deterministic replay comparison mismatch"],
        "mismatch_summary": mismatches,
        "comparison_digest": _comparison_digest(digest_payload),
    }


def evaluate_trace_pass_fail(trace_entry: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    expected_status = trace_entry["expected_decision_status"]
    min_score = float(trace_entry["minimum_reproducibility_score"])

    failure_reasons = list(analysis.get("failure_reasons") or [])

    if analysis.get("decision_status") != expected_status:
        failure_reasons.append(
            f"decision_status '{analysis.get('decision_status')}' does not match expected '{expected_status}'"
        )

    score = float(analysis.get("reproducibility_score", 0.0))
    if score < min_score:
        failure_reasons.append(
            f"reproducibility_score {score:.4f} is below minimum {min_score:.4f}"
        )

    out = dict(analysis)
    out["failure_reasons"] = failure_reasons
    out["passed"] = len(failure_reasons) == 0
    return out


def aggregate_regression_results(
    suite: Dict[str, Any],
    per_trace_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ordered_results = sorted(per_trace_results, key=lambda x: x["trace_id"])
    total = len(ordered_results)
    passed = sum(1 for r in ordered_results if r["passed"])
    failed = total - passed

    summary_payload = {
        "suite_id": suite["suite_id"],
        "results": [
            {
                "trace_id": r["trace_id"],
                "comparison_digest": r["comparison_digest"],
                "passed": r["passed"],
            }
            for r in ordered_results
        ],
    }
    run_id = _comparison_digest(summary_payload)
    created_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    drift_counts: Dict[str, int] = {}
    for r in ordered_results:
        dt = r.get("drift_type") or ""
        if dt:
            drift_counts[dt] = drift_counts.get(dt, 0) + 1

    avg_score = (
        sum(float(r.get("reproducibility_score", 0.0)) for r in ordered_results) / total if total else 0.0
    )

    return {
        "artifact_type": "regression_result",
        "schema_version": "1.1.0",
        "blocked": False,
        "regression_status": "pass" if failed == 0 else "fail",
        "run_id": run_id,
        "suite_id": suite["suite_id"],
        "created_at": created_at,
        "total_traces": total,
        "passed_traces": passed,
        "failed_traces": failed,
        "pass_rate": (passed / total) if total else 0.0,
        "overall_status": "pass" if failed == 0 else "fail",
        "results": ordered_results,
        "summary": {
            "drift_counts": drift_counts,
            "average_reproducibility_score": avg_score,
        },
    }


def validate_regression_run_result(result: Any) -> List[str]:
    schema = _load_schema(_RUN_RESULT_SCHEMA_PATH)
    return _validate_against_schema(result, schema)


def run_regression_suite(path: str | Path) -> Dict[str, Any]:
    suite = load_regression_suite(path)

    per_trace_results: List[Dict[str, Any]] = []
    for trace_entry in suite["traces"]:
        analysis = run_trace_regression(trace_entry)
        per_trace_results.append(evaluate_trace_pass_fail(trace_entry, analysis))

    run_result = aggregate_regression_results(suite, per_trace_results)
    errors = validate_regression_run_result(run_result)
    if errors:
        raise RegressionHarnessError(
            f"run_regression_suite: run result failed schema validation: {errors}"
        )

    return run_result
