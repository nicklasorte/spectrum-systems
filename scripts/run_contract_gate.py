"""
Contract Gate runner — Gate 1 of 4.

Runs schema enforcement, artifact boundary, module architecture, system registry guard,
authority drift/leak guard, and contract preflight. Emits one structured gate result artifact.

Fail-closed: any missing required artifact or non-ALLOW decision exits non-zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


_GATE_NAME = "contract_gate"
_SCHEMA_VERSION = "1.0.0"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def _fail_closed(reason: str, gate_name: str, root_cause: str, next_action: str,
                 affected_files: list[str], failed_command: str,
                 artifact_refs: list[str], output_dir: Path) -> None:
    failure_summary = {
        "gate_name": gate_name,
        "failure_class": "contract_gate_failure",
        "root_cause": root_cause,
        "blocking_reason": reason,
        "next_action": next_action,
        "affected_files": affected_files,
        "failed_command": failed_command,
        "artifact_refs": artifact_refs,
    }
    result = _build_result("block", {}, failure_summary)
    _write_result(result, output_dir)
    print(f"[contract_gate] BLOCK: {reason}", file=sys.stderr)
    sys.exit(1)


def _build_result(status: str, details: dict, failure_summary: dict | None) -> dict:
    payload: dict = {
        "artifact_type": "contract_gate_result",
        "schema_version": _SCHEMA_VERSION,
        "gate_name": _GATE_NAME,
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_contract_gate.py",
        **details,
    }
    if failure_summary:
        payload["failure_summary"] = failure_summary
    text = json.dumps(payload, sort_keys=True, indent=2)
    payload["artifact_hash"] = _sha256(text)
    return payload


def _write_result(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "contract_gate_result.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[contract_gate] result written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Contract Gate runner")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--output-dir", default="outputs/gates")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--execution-context", default="pqx_governed")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    repo_root = Path(args.repo_root)
    executed_commands: list[str] = []
    details: dict = {
        "base_ref": args.base_ref,
        "head_ref": args.head_ref,
        "execution_context": args.execution_context,
        "executed_commands": executed_commands,
    }

    # Step 1: Artifact boundary check
    cmd = [sys.executable, "scripts/check_artifact_boundary.py"]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "artifact boundary check failed",
            _GATE_NAME,
            err.strip() or out.strip() or "check_artifact_boundary.py non-zero exit",
            "Fix artifact boundary violations in the changed files",
            [],
            "scripts/check_artifact_boundary.py",
            [],
            output_dir,
        )

    # Step 2: Module architecture validation
    cmd = [sys.executable, "scripts/validate_module_architecture.py"]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "module architecture validation failed",
            _GATE_NAME,
            err.strip() or out.strip(),
            "Fix module cross-write violations",
            [],
            "scripts/validate_module_architecture.py",
            [],
            output_dir,
        )

    # Step 3: Orchestration boundary validation
    cmd = [sys.executable, "scripts/validate_orchestration_boundaries.py"]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "orchestration boundary validation failed",
            _GATE_NAME,
            err.strip() or out.strip(),
            "Fix orchestration boundary violations",
            [],
            "scripts/validate_orchestration_boundaries.py",
            [],
            output_dir,
        )

    # Step 4: Authority shape preflight (suggest-only, informational)
    authority_shape_out = repo_root / "outputs/authority_shape_preflight"
    authority_shape_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "scripts/run_authority_shape_preflight.py",
        "--base-ref", args.base_ref,
        "--head-ref", args.head_ref,
        "--suggest-only",
        "--output", str(authority_shape_out / "authority_shape_preflight_result.json"),
    ]
    executed_commands.append(" ".join(cmd))
    _run(cmd, cwd=str(repo_root))  # suggest-only; non-blocking

    # Step 5: Authority drift guard
    authority_drift_out = repo_root / "outputs/authority_drift_guard"
    authority_drift_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "scripts/run_authority_drift_guard.py",
        "--base-ref", args.base_ref,
        "--head-ref", args.head_ref,
        "--output", str(authority_drift_out / "authority_drift_guard_result.json"),
    ]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "authority drift guard failed",
            _GATE_NAME,
            err.strip() or out.strip(),
            "Resolve authority drift violations before proceeding",
            [],
            "scripts/run_authority_drift_guard.py",
            [str(authority_drift_out / "authority_drift_guard_result.json")],
            output_dir,
        )

    # Step 6: System registry guard
    srg_out = repo_root / "outputs/system_registry_guard"
    srg_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "scripts/run_system_registry_guard.py",
        "--base-ref", args.base_ref,
        "--head-ref", args.head_ref,
        "--output", str(srg_out / "system_registry_guard_result.json"),
    ]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "system registry guard failed",
            _GATE_NAME,
            err.strip() or out.strip(),
            "Fix system registry violations before proceeding",
            ["docs/architecture/system_registry.md"],
            "scripts/run_system_registry_guard.py",
            [str(srg_out / "system_registry_guard_result.json")],
            output_dir,
        )

    # Step 7: Authority leak guard
    leak_out = repo_root / "outputs/authority_leak_guard"
    leak_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "scripts/run_authority_leak_guard.py",
        "--base-ref", args.base_ref,
        "--head-ref", args.head_ref,
        "--output", str(leak_out / "authority_leak_guard_result.json"),
    ]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "authority leak guard failed",
            _GATE_NAME,
            err.strip() or out.strip(),
            "Fix authority leak violations",
            [],
            "scripts/run_authority_leak_guard.py",
            [str(leak_out / "authority_leak_guard_result.json")],
            output_dir,
        )

    # Step 8: Contract preflight (the core schema + pytest selection + execution gate)
    preflight_out = repo_root / "outputs/contract_preflight"
    preflight_out.mkdir(parents=True, exist_ok=True)
    pqx_wrapper = preflight_out / "preflight_pqx_task_wrapper.json"

    cmd = [
        sys.executable, "scripts/build_preflight_pqx_wrapper.py",
        "--base-ref", args.base_ref,
        "--head-ref", args.head_ref,
        "--output", str(pqx_wrapper),
    ]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    if rc != 0:
        _fail_closed(
            "preflight PQX wrapper build failed",
            _GATE_NAME,
            err.strip() or out.strip(),
            "Diagnose build_preflight_pqx_wrapper.py failure",
            [],
            "scripts/build_preflight_pqx_wrapper.py",
            [],
            output_dir,
        )

    env = {**os.environ, "GITHUB_EVENT_NAME": os.environ.get("GITHUB_EVENT_NAME", "pull_request")}
    for k in ("GITHUB_BASE_SHA", "GITHUB_HEAD_SHA", "GITHUB_BEFORE_SHA", "GITHUB_SHA"):
        if k in os.environ:
            env[k] = os.environ[k]

    cmd = [
        sys.executable, "scripts/run_contract_preflight.py",
        "--base-ref", args.base_ref,
        "--head-ref", args.head_ref,
        "--output-dir", str(preflight_out),
        "--execution-context", args.execution_context,
        "--pqx-wrapper-path", str(pqx_wrapper),
        "--authority-evidence-ref", "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json",
    ]
    executed_commands.append(" ".join(cmd))
    rc, out, err = _run(cmd, cwd=str(repo_root))
    details["preflight_exit_code"] = rc

    # Validate contract preflight result artifact (canonical trust enforcement)
    artifact_path = preflight_out / "contract_preflight_result_artifact.json"
    if not artifact_path.is_file():
        _fail_closed(
            "missing contract_preflight_result_artifact.json",
            _GATE_NAME,
            "run_contract_preflight.py did not produce required result artifact",
            "Diagnose run_contract_preflight.py failure",
            [],
            "scripts/run_contract_preflight.py",
            [],
            output_dir,
        )

    preflight_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    decision = str((preflight_payload.get("control_signal") or {}).get("strategy_gate_decision") or "BLOCK")
    record_ref = str(preflight_payload.get("pytest_execution_record_ref") or "").strip()
    selection_ref = str(preflight_payload.get("pytest_selection_integrity_result_ref") or "").strip()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "pull_request")

    if event_name == "pull_request":
        if decision == "WARN":
            _fail_closed(
                "WARN is not pass-equivalent for pull_request",
                _GATE_NAME,
                "strategy_gate_decision=WARN",
                "Resolve WARN conditions before merging",
                [],
                "scripts/run_contract_preflight.py",
                [str(artifact_path)],
                output_dir,
            )
        if not record_ref:
            _fail_closed(
                "missing pytest_execution_record_ref",
                _GATE_NAME,
                "contract_preflight_result_artifact.json has no pytest_execution_record_ref",
                "Diagnose run_contract_preflight.py — execution record not produced",
                [],
                "scripts/run_contract_preflight.py",
                [str(artifact_path)],
                output_dir,
            )
        record_path = repo_root / record_ref
        if not record_path.is_file():
            _fail_closed(
                f"missing pytest_execution_record artifact at {record_ref}",
                _GATE_NAME,
                f"pytest_execution_record not found at {record_ref}",
                "Verify that run_contract_preflight.py wrote the execution record",
                [],
                "scripts/run_contract_preflight.py",
                [str(artifact_path)],
                output_dir,
            )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        executed = bool(record.get("executed", False))
        selected_targets = record.get("selected_targets") or []
        provenance_fields = [
            "source_commit_sha", "source_head_ref", "workflow_run_id",
            "producer_script", "produced_at", "artifact_hash",
        ]
        if decision == "ALLOW" and not executed:
            _fail_closed(
                "PR allow with executed=false",
                _GATE_NAME,
                "pytest_execution_record.executed=false",
                "Verify pytest actually ran during preflight",
                [],
                "scripts/run_contract_preflight.py",
                [record_ref],
                output_dir,
            )
        if decision == "ALLOW" and not selected_targets:
            _fail_closed(
                "PR allow with empty selected_targets",
                _GATE_NAME,
                "pytest_execution_record.selected_targets is empty",
                "Verify test selection produced at least one target",
                [],
                "scripts/run_contract_preflight.py",
                [record_ref],
                output_dir,
            )
        if any(not str(record.get(f) or "").strip() for f in provenance_fields):
            missing = [f for f in provenance_fields if not str(record.get(f) or "").strip()]
            _fail_closed(
                f"missing pytest_execution_record provenance fields: {missing}",
                _GATE_NAME,
                f"Fields missing: {missing}",
                "Ensure run_contract_preflight.py writes all provenance fields",
                [],
                "scripts/run_contract_preflight.py",
                [record_ref],
                output_dir,
            )
        if not selection_ref:
            _fail_closed(
                "missing pytest_selection_integrity_result_ref",
                _GATE_NAME,
                "contract_preflight_result_artifact has no pytest_selection_integrity_result_ref",
                "Diagnose run_contract_preflight.py — selection integrity artifact not produced",
                [],
                "scripts/run_contract_preflight.py",
                [str(artifact_path)],
                output_dir,
            )

    details["strategy_gate_decision"] = decision
    details["pytest_execution_record_ref"] = record_ref
    details["pytest_selection_integrity_result_ref"] = selection_ref

    if decision in ("BLOCK", "FREEZE"):
        _fail_closed(
            f"contract preflight decision={decision} (exit={rc})",
            _GATE_NAME,
            f"run_contract_preflight.py returned {decision} decision",
            "Review contract_preflight_result_artifact.json and contract_preflight_report.md for details",
            [],
            "scripts/run_contract_preflight.py",
            [str(artifact_path)],
            output_dir,
        )

    result = _build_result("allow", details, None)
    _write_result(result, output_dir)
    print(f"[contract_gate] ALLOW — decision={decision}")


if __name__ == "__main__":
    main()
