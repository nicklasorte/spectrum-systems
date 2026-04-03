#!/usr/bin/env python3
"""Run one governed bounded system cycle and emit operator summary artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.system_cycle_operator import SystemCycleOperatorError, run_system_cycle


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-command bounded roadmap run + integration summary emission.")
    parser.add_argument("--roadmap-artifact", type=Path, required=True)
    parser.add_argument("--selection-signals", type=Path, required=True)
    parser.add_argument("--authorization-signals", type=Path, required=True)
    parser.add_argument("--integration-inputs", type=Path, required=True)
    parser.add_argument("--pqx-state-path", type=Path, required=True)
    parser.add_argument("--pqx-runs-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execution-policy", type=Path)
    parser.add_argument("--created-at")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = run_system_cycle(
            roadmap_artifact=_load_json(args.roadmap_artifact),
            selection_signals=_load_json(args.selection_signals),
            authorization_signals=_load_json(args.authorization_signals),
            integration_inputs=_load_json(args.integration_inputs),
            pqx_state_path=args.pqx_state_path,
            pqx_runs_root=args.pqx_runs_root,
            execution_policy=_load_json(args.execution_policy) if args.execution_policy else None,
            created_at=args.created_at,
        )
    except (OSError, ValueError, json.JSONDecodeError, SystemCycleOperatorError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = {
        "roadmap_multi_batch_run_result": args.output_dir / "roadmap_multi_batch_run_result.json",
        "core_system_integration_validation": args.output_dir / "core_system_integration_validation.json",
        "next_step_recommendation": args.output_dir / "next_step_recommendation.json",
        "build_summary": args.output_dir / "build_summary.json",
        "updated_roadmap": args.output_dir / "roadmap_updated.json",
    }

    for key, path in artifact_paths.items():
        path.write_text(json.dumps(result[key], indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "completed",
                "output_dir": str(args.output_dir),
                "build_summary": str(artifact_paths["build_summary"]),
                "next_step_recommendation": str(artifact_paths["next_step_recommendation"]),
                "stop_reason": result["build_summary"]["failure_surface"]["stop_reason"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
