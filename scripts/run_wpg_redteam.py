#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.wpg.redteam import run_wpg_redteam_suite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic WPG red-team suite")
    parser.add_argument("--output", required=True, help="Path to findings artifact JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = run_wpg_redteam_suite()
    validate_artifact(artifact, "wpg_redteam_findings")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "overall_verdict": artifact["overall_verdict"]}, indent=2))
    return 0 if artifact["overall_verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
