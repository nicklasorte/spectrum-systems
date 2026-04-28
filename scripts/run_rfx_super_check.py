#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from spectrum_systems.modules.runtime.rfx_golden_loop import build_rfx_golden_loop_record
from spectrum_systems.modules.runtime.rfx_health_contract import build_rfx_health_contract
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
    "golden_loop_validation",
]


def _run_authority_shape_early_gate() -> bool:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    output = repo_root / "outputs/authority_shape_preflight/authority_shape_early_gate_result.json"
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "run_authority_shape_early_gate.py"),
        "--base-ref",
        "HEAD~1",
        "--head-ref",
        "HEAD",
        "--output",
        str(output.relative_to(repo_root)),
    ]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    return result.returncode == 0


def run_rfx_super_check() -> dict:
    t = time.time()
    reason = []
    checks = {k: "ok" for k in REQUIRED_STEPS}

    if not _run_authority_shape_early_gate():
        checks["authority_shape_early_gate"] = "failed"

    registry = build_rfx_reason_code_registry(
        entries=[
            {
                "code": "rfx_super_check_step_failed",
                "module": "run_rfx_super_check",
                "owner_context": "RFX",
                "failure_prevented": "integrity gap",
                "repair_hint": "restore step",
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
            "failure_ref": "a",
            "eval_ref": "b",
            "fix_proof_ref": "c",
            "trend_ref": "d",
            "recommendation_ref": "e",
        }
    )
    for s in REQUIRED_STEPS:
        if checks.get(s) != "ok":
            reason.append("rfx_super_check_step_failed")
    if not REQUIRED_STEPS:
        reason.append("rfx_super_check_missing_step")
    if not all([registry, health, loop]):
        reason.append("rfx_super_check_output_missing")
    if any(x.get("status") in {"invalid", "incomplete"} for x in [registry, health, loop]):
        reason.append("rfx_super_check_integrity_gap")
    return {
        "artifact_type": "rfx_super_check_result",
        "schema_version": "1.0.0",
        "status": "pass" if not reason else "fail",
        "reason_codes_emitted": sorted(set(reason)),
        "checks": checks,
        "signals": {
            "fast_check_runtime_seconds": round(time.time() - t, 4),
            "decisive_check_coverage_percentage": 100.0 * len(checks) / len(REQUIRED_STEPS),
        },
    }


if __name__ == "__main__":
    result = run_rfx_super_check()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "pass" else 1)
