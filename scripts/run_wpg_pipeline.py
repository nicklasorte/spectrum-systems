#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline_from_file


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run governed WPG pipeline")
    p.add_argument("--input", required=True, help="Input transcript JSON")
    p.add_argument("--output-dir", default="outputs/wpg", help="Output directory")
    p.add_argument("--phase-checkpoint", help="Optional phase checkpoint artifact JSON")
    p.add_argument("--phase-registry", help="Optional phase registry artifact JSON")
    p.add_argument(
        "--mode",
        default="working_paper",
        choices=["working_paper", "executive_summary", "FAQ_brief", "slide_outline"],
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if args.phase_checkpoint:
        payload["phase_checkpoint_record"] = json.loads(Path(args.phase_checkpoint).read_text(encoding="utf-8"))
    if args.phase_registry:
        payload["phase_registry"] = json.loads(Path(args.phase_registry).read_text(encoding="utf-8"))
    input_path_with_phase = input_path
    if args.phase_checkpoint or args.phase_registry:
        input_path_with_phase = Path(args.output_dir) / "_wpg_input_with_phase.json"
        input_path_with_phase.parent.mkdir(parents=True, exist_ok=True)
        input_path_with_phase.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    bundle = run_wpg_pipeline_from_file(input_path_with_phase, Path(args.output_dir), mode=args.mode)
    print(json.dumps({
        "run_id": bundle["run_id"],
        "trace_id": bundle["trace_id"],
        "mode": bundle["mode"],
        "artifacts": sorted(bundle["artifact_chain"].keys()),
        "replay_signature": bundle["replay"]["signature"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
