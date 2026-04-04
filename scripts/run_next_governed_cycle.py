#!/usr/bin/env python3
"""Run exactly one governed next cycle when next_cycle_decision allows it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.next_governed_cycle_runner import (
    NextGovernedCycleRunnerError,
    run_next_governed_cycle,
)


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one governed next cycle from decision+bundle handoff artifacts.")
    parser.add_argument("--next-cycle-decision", type=Path, required=True)
    parser.add_argument("--next-cycle-input-bundle", type=Path, required=True)
    parser.add_argument("--roadmap-artifact", type=Path, required=True)
    parser.add_argument("--selection-signals", type=Path, required=True)
    parser.add_argument("--authorization-signals", type=Path, required=True)
    parser.add_argument("--integration-inputs", type=Path, required=True)
    parser.add_argument("--pqx-state-path", type=Path, required=True)
    parser.add_argument("--pqx-runs-root", type=Path, required=True)
    parser.add_argument("--output-cycle-runner-result", type=Path, required=True)
    parser.add_argument("--output-executed-cycle-dir", type=Path)
    parser.add_argument("--execution-policy", type=Path)
    parser.add_argument("--created-at")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = run_next_governed_cycle(
            next_cycle_decision=_load_json(args.next_cycle_decision),
            next_cycle_input_bundle=_load_json(args.next_cycle_input_bundle),
            roadmap_artifact=_load_json(args.roadmap_artifact),
            selection_signals=_load_json(args.selection_signals),
            authorization_signals=_load_json(args.authorization_signals),
            integration_inputs=_load_json(args.integration_inputs),
            pqx_state_path=args.pqx_state_path,
            pqx_runs_root=args.pqx_runs_root,
            execution_policy=_load_json(args.execution_policy) if args.execution_policy else None,
            created_at=args.created_at,
        )
    except (OSError, ValueError, json.JSONDecodeError, NextGovernedCycleRunnerError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2

    args.output_cycle_runner_result.parent.mkdir(parents=True, exist_ok=True)
    args.output_cycle_runner_result.write_text(json.dumps(result["cycle_runner_result"], indent=2) + "\n", encoding="utf-8")

    executed_cycle = result.get("executed_cycle")
    if executed_cycle and args.output_executed_cycle_dir:
        args.output_executed_cycle_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths = {
            "roadmap_multi_batch_run_result": args.output_executed_cycle_dir / "roadmap_multi_batch_run_result.json",
            "core_system_integration_validation": args.output_executed_cycle_dir / "core_system_integration_validation.json",
            "next_step_recommendation": args.output_executed_cycle_dir / "next_step_recommendation.json",
            "next_cycle_decision": args.output_executed_cycle_dir / "next_cycle_decision.json",
            "next_cycle_input_bundle": args.output_executed_cycle_dir / "next_cycle_input_bundle.json",
            "build_summary": args.output_executed_cycle_dir / "build_summary.json",
            "updated_roadmap": args.output_executed_cycle_dir / "roadmap_updated.json",
        }
        for key, path in artifact_paths.items():
            path.write_text(json.dumps(executed_cycle[key], indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": result["cycle_runner_result"]["execution_status"], "result": result["cycle_runner_result"]}, indent=2))
    if result["cycle_runner_result"]["execution_status"] == "executed":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
