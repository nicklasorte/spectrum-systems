#!/usr/bin/env python3
"""CLI for VAL-08 end-to-end failure simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.end_to_end_failure_simulation import (  # noqa: E402
    EndToEndFailureSimulationError,
    run_end_to_end_failure_simulation,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VAL-08 end-to-end failure simulation matrix.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-bundle-ref", type=str)
    parser.add_argument("--replay-result-ref", type=str)
    parser.add_argument("--eval-summary-ref", type=str)
    parser.add_argument("--error-budget-status-ref", type=str)
    parser.add_argument("--monitor-record-ref", type=str)
    parser.add_argument("--control-decision-ref", type=str)
    parser.add_argument("--certification-pack-ref", type=str)
    parser.add_argument("--done-certification-ref", type=str)
    parser.add_argument("--xrun-ref", type=str)
    parser.add_argument("--policy-backtest-ref", type=str)
    parser.add_argument("--fault-profile-ref", type=str)
    return parser.parse_args()


def _input_refs(args: argparse.Namespace) -> Dict[str, Any]:
    refs = {
        "context_bundle_ref": args.context_bundle_ref,
        "replay_result_ref": args.replay_result_ref,
        "eval_summary_ref": args.eval_summary_ref,
        "error_budget_status_ref": args.error_budget_status_ref,
        "monitor_record_ref": args.monitor_record_ref,
        "control_decision_ref": args.control_decision_ref,
        "certification_pack_ref": args.certification_pack_ref,
        "done_certification_ref": args.done_certification_ref,
        "xrun_ref": args.xrun_ref,
        "policy_backtest_ref": args.policy_backtest_ref,
        "fault_profile_ref": args.fault_profile_ref,
    }
    return {k: v for k, v in refs.items() if isinstance(v, str) and v.strip()}


def main() -> int:
    args = _parse_args()
    payload = _input_refs(args)
    result = run_end_to_end_failure_simulation(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EndToEndFailureSimulationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
