#!/usr/bin/env python3
"""CLI for VAL-11 certification integrity validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.certification_integrity import (  # noqa: E402
    CertificationIntegrityError,
    run_certification_integrity_validation,
)


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CertificationIntegrityError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CertificationIntegrityError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def _load_array(path: Path, *, label: str) -> List[Dict[str, Any]]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, list):
        raise CertificationIntegrityError(f"{label} must be a JSON array")
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise CertificationIntegrityError(f"{label}[{idx}] must be a JSON object")
    return payload


def _load_object(path: Path, *, label: str) -> Dict[str, Any]:
    payload = _load_json(path, label=label)
    if not isinstance(payload, dict):
        raise CertificationIntegrityError(f"{label} must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-11 certification integrity validation matrix.")
    parser.add_argument("--replay-results", type=Path, required=True)
    parser.add_argument("--regression-results", type=Path, required=True)
    parser.add_argument("--error-budget-statuses", type=Path, required=True)
    parser.add_argument("--failure-injection-results", type=Path, required=True)
    parser.add_argument("--control-decisions", type=Path, required=True)
    parser.add_argument("--policy-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload: Dict[str, Any] = {
        "replay_results": _load_array(args.replay_results, label="replay_results"),
        "regression_results": _load_array(args.regression_results, label="regression_results"),
        "error_budget_statuses": _load_array(args.error_budget_statuses, label="error_budget_statuses"),
        "failure_injection_results": _load_array(args.failure_injection_results, label="failure_injection_results"),
        "control_decisions": _load_array(args.control_decisions, label="control_decisions"),
        "policy_ref": _load_object(args.policy_ref, label="policy_ref"),
    }

    result = run_certification_integrity_validation(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CertificationIntegrityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
