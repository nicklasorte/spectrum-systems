#!/usr/bin/env python3
"""Run deterministic BATCH-Y operator shakeout scenarios and emit governed friction/backlog artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.operator_shakeout import run_operator_shakeout


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BATCH-Y operator shakeout over deterministic system-cycle scenarios.")
    parser.add_argument("--pqx-state-path", type=Path, required=True)
    parser.add_argument("--pqx-runs-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--created-at")
    parser.add_argument("--scenario-id", action="append", dest="scenario_ids")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = run_operator_shakeout(
            pqx_state_path=args.pqx_state_path,
            pqx_runs_root=args.pqx_runs_root,
            created_at=args.created_at,
            scenario_ids=args.scenario_ids,
        )
    except Exception as exc:  # deterministic wrapper surface for operators/CI
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "operator_friction_report": args.output_dir / "operator_friction_report.json",
        "operator_backlog_handoff": args.output_dir / "operator_backlog_handoff.json",
        "scenario_results": args.output_dir / "scenario_results.json",
    }

    paths["operator_friction_report"].write_text(json.dumps(result["operator_friction_report"], indent=2) + "\n", encoding="utf-8")
    paths["operator_backlog_handoff"].write_text(json.dumps(result["operator_backlog_handoff"], indent=2) + "\n", encoding="utf-8")
    paths["scenario_results"].write_text(json.dumps(result["scenario_results"], indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "completed",
                "trace_id": result["trace_id"],
                "output_dir": str(args.output_dir),
                "operator_friction_report": str(paths["operator_friction_report"]),
                "operator_backlog_handoff": str(paths["operator_backlog_handoff"]),
                "scenarios_executed": len(result["scenario_results"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
