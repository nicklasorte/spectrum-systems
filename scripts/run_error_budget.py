#!/usr/bin/env python3
"""Build a governed error_budget_status artifact from observability + SLO artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.error_budget import (  # noqa: E402
    ErrorBudgetError,
    build_error_budget_status,
    load_error_budget_policy,
)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorBudgetError(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorBudgetError(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ErrorBudgetError(f"input file must contain an object: {path}")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic error_budget_status artifact.")
    parser.add_argument("--observability", required=True, help="Path to observability_metrics artifact JSON.")
    parser.add_argument("--slo", required=True, help="Path to service_level_objective artifact JSON.")
    parser.add_argument("--policy", help="Optional path to error_budget_policy artifact JSON.")
    parser.add_argument("--trace-id", help="Optional explicit trace ID override.")
    parser.add_argument("--output", required=True, help="Output path for error_budget_status JSON artifact.")
    args = parser.parse_args(argv)

    observability = _load_json(Path(args.observability))
    slo = _load_json(Path(args.slo))

    if args.policy:
        policy = _load_json(Path(args.policy))
    else:
        policy = load_error_budget_policy()

    status = build_error_budget_status(
        observability,
        slo,
        policy=policy,
        trace_id=args.trace_id,
    )
    validate_artifact(status, "error_budget_status")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ErrorBudgetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
