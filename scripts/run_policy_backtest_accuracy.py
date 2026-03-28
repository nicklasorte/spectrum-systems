#!/usr/bin/env python3
"""Thin CLI for VAL-05 policy backtest accuracy validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.policy_backtest_accuracy import (  # noqa: E402
    PolicyBacktestAccuracyError,
    run_policy_backtest_accuracy,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyBacktestAccuracyError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyBacktestAccuracyError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_object(path: Path, *, label: str) -> Dict[str, Any]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, dict):
        raise PolicyBacktestAccuracyError(f"{label} must be a JSON object: {path}")
    return payload


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise PolicyBacktestAccuracyError(f"{label} must be a JSON array: {path}")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise PolicyBacktestAccuracyError(f"{label}[{idx}] must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-05 policy backtest accuracy validation matrix.")
    parser.add_argument("--replay-results", type=Path, required=True)
    parser.add_argument("--eval-summaries", type=Path, required=True)
    parser.add_argument("--error-budget-statuses", type=Path, required=True)
    parser.add_argument("--cross-run-intelligence-decisions", type=Path, required=True)
    parser.add_argument("--baseline-policy-ref", type=Path, required=True)
    parser.add_argument(
        "--candidate-policy-refs",
        type=Path,
        required=False,
        help="Optional candidate policy refs array. Validation matrix remains deterministic by case type.",
    )
    parser.add_argument(
        "--expected-outcomes-ref",
        type=Path,
        required=False,
        help="Optional expected outcomes override object.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "replay_results": _load_array(args.replay_results, label="replay_results"),
        "eval_summaries": _load_array(args.eval_summaries, label="eval_summaries"),
        "error_budget_statuses": _load_array(args.error_budget_statuses, label="error_budget_statuses"),
        "cross_run_intelligence_decisions": _load_array(
            args.cross_run_intelligence_decisions,
            label="cross_run_intelligence_decisions",
        ),
        "baseline_policy_ref": _load_object(args.baseline_policy_ref, label="baseline_policy_ref"),
    }

    if args.candidate_policy_refs is not None:
        payload["candidate_policy_refs"] = _load_array(args.candidate_policy_refs, label="candidate_policy_refs")
    if args.expected_outcomes_ref is not None:
        payload["expected_outcomes_ref"] = _load_object(args.expected_outcomes_ref, label="expected_outcomes_ref")

    result = run_policy_backtest_accuracy(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))

    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PolicyBacktestAccuracyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
