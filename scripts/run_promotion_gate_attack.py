#!/usr/bin/env python3
"""CLI for VAL-01 promotion-gate attack validation."""

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
from spectrum_systems.modules.governance.promotion_gate_attack import (  # noqa: E402
    PromotionGateAttackError,
    run_promotion_gate_attack,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run VAL-01 promotion gate attack validation slice.")
    parser.add_argument("--valid-done-certification", required=True, help="Path to valid done_certification_record artifact.")
    parser.add_argument("--enforcement-input", required=True, help="Path to evaluation_budget_decision artifact.")
    parser.add_argument("--invalid-done-certification", help="Optional path to invalid done certification artifact.")
    parser.add_argument("--failed-done-certification", help="Optional path to failed done certification artifact.")
    parser.add_argument("--malformed-done-certification", help="Optional path to malformed done certification artifact.")
    parser.add_argument("--missing-done-certification", help="Optional path for expected-missing done certification artifact.")
    parser.add_argument("--policy", help="Optional policy reference path for audit linkage.")
    parser.add_argument("--output", required=True, help="Path to write promotion_gate_attack_result artifact.")
    args = parser.parse_args(argv)

    refs: Dict[str, str] = {
        "valid_done_certification_ref": args.valid_done_certification,
        "enforcement_input_ref": args.enforcement_input,
    }
    optional_refs = {
        "invalid_done_certification_ref": args.invalid_done_certification,
        "failed_done_certification_ref": args.failed_done_certification,
        "malformed_done_certification_ref": args.malformed_done_certification,
        "missing_done_certification_ref": args.missing_done_certification,
        "policy_ref": args.policy,
    }
    for key, value in optional_refs.items():
        if value:
            refs[key] = value

    try:
        result = run_promotion_gate_attack(refs)
        validate_artifact(result, "promotion_gate_attack_result")
    except PromotionGateAttackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    output_path = Path(args.output)
    _write_json(output_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))

    if result["final_status"] == "FAILED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
