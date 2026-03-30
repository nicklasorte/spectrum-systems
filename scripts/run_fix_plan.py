#!/usr/bin/env python3
"""Generate deterministic fix_plan_artifact from cycle manifest, decision, and remediation artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.orchestration.fix_plan import build_fix_plan_artifact


def _load(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object json: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Path to cycle manifest JSON")
    parser.add_argument("--decision", required=True, help="Path to next_step_decision_artifact JSON")
    parser.add_argument("--remediation", required=True, help="Path to drift_remediation_artifact JSON")
    parser.add_argument("--output", required=True, help="Output path for fix_plan_artifact JSON")
    args = parser.parse_args()

    manifest = _load(args.manifest)
    decision = _load(args.decision)
    remediation = _load(args.remediation)
    artifact = build_fix_plan_artifact(manifest=manifest, decision=decision, remediation=remediation)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
