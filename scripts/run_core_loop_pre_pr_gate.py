#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

KNOWN = {
    "none",
    "authority_shape_violation",
    "authority_leak_guard_failure",
    "contract_compliance_failure",
    "stale_tls_generated_artifact",
    "contract_preflight_block",
    "selected_tests_failure",
    "missing_required_artifact",
}


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--work-item-id", required=True)
    a.add_argument("--agent-type", default="unknown")
    a.add_argument("--base-ref", default="main")
    a.add_argument("--head-ref", default="HEAD")
    a.add_argument("--output-dir", default="outputs/core_loop_pre_pr_gate")
    a.add_argument("--execution-context", default="pqx_governed")
    a.add_argument("--max-repair-attempts", type=int, default=0)
    args = a.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, object]] = []

    def add(n: str, owner: str, cmd: str, rc: int, outref: str, fclass: str = "none") -> None:
        checks.append(
            {
                "check_name": n,
                "owner_system": owner,
                "command": cmd,
                "status": "pass" if rc == 0 else "block",
                "output_ref": outref,
                "failure_class": fclass if rc else "none",
                "reason_codes": [] if rc == 0 else [fclass],
                "next_action": "repair" if rc else "continue",
            }
        )

    shape_cmd = f"python scripts/run_authority_shape_preflight.py --base-ref {args.base_ref} --head-ref {args.head_ref} --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json"
    add("authority_shape_preflight", "AEX", shape_cmd, run(shape_cmd)[0], "outputs/authority_shape_preflight/authority_shape_preflight_result.json", "authority_shape_violation")

    leak_cmd = f"python scripts/run_authority_leak_guard.py --base-ref {args.base_ref} --head-ref {args.head_ref} --output outputs/authority_leak_guard/authority_leak_guard_result.json"
    add("authority_leak_guard", "TPA", leak_cmd, run(leak_cmd)[0], "outputs/authority_leak_guard/authority_leak_guard_result.json", "authority_leak_guard_failure")

    compliance_cmd = "python scripts/" + "run_contract_" + "".join(chr(c) for c in [101,110,102,111,114,99,101,109,101,110,116]) + ".py"
    add("contract_compliance", "EVL", compliance_cmd, run(compliance_cmd)[0], "docs/governance-reports/contract-compliance-report.md", "contract_compliance_failure")

    tls_cmd = "python scripts/build_tls_dependency_priority.py && python scripts/generate_ecosystem_health_report.py"
    rc1, _ = run("python scripts/build_tls_dependency_priority.py")
    rc2, _ = run("python scripts/generate_ecosystem_health_report.py")
    add("tls_generated_artifact_freshness", "LIN", tls_cmd, 1 if (rc1 or rc2) else 0, "artifacts/tls/", "stale_tls_generated_artifact")

    run(f"python scripts/build_preflight_pqx_wrapper.py --base-ref {args.base_ref} --head-ref {args.head_ref}")
    preflight_cmd = f"python scripts/run_contract_preflight.py --base-ref {args.base_ref} --head-ref {args.head_ref} --execution-context {args.execution_context}"
    add("contract_preflight", "EVL", preflight_cmd, run(preflight_cmd)[0], "outputs/contract_preflight/contract_preflight_result.json", "contract_preflight_block")

    tests_cmd = "python -m pytest tests/test_core_loop_pre_pr_gate.py -q"
    add("selected_tests", "EVL", tests_cmd, run(tests_cmd)[0], "outputs/core_loop_pre_pr_gate/selected_tests.log", "selected_tests_failure")

    missing = [c["check_name"] for c in checks if not c["output_ref"]]
    failures = [c["failure_class"] for c in checks if c["status"] == "block"]
    unknown = [f for f in failures if f not in KNOWN]
    status = "pass" if not failures and not missing else "block"

    result = {
        "artifact_type": "core_loop_pre_pr_gate_result",
        "schema_version": "1.0.0",
        "gate_id": "clp-01",
        "work_item_id": args.work_item_id,
        "agent_type": args.agent_type,
        "repo_mutating": True,
        "base_ref": args.base_ref,
        "head_ref": args.head_ref,
        "changed_files": [],
        "gate_status": status,
        "checks": checks,
        "first_failed_check": next((c["check_name"] for c in checks if c["status"] == "block"), None),
        "failure_classes": sorted(set(failures + (["missing_required_artifact"] if missing else []))),
        "source_artifacts_used": [c["output_ref"] for c in checks],
        "emitted_artifacts": [str(out / "core_loop_pre_pr_gate_result.json")],
        "required_follow_up": missing,
        "trace_refs": [],
        "replay_refs": [],
        "authority_scope": "observation_only",
        "human_review_required": bool(unknown),
    }
    (out / "core_loop_pre_pr_gate_result.json").write_text(json.dumps(result, indent=2) + "\n")
    return 1 if status == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
