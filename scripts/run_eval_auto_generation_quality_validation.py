#!/usr/bin/env python3
"""CLI for VAL-07 eval auto-generation quality validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.eval_auto_generation_quality import (  # noqa: E402
    EvalAutoGenerationQualityError,
    run_eval_auto_generation_quality_validation,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvalAutoGenerationQualityError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvalAutoGenerationQualityError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise EvalAutoGenerationQualityError(f"{label} must be a JSON array")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise EvalAutoGenerationQualityError(f"{label}[{idx}] must be a JSON object")
    return payload


def _load_policy(path: Path) -> Dict[str, Any]:
    payload = _load_json(path, label="policy_ref")
    if not isinstance(payload, dict):
        raise EvalAutoGenerationQualityError("policy_ref must be a JSON object")
    return payload


def _load_optional_json(path: Path | None, *, label: str) -> Any:
    if path is None:
        return None
    return _load_json(path, label=label)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-07 eval auto-generation quality validation.")
    parser.add_argument("--replay-results", type=Path, required=True)
    parser.add_argument("--eval-summaries", type=Path, required=True)
    parser.add_argument("--regression-results", type=Path, required=True)
    parser.add_argument("--drift-results", type=Path, required=True)
    parser.add_argument("--monitor-records", type=Path, required=True)
    parser.add_argument("--policy-ref", type=Path, required=True)
    parser.add_argument("--cross-run-intelligence-decisions", type=Path)
    parser.add_argument("--failure-injection-results", type=Path)
    parser.add_argument("--expected-outcomes-ref", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "replay_results": _load_array(args.replay_results, label="replay_results"),
        "eval_summaries": _load_array(args.eval_summaries, label="eval_summaries"),
        "regression_results": _load_array(args.regression_results, label="regression_results"),
        "drift_results": _load_array(args.drift_results, label="drift_results"),
        "monitor_records": _load_array(args.monitor_records, label="monitor_records"),
        "policy_ref": _load_policy(args.policy_ref),
    }

    cross_run_decisions = _load_optional_json(args.cross_run_intelligence_decisions, label="cross_run_intelligence_decisions")
    if cross_run_decisions is not None:
        if isinstance(cross_run_decisions, dict):
            payload["cross_run_intelligence_decisions"] = [cross_run_decisions]
        elif isinstance(cross_run_decisions, list):
            payload["cross_run_intelligence_decisions"] = cross_run_decisions
        else:
            raise EvalAutoGenerationQualityError("cross_run_intelligence_decisions must be a JSON object or array")

    failure_injection_results = _load_optional_json(args.failure_injection_results, label="failure_injection_results")
    if failure_injection_results is not None:
        if isinstance(failure_injection_results, dict):
            payload["failure_injection_results"] = [failure_injection_results]
        elif isinstance(failure_injection_results, list):
            payload["failure_injection_results"] = failure_injection_results
        else:
            raise EvalAutoGenerationQualityError("failure_injection_results must be a JSON object or array")

    expected_outcomes = _load_optional_json(args.expected_outcomes_ref, label="expected_outcomes_ref")
    if expected_outcomes is not None:
        if not isinstance(expected_outcomes, dict):
            raise EvalAutoGenerationQualityError("expected_outcomes_ref must be a JSON object")
        payload["expected_outcomes_ref"] = expected_outcomes
        payload["expected_outcomes_ref_path"] = str(args.expected_outcomes_ref)

    result = run_eval_auto_generation_quality_validation(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvalAutoGenerationQualityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
