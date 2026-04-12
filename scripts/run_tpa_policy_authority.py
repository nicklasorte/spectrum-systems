#!/usr/bin/env python3
"""Thin CLI for deterministic TPA policy authority evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.tpa_policy_authority import evaluate_tpa_policy_input_bundle, run_redteam_round


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate TPA policy authority bundle")
    parser.add_argument("--input", type=Path, help="Path to tpa_policy_input_bundle JSON")
    parser.add_argument("--redteam-round", help="Run deterministic TPA red-team round id")
    args = parser.parse_args()

    if bool(args.input) == bool(args.redteam_round):
        raise SystemExit("Provide exactly one of --input or --redteam-round")

    if args.input:
        result = evaluate_tpa_policy_input_bundle(_load_json(args.input))
    else:
        result = run_redteam_round(round_id=str(args.redteam_round))

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
