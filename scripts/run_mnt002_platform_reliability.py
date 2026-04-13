#!/usr/bin/env python3
"""Thin CLI to execute MNT-002 platform reliability runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spectrum_systems.modules.runtime.platform_reliability_ops import run_mnt002_platform_reliability


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MNT-002 platform reliability bundle generation")
    parser.add_argument("--evidence", required=True, help="Path to evidence JSON")
    parser.add_argument("--output", required=True, help="Path to output bundle JSON")
    parser.add_argument("--now", default=None, help="Optional ISO timestamp override")
    args = parser.parse_args()

    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    artifact = run_mnt002_platform_reliability(evidence, now_iso=args.now)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
