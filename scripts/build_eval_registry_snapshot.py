#!/usr/bin/env python3
"""Build a governed eval_registry_snapshot from policy + datasets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.evaluation.eval_dataset_loader import (  # noqa: E402
    load_eval_admission_policy,
    load_eval_dataset,
)
from spectrum_systems.modules.evaluation.eval_dataset_registry import (  # noqa: E402
    build_registry_snapshot,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an eval_registry_snapshot artifact")
    parser.add_argument("--policy", required=True, help="Path to eval_admission_policy JSON")
    parser.add_argument("--datasets", nargs="+", required=True, help="One or more eval_dataset JSON paths")
    parser.add_argument("--snapshot-id", required=True, help="Snapshot identifier")
    parser.add_argument("--trace-id", required=True, help="Trace identifier")
    parser.add_argument("--run-id", required=True, help="Run identifier")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args(argv)

    policy = load_eval_admission_policy(args.policy)
    datasets = [load_eval_dataset(path) for path in args.datasets]

    snapshot = build_registry_snapshot(
        snapshot_id=args.snapshot_id,
        trace_id=args.trace_id,
        run_id=args.run_id,
        active_policy_id=policy["policy_id"],
        datasets=datasets,
    )

    rendered = json.dumps(snapshot, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
