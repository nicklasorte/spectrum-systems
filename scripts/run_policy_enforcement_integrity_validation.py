#!/usr/bin/env python3
"""CLI for VAL-10 policy enforcement integrity validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.governance.policy_enforcement_integrity import (  # noqa: E402
    PolicyEnforcementIntegrityError,
    run_policy_enforcement_integrity_validation,
)


def _load_optional(path: Path | None, *, label: str) -> Any:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyEnforcementIntegrityError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyEnforcementIntegrityError(f"{label} file is not valid JSON: {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VAL-10 policy enforcement integrity validation matrix.")
    parser.add_argument("--policy-ref", type=Path)
    parser.add_argument("--alternate-policy-ref", type=Path)
    parser.add_argument("--eval-summary-ref", type=Path)
    parser.add_argument("--error-budget-status-ref", type=Path)
    parser.add_argument("--monitor-record-ref", type=Path)
    parser.add_argument("--control-decision-ref", type=Path)
    parser.add_argument("--certification-pack-ref", type=Path)
    parser.add_argument("--done-certification-ref", type=Path)
    parser.add_argument("--replay-result-ref", type=Path)
    parser.add_argument("--routing-input-ref", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload: Dict[str, Any] = {}
    for key, path in {
        "policy_ref": args.policy_ref,
        "alternate_policy_ref": args.alternate_policy_ref,
        "eval_summary_ref": args.eval_summary_ref,
        "error_budget_status_ref": args.error_budget_status_ref,
        "monitor_record_ref": args.monitor_record_ref,
        "control_decision_ref": args.control_decision_ref,
        "certification_pack_ref": args.certification_pack_ref,
        "done_certification_ref": args.done_certification_ref,
        "replay_result_ref": args.replay_result_ref,
        "routing_input_ref": args.routing_input_ref,
    }.items():
        loaded = _load_optional(path, label=key)
        if loaded is not None:
            payload[key] = loaded

    result = run_policy_enforcement_integrity_validation(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(args.output))
    return 0 if result.get("final_status") == "PASSED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PolicyEnforcementIntegrityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
