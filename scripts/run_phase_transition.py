#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.wpg.phase_governance import default_phase_registry, evaluate_phase_transition
from spectrum_systems.modules.runtime.checkpoint_stage_contracts import evaluate_checkpoint_transition


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate governed WPG phase transition eligibility")
    parser.add_argument("--checkpoint", required=True, help="Path to phase_checkpoint_record JSON")
    parser.add_argument("--registry", help="Path to phase_registry JSON")
    parser.add_argument("--action", default="continue", choices=["start", "continue", "resume"])
    parser.add_argument("--redteam-open-high", type=int, default=0)
    parser.add_argument("--validation-passed", choices=["true", "false"], default="true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checkpoint = _load_json(Path(args.checkpoint))
    registry = _load_json(Path(args.registry)) if args.registry else default_phase_registry(checkpoint["trace_id"])
    result = evaluate_phase_transition(
        phase_checkpoint_record=checkpoint,
        phase_registry=registry,
        requested_action=args.action,
        redteam_open_high=args.redteam_open_high,
        validation_passed=args.validation_passed == "true",
    )
    evaluate_checkpoint_transition(
        trace_id=checkpoint["trace_id"],
        current_state="ACTIVE",
        action="COMPLETE" if result["decision"] == "ALLOW" else "HIBERNATE",
    )
    print(json.dumps(result, indent=2))
    return 0 if result["decision"] == "ALLOW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
