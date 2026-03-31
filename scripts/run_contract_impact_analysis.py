#!/usr/bin/env python3
"""Run deterministic contract impact analysis and emit governed artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.governance import (  # noqa: E402
    ContractImpactAnalysisError,
    analyze_contract_impact,
    write_contract_impact_artifact,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic governed contract impact analysis")
    parser.add_argument("--changed-contract-path", action="append", required=True)
    parser.add_argument("--changed-example-path", action="append", default=[])
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--baseline-ref", default="HEAD")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        artifact = analyze_contract_impact(
            repo_root=REPO_ROOT,
            changed_contract_paths=args.changed_contract_path,
            changed_example_paths=args.changed_example_path,
            baseline_ref=args.baseline_ref,
        )
    except ContractImpactAnalysisError as exc:
        print(json.dumps({"error": str(exc), "blocking": True}, indent=2), file=sys.stderr)
        return 2

    output_path = Path(args.output_path)
    write_contract_impact_artifact(artifact, output_path)

    try:
        validate_artifact(artifact, "contract_impact_artifact")
    except Exception as exc:  # pragma: no cover - hard fail branch
        print(json.dumps({"error": f"artifact schema validation failed: {exc}", "blocking": True}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps({"output_path": str(output_path), "compatibility_class": artifact["compatibility_class"], "blocking": artifact["blocking"]}, indent=2))

    if artifact["compatibility_class"] in {"breaking", "indeterminate"}:
        return 2
    if artifact["blocking"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
