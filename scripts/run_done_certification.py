#!/usr/bin/env python3
"""CLI for deterministic DONE-01 fail-closed certification gate."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.governance.done_certification import (  # noqa: E402
    DoneCertificationError,
    run_done_certification,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run DONE-01 deterministic done certification gate.")
    parser.add_argument("--replay-result", required=True, help="Path to replay_result artifact.")
    parser.add_argument("--regression-result", required=True, help="Path to regression_result artifact.")
    parser.add_argument("--certification-pack", required=True, help="Path to control_loop_certification_pack artifact.")
    parser.add_argument("--error-budget", required=True, help="Path to error_budget_status artifact.")
    parser.add_argument("--policy", required=True, help="Path to evaluation_control_decision artifact.")
    parser.add_argument("--failure-injection", help="Optional path to governed_failure_injection_summary artifact.")
    parser.add_argument("--output", required=True, help="Path to write done_certification_record artifact.")
    parser.add_argument("--error-output", help="Optional path to write done_certification_error artifact on failures.")
    args = parser.parse_args(argv)

    refs: Dict[str, str] = {
        "replay_result_ref": args.replay_result,
        "regression_result_ref": args.regression_result,
        "certification_pack_ref": args.certification_pack,
        "error_budget_ref": args.error_budget,
        "policy_ref": args.policy,
    }
    if args.failure_injection:
        refs["failure_injection_ref"] = args.failure_injection

    try:
        record = run_done_certification(refs)
        validate_artifact(record, "done_certification_record")
    except DoneCertificationError as exc:
        if args.error_output:
            error_artifact = {
                "artifact_type": "done_certification_error",
                "schema_version": "1.0.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_code": "DONE_CERTIFICATION_FAILED",
                "message": str(exc),
                "input_refs": refs,
                "trace_id": None,
            }
            validate_artifact(error_artifact, "done_certification_error")
            _write_json(Path(args.error_output), error_artifact)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    output_path = Path(args.output)
    _write_json(output_path, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    if record["final_status"] == "FAILED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
