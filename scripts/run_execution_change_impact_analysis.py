#!/usr/bin/env python3
"""Run deterministic execution change impact analysis and emit governed artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.governance import (  # noqa: E402
    ExecutionChangeImpactAnalysisError,
    analyze_execution_change_impact,
    write_execution_change_impact_artifact,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic governed execution change impact analysis")
    parser.add_argument("--changed-path", action="append", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--baseline-ref", default="HEAD")
    parser.add_argument("--provided-review", action="append", default=[])
    parser.add_argument("--provided-eval-artifact", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        artifact = analyze_execution_change_impact(
            repo_root=REPO_ROOT,
            changed_paths=args.changed_path,
            baseline_ref=args.baseline_ref,
            provided_reviews=args.provided_review,
            provided_eval_artifacts=args.provided_eval_artifact,
        )
    except ExecutionChangeImpactAnalysisError as exc:
        print(json.dumps({"error": str(exc), "blocking": True, "indeterminate": True}, indent=2), file=sys.stderr)
        return 2

    output_path = Path(args.output_path)
    write_execution_change_impact_artifact(artifact, output_path)

    try:
        validate_artifact(artifact, "execution_change_impact_artifact")
    except Exception as exc:  # pragma: no cover - hard fail branch
        print(json.dumps({"error": f"artifact schema validation failed: {exc}", "blocking": True}, indent=2), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "risk_classification": artifact["risk_classification"],
                "blocking": artifact["blocking"],
                "indeterminate": artifact["indeterminate"],
                "safe_to_execute": artifact["safe_to_execute"],
            },
            indent=2,
        )
    )

    if artifact["blocking"] or artifact["indeterminate"] or artifact["safe_to_execute"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
