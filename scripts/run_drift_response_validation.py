#!/usr/bin/env python3
"""CLI for VAL-09 drift response validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.drift_response_validation import (  # noqa: E402
    DriftResponseValidationError,
    run_drift_response_validation,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DriftResponseValidationError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DriftResponseValidationError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise DriftResponseValidationError(f"{label} must be a JSON array")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise DriftResponseValidationError(f"{label}[{idx}] must be a JSON object")
    return payload


def _load_object(path: Path, *, label: str) -> Dict[str, Any]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, dict):
        raise DriftResponseValidationError(f"{label} must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-09 drift response validation.")
    parser.add_argument("--replay-results", type=Path, required=True)
    parser.add_argument("--baseline-gate-policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = {
        "replay_results": _load_array(args.replay_results, label="replay_results"),
        "baseline_gate_policy": _load_object(args.baseline_gate_policy, label="baseline_gate_policy"),
    }

    result = run_drift_response_validation(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DriftResponseValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
