"""RPL+EVL: historical_replay_validator — backtest against known failing PR patterns (CLX-ALL-01 Phase 4).

Replays a corpus of known failing PR cases and validates that:
  - Expected failure classification matches actual classification.
  - primary_reason is stable (same across replays).
  - Results are deterministic (no non-deterministic outcomes).

Fails if: any mismatch, missing classification, or non-deterministic result.

This module is bounded to replay and comparison. It does not modify state,
apply repairs, or emit control decisions. Outputs feed EVL for coverage
tracking.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

# Known historical failure case corpus (schema-bound, no free-text).
# Each case: case_id, failure_class, expected_classification, replay_input.
_BUILTIN_CORPUS: list[dict[str, Any]] = [
    {
        "case_id": "hist-authority-shape-001",
        "failure_class": "authority_shape_violation",
        "expected_classification": "authority_shape_violation",
        "description": "HOP file uses promotion_decision outside the declared owner path",
        "replay_input": {
            "violation_type": "vocabulary_violation",
            "cluster": "promotion",
            "symbol": "harness_promotion_decision",
        },
    },
    {
        "case_id": "hist-registry-guard-001",
        "failure_class": "registry_guard_failure",
        "expected_classification": "registry_guard_failure",
        "description": "New system acronym not declared in system_registry.md",
        "replay_input": {
            "violation_type": "registry_guard",
            "symbol": "UNK",
        },
    },
    {
        "case_id": "hist-manifest-drift-001",
        "failure_class": "manifest_drift",
        "expected_classification": "manifest_drift",
        "description": "standards-manifest vocabulary drifted from authority_shape_vocabulary.json",
        "replay_input": {
            "violation_type": "manifest_drift",
            "drift_count": 3,
        },
    },
    {
        "case_id": "hist-shadow-overlap-001",
        "failure_class": "shadow_ownership_overlap",
        "expected_classification": "authority_shape_violation",
        "description": "Non-owner file emits closure_decision_artifact",
        "replay_input": {
            "violation_type": "shadow_ownership_overlap",
            "symbol": "closure_decision_artifact",
            "declared_owner": "HOP",
            "actual_owner": "CDE",
        },
    },
]


class HistoricalReplayValidatorError(ValueError):
    """Raised when replay validation cannot complete deterministically."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _report_id(trace_id: str) -> str:
    digest = hashlib.sha256(f"hrv-{trace_id}-{_now()}".encode()).hexdigest()[:12]
    return f"hrv-{digest}"


def _classify_replay_input(replay_input: dict[str, Any]) -> str | None:
    """Derive classification from a replay input dict.

    Returns a classification string or None if input is insufficient.
    Deterministic: same input always produces same output.
    """
    vtype = str(replay_input.get("violation_type") or "").strip()
    if not vtype:
        return None

    if vtype in ("vocabulary_violation", "shadow_ownership_overlap", "forbidden_symbol"):
        return "authority_shape_violation"
    if vtype == "registry_guard":
        return "registry_guard_failure"
    if vtype == "manifest_drift":
        return "manifest_drift"
    return None


def _replay_case(
    case: dict[str, Any],
    classifier: Callable[[dict[str, Any]], str | None] | None = None,
) -> dict[str, Any]:
    """Replay a single historical case and return a result record."""
    if not isinstance(case, dict):
        return {
            "case_id": "unknown",
            "failure_class": "",
            "expected_classification": "",
            "actual_classification": None,
            "primary_reason_stable": False,
            "result": "invalid_corpus_entry",
            "detail": f"corpus entry must be a dict, got {type(case).__name__}",
        }
    case_id = str(case.get("case_id") or "")
    failure_class = str(case.get("failure_class") or "")
    expected = str(case.get("expected_classification") or "")
    replay_input = case.get("replay_input") or {}

    if not case_id or not expected:
        return {
            "case_id": case_id or "unknown",
            "failure_class": failure_class,
            "expected_classification": expected,
            "actual_classification": None,
            "primary_reason_stable": False,
            "result": "missing_classification",
            "detail": "case_id or expected_classification missing from corpus entry",
        }

    # Use provided classifier or built-in.
    classify = classifier if classifier is not None else _classify_replay_input
    actual = classify(replay_input)

    if actual is None:
        return {
            "case_id": case_id,
            "failure_class": failure_class,
            "expected_classification": expected,
            "actual_classification": None,
            "primary_reason_stable": False,
            "result": "missing_classification",
            "detail": "classifier returned None — insufficient replay input",
        }

    # primary_reason_stable: replaying the same input twice must produce the same result.
    actual2 = classify(replay_input)
    primary_reason_stable = actual == actual2

    if not primary_reason_stable:
        return {
            "case_id": case_id,
            "failure_class": failure_class,
            "expected_classification": expected,
            "actual_classification": actual,
            "primary_reason_stable": False,
            "result": "non_deterministic",
            "detail": f"Classifier produced different results: '{actual}' vs '{actual2}'",
        }

    if actual != expected:
        return {
            "case_id": case_id,
            "failure_class": failure_class,
            "expected_classification": expected,
            "actual_classification": actual,
            "primary_reason_stable": True,
            "result": "mismatch",
            "detail": f"Expected '{expected}', got '{actual}'",
        }

    return {
        "case_id": case_id,
        "failure_class": failure_class,
        "expected_classification": expected,
        "actual_classification": actual,
        "primary_reason_stable": True,
        "result": "pass",
        "detail": "Classification matches expected",
    }


def run_historical_replay_validation(
    *,
    trace_id: str,
    run_id: str = "",
    additional_cases: list[dict[str, Any]] | None = None,
    classifier: Callable[[dict[str, Any]], str | None] | None = None,
) -> dict[str, Any]:
    """Run full historical replay validation.

    Replays all builtin corpus cases plus any ``additional_cases``. Returns
    a ``replay_validation_report``. Status is ``'fail'`` if any case
    produces mismatch, missing_classification, or non_deterministic result.

    Raises ``HistoricalReplayValidatorError`` on invalid inputs.
    """
    if not isinstance(trace_id, str) or not trace_id:
        raise HistoricalReplayValidatorError("trace_id must be a non-empty string")

    corpus = list(_BUILTIN_CORPUS)
    if additional_cases is not None:
        if not isinstance(additional_cases, list):
            raise HistoricalReplayValidatorError("additional_cases must be a list")
        corpus.extend(additional_cases)

    results: list[dict[str, Any]] = []
    for case in corpus:
        results.append(_replay_case(case, classifier=classifier))

    total = len(results)
    passed = sum(1 for r in results if r["result"] == "pass")
    failed = sum(1 for r in results if r["result"] != "pass")
    mismatches = sum(1 for r in results if r["result"] == "mismatch")

    overall = "pass" if failed == 0 else "fail"
    failure_reason: str | None = None
    if overall == "fail":
        non_pass = [r for r in results if r["result"] != "pass"]
        first = non_pass[0]
        failure_reason = f"{first['result']}: case {first['case_id']} — {first['detail']}"

    return {
        "artifact_type": "replay_validation_report",
        "schema_version": "1.0.0",
        "report_id": _report_id(trace_id),
        "trace_id": trace_id,
        "run_id": run_id,
        "replayed_cases": results,
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": failed,
        "mismatch_cases": mismatches,
        "overall_status": overall,
        "failure_reason": failure_reason,
        "emitted_at": _now(),
    }


__all__ = [
    "HistoricalReplayValidatorError",
    "run_historical_replay_validation",
]
