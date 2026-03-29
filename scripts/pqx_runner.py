#!/usr/bin/env python3
"""Run the minimal governed PQX backbone control loop."""

from __future__ import annotations

import argparse
from pathlib import Path

from spectrum_systems.modules.pqx_backbone import run_pqx_backbone


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic PQX roadmap runner")
    parser.add_argument("--step-id", help="Explicit roadmap step id to execute.")
    parser.add_argument(
        "--pqx-output-file",
        type=Path,
        help="Path to deterministic PQX output text input. Required for execution; if missing, run blocks fail-closed.",
    )
    parser.add_argument(
        "--roadmap-path",
        type=Path,
        default=REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md",
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=REPO_ROOT / "data" / "pqx_state.json",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=REPO_ROOT / "data" / "pqx_runs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pqx_output_text = None
    if args.pqx_output_file:
        pqx_output_text = args.pqx_output_file.read_text(encoding="utf-8")

    result = run_pqx_backbone(
        selected_step_id=args.step_id,
        pqx_output_text=pqx_output_text,
        roadmap_path=args.roadmap_path,
        state_path=args.state_path,
        runs_root=args.runs_root,
    )

    print(result)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
