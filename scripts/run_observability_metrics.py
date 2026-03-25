#!/usr/bin/env python3
"""Build a governed observability_metrics artifact from governed source artifacts."""

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
from spectrum_systems.modules.runtime.observability_metrics import (  # noqa: E402
    ObservabilityMetricsError,
    build_observability_metrics,
)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ObservabilityMetricsError(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ObservabilityMetricsError(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ObservabilityMetricsError(f"input file must contain an object: {path}")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic observability_metrics artifact.")
    parser.add_argument(
        "--source-artifact",
        action="append",
        required=True,
        help="Path to a governed source artifact JSON file. Can be repeated.",
    )
    parser.add_argument("--slo", help="Optional path to service_level_objective artifact.")
    parser.add_argument("--trace-id", help="Optional explicit trace ID override.")
    parser.add_argument("--output", required=True, help="Output path for observability_metrics JSON artifact.")
    args = parser.parse_args(argv)

    source_artifacts = [_load_json(Path(path)) for path in args.source_artifact]
    slo = _load_json(Path(args.slo)) if args.slo else None

    metrics = build_observability_metrics(source_artifacts, slo_definition=slo, trace_id=args.trace_id)
    validate_artifact(metrics, "observability_metrics")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ObservabilityMetricsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
