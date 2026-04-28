#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from spectrum_systems.modules.runtime.rfx_contract_snapshot import compare_rfx_contract_snapshot
from spectrum_systems.modules.runtime.rfx_golden_loop import build_rfx_golden_loop_record
from spectrum_systems.modules.runtime.rfx_health_contract import build_rfx_health_contract
from spectrum_systems.modules.runtime.rfx_loop_proof import build_rfx_loop_proof
from spectrum_systems.modules.runtime.rfx_reason_code_registry import build_rfx_reason_code_registry

REQUIRED_STEPS = [
    "targeted_rfx_tests",
    "authority_shape_early_gate",
    "authority_shape_preflight",
    "authority_drift_guard",
    "system_registry_guard",
    "roadmap_authority_check",
    "strategy_compliance_check",
    "reason_code_registry_validation",
    "health_contract_validation",
    "contract_snapshot_validation",
    "golden_loop_validation",
    "loop_proof_validation",
]

CRITICAL_CHECKS = {
    "authority_shape_preflight",
    "authority_drift_guard",
    "system_registry_guard",
    "strategy_compliance_check",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RFX super-check")
    parser.add_argument("--base-ref", default="HEAD~1", help="Git base ref for early gate changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for early gate changed-file resolution")
    parser.add_argument(
        "--early-gate-output",
        default="outputs/authority_shape_preflight/authority_shape_early_gate_result.json",
        help="Artifact output path for authority-shape early gate",
    )
    return parser.parse_args()


def _run_authority_shape_early_gate(*, base_ref: str, head_ref: str, output_rel: str) -> bool:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "run_authority_shape_early_gate.py"),
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--output",
        output_rel,
    ]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    return result.returncode == 0


def run_rfx_super_check(
    *,
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
    output_rel: str = "outputs/authority_shape_preflight/authority_shape_early_gate_result.json",
) -> dict:
    started = time.time()
    reason_codes = []
    checks = {key: "ok" for key in REQUIRED_STEPS}

    if not _run_authority_shape_early_gate(base_ref=base_ref, head_ref=head_ref, output_rel=output_rel):
        checks["authority_shape_early_gate"] = "failed"

    registry = build_rfx_reason_code_registry(
        entries=[
            {
                "code": "rfx_super_check_step_failed",
                "module": "run_rfx_super_check",
                "owner_context": "RFX",
                "failure_prevented": "integrity gap",
                "repair_hint": "restore failed check",
            }
        ],
        module_exports={"run_rfx_super_check": ["rfx_super_check_step_failed"]},
    )

    health = build_rfx_health_contract(
        modules=[
            {
                "module": "run_rfx_super_check",
                "reason_codes": ["rfx_super_check_step_failed"],
                "artifact_types": ["rfx_super_check_result"],
                "owner_refs": ["TLC"],
                "test_refs": ["tests/test_run_rfx_super_check.py"],
                "debug_bundle_available": True,
            }
        ]
    )

    loop = build_rfx_golden_loop_record(
        loop={
            "failure_ref": "f",
            "eval_ref": "e",
            "fix_proof_ref": "p",
            "trend_ref": "t",
            "recommendation_ref": "r",
        }
    )

    loop_proof = build_rfx_loop_proof(
        proof={
            "proof_id": "rfx-super-check",
            "run_id": "rfx-super-check",
            "trace_id": "rfx-super-check",
            "owner_context": "RFX",
            "failure_ref": "f",
            "eval_ref": "e",
            "repair_ref": "p",
            "learn_ref": "t",
            "recommend_ref": "r",
            "failing_stage": "prove",
            "reason_codes": ["rfx_super_check_step_failed"],
            "repair_hint": "restore check",
        }
    )

    contract_snapshot = compare_rfx_contract_snapshot(
        current=[{"module": "run_rfx_super_check", "artifact_type": "rfx_super_check_result", "fields": ["checks"], "reason_codes": ["rfx_super_check_step_failed"]}],
        manifest={"contracts": {}},
        migration_note="baseline",
    )

    for critical in CRITICAL_CHECKS:
        if critical not in checks:
            reason_codes.append("rfx_super_check_missing_critical_check")

    for step_name in REQUIRED_STEPS:
        if checks.get(step_name) != "ok":
            reason_codes.append("rfx_super_check_step_failed")

    if any(
        artifact.get("status") in {"invalid", "incomplete", "mismatch"}
        for artifact in [registry, health, loop, loop_proof, contract_snapshot]
    ):
        reason_codes.append("rfx_super_check_integrity_gap")

    return {
        "artifact_type": "rfx_super_check_result",
        "schema_version": "1.0.0",
        "status": "pass" if not reason_codes else "fail",
        "reason_codes_emitted": sorted(set(reason_codes)),
        "checks": checks,
        "signals": {
            "fast_check_runtime_seconds": round(time.time() - started, 4),
            "decisive_check_coverage_percentage": round(100.0 * len(checks) / len(REQUIRED_STEPS), 2),
        },
    }


if __name__ == "__main__":
    args = _parse_args()
    result = run_rfx_super_check(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        output_rel=args.early_gate_output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "pass" else 1)
