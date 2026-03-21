#!/usr/bin/env python3
"""CLI wrapper for the BAH drift detection engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.drift_detection_engine import (  # noqa: E402
    DriftDetectionError,
    run_drift_detection,
)

EXIT_NO_DRIFT = 0
EXIT_DRIFT = 1
EXIT_FAILURE = 2


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare replay and baseline artifacts for drift.")
    parser.add_argument("--replay", required=True, help="Path to replay_result JSON artifact.")
    parser.add_argument("--baseline", default=None, help="Path to baseline replay_result JSON artifact.")
    parser.add_argument("--config", default=None, help="Optional path to drift detection config JSON.")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write drift_detection_result artifact JSON.",
    )
    args = parser.parse_args(argv)

    try:
        replay = _load_json(Path(args.replay))
        baseline = _load_json(Path(args.baseline)) if args.baseline else None
        config = _load_json(Path(args.config)) if args.config else None
        result = run_drift_detection(replay, baseline, config=config)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to load input JSON: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    except DriftDetectionError as exc:
        print(f"ERROR: drift detection failed: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    output_path = Path(args.output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to write output JSON: {exc}", file=sys.stderr)
        return EXIT_FAILURE

    print(json.dumps(result, indent=2))
    if result.get("drift_status") == "no_drift":
        return EXIT_NO_DRIFT
    if result.get("drift_status") == "drift_detected":
        return EXIT_DRIFT
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
