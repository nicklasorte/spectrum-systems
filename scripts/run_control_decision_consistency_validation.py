#!/usr/bin/env python3
"""CLI for VAL-04 control decision consistency validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.control_decision_consistency import (  # noqa: E402
    ControlDecisionConsistencyError,
    run_control_decision_consistency_validation,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlDecisionConsistencyError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ControlDecisionConsistencyError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise ControlDecisionConsistencyError(f"{label} must be a JSON array")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ControlDecisionConsistencyError(f"{label}[{idx}] must be a JSON object")
    return payload


def _load_policy(path: Path) -> Dict[str, Any] | str:
    payload = _load_json(path, label="policy_ref")
    if isinstance(payload, str):
        if not payload.strip():
            raise ControlDecisionConsistencyError("policy_ref string must be non-empty")
        return payload
    if not isinstance(payload, dict):
        raise ControlDecisionConsistencyError("policy_ref must be a JSON object or string")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-04 control decision consistency validation.")
    parser.add_argument("--eval-summaries", type=Path, required=True)
    parser.add_argument("--error-budget-statuses", type=Path, required=True)
    parser.add_argument("--monitor-records", type=Path, required=True)
    parser.add_argument("--cross-run-intelligence-decisions", type=Path, required=True)
    parser.add_argument("--policy-ref", type=Path, required=True)
    parser.add_argument("--repeat-count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "eval_summaries": _load_array(args.eval_summaries, label="eval_summaries"),
        "error_budget_statuses": _load_array(args.error_budget_statuses, label="error_budget_statuses"),
        "monitor_records": _load_array(args.monitor_records, label="monitor_records"),
        "cross_run_intelligence_decisions": _load_array(
            args.cross_run_intelligence_decisions,
            label="cross_run_intelligence_decisions",
        ),
        "policy_ref": _load_policy(args.policy_ref),
        "repeat_count": args.repeat_count,
    }

    result = run_control_decision_consistency_validation(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ControlDecisionConsistencyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
