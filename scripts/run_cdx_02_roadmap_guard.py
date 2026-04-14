#!/usr/bin/env python3
"""Run deterministic CDX-02 roadmap guard."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.cdx_02_roadmap_guard import evaluate_cdx_02_roadmap_guard


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CDX-02 roadmap authority guard")
    parser.add_argument("--output", required=True, help="Path for emitted JSON result")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = evaluate_cdx_02_roadmap_guard(repo_root=REPO_ROOT)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
