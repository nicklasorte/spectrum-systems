#!/usr/bin/env python3
"""CLI for VAL-06 XRUN signal quality validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.xrun_signal_quality import (  # noqa: E402
    XRunSignalQualityError,
    run_xrun_signal_quality_validation,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise XRunSignalQualityError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise XRunSignalQualityError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise XRunSignalQualityError(f"{label} must be a JSON array")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise XRunSignalQualityError(f"{label}[{idx}] must be a JSON object")
    return payload


def _load_policy(path: Path) -> Dict[str, Any]:
    payload = _load_json(path, label="policy_ref")
    if not isinstance(payload, dict):
        raise XRunSignalQualityError("policy_ref must be a JSON object")
    return payload


def _load_optional_expected(path: Path | None) -> Dict[str, Any] | None:
    if path is None:
        return None
    payload = _load_json(path, label="expected_outcomes_ref")
    if not isinstance(payload, dict):
        raise XRunSignalQualityError("expected_outcomes_ref must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-06 XRUN signal quality validation.")
    parser.add_argument("--replay-results", type=Path, required=True)
    parser.add_argument("--eval-summaries", type=Path, required=True)
    parser.add_argument("--regression-results", type=Path, required=True)
    parser.add_argument("--drift-results", type=Path, required=True)
    parser.add_argument("--monitor-records", type=Path, required=True)
    parser.add_argument("--policy-ref", type=Path, required=True)
    parser.add_argument("--expected-outcomes-ref", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "replay_results": _load_array(args.replay_results, label="replay_results"),
        "eval_summaries": _load_array(args.eval_summaries, label="eval_summaries"),
        "regression_results": _load_array(args.regression_results, label="regression_results"),
        "drift_results": _load_array(args.drift_results, label="drift_results"),
        "monitor_records": _load_array(args.monitor_records, label="monitor_records"),
        "policy_ref": _load_policy(args.policy_ref),
    }

    expected_outcomes = _load_optional_expected(args.expected_outcomes_ref)
    if expected_outcomes is not None:
        payload["expected_outcomes_ref"] = expected_outcomes
        payload["expected_outcomes_ref_path"] = str(args.expected_outcomes_ref)

    result = run_xrun_signal_quality_validation(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except XRunSignalQualityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
