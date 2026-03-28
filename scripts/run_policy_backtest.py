#!/usr/bin/env python3
"""Run deterministic policy backtesting from governed artifact inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.policy_backtesting import (  # noqa: E402
    PolicyBacktestingError,
    run_policy_backtest,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyBacktestingError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyBacktestingError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_object(path: Path, *, label: str) -> Dict[str, Any]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, dict):
        raise PolicyBacktestingError(f"{label} must be a JSON object: {path}")
    return payload


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise PolicyBacktestingError(f"{label} must be a JSON array: {path}")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise PolicyBacktestingError(f"{label}[{idx}] must be a JSON object")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic policy backtesting.")
    parser.add_argument("--replay-results", required=True, help="Path to replay_results JSON array.")
    parser.add_argument("--eval-summaries", required=True, help="Path to eval_summaries JSON array.")
    parser.add_argument("--error-budget-statuses", required=True, help="Path to error_budget_statuses JSON array.")
    parser.add_argument(
        "--cross-run-intelligence-decisions",
        required=True,
        help="Path to cross_run_intelligence_decisions JSON array.",
    )
    parser.add_argument("--baseline-policy-ref", required=True, help="Path to baseline policy ref JSON object.")
    parser.add_argument("--candidate-policy-ref", required=True, help="Path to candidate policy ref JSON object.")
    parser.add_argument("--output", required=True, help="Output path for policy_backtest_result JSON artifact.")
    args = parser.parse_args(argv)

    payload = {
        "replay_results": _load_array(Path(args.replay_results), label="replay_results"),
        "eval_summaries": _load_array(Path(args.eval_summaries), label="eval_summaries"),
        "error_budget_statuses": _load_array(Path(args.error_budget_statuses), label="error_budget_statuses"),
        "cross_run_intelligence_decisions": _load_array(
            Path(args.cross_run_intelligence_decisions),
            label="cross_run_intelligence_decisions",
        ),
        "baseline_policy_ref": _load_object(Path(args.baseline_policy_ref), label="baseline_policy_ref"),
        "candidate_policy_ref": _load_object(Path(args.candidate_policy_ref), label="candidate_policy_ref"),
    }

    result = run_policy_backtest(payload)
    validate_artifact(result, "policy_backtest_result")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PolicyBacktestingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
