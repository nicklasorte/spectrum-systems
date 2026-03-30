#!/usr/bin/env python3
"""Run deterministic next-step decision engine for a cycle manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.orchestration.next_step_decision import build_next_step_decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Path to cycle manifest JSON")
    args = parser.parse_args()

    decision = build_next_step_decision(args.manifest)
    print(json.dumps(decision, indent=2))
    return 1 if decision.get("blocking") else 0


if __name__ == "__main__":
    raise SystemExit(main())
