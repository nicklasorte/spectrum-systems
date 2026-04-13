#!/usr/bin/env python3
"""Run governed preflight BLOCK auto-repair flow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spectrum_systems.modules.runtime.github_pr_autofix_contract_preflight import (
    ContractPreflightAutofixError,
    run_preflight_block_autorepair,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Governed contract preflight BLOCK auto-repair")
    parser.add_argument("--output-dir", default="outputs/contract_preflight")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--execution-context", default="pqx_governed")
    parser.add_argument("--pqx-wrapper-path", default="outputs/contract_preflight/preflight_pqx_task_wrapper.json")
    parser.add_argument("--authority-evidence-ref", required=True)
    parser.add_argument("--same-repo-write-allowed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    try:
        result = run_preflight_block_autorepair(
            repo_root=Path(__file__).resolve().parents[1],
            output_dir=output_dir,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            execution_context=args.execution_context,
            pqx_wrapper_path=Path(args.pqx_wrapper_path),
            authority_evidence_ref=args.authority_evidence_ref,
            same_repo_write_allowed=bool(args.same_repo_write_allowed),
        )
    except ContractPreflightAutofixError as exc:
        bundle_paths = {
            "diagnosis": str(output_dir / "preflight_block_diagnosis_record.json"),
            "repair_plan": str(output_dir / "preflight_repair_plan_record.json"),
            "repair_candidate": str(output_dir / "failure_repair_candidate_artifact.json"),
            "rerun_decision": str(output_dir / "preflight_repair_result_record.json"),
            "escalation": str(output_dir / "preflight_human_escalation_record.json"),
        }
        print(json.dumps({"status": "blocked", "error": str(exc), "artifact_paths": bundle_paths}))
        return 2
    print(json.dumps({"status": "passed", "result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
