"""
PR Gate Orchestrator — thin coordinator for the four canonical gates.

Calls gates in order, collects result artifacts, emits one final artifact.
This script contains NO policy decisions, NO schema shortcuts, NO test selection
logic, and NO certification logic. It is a thin sequencer only.

Gate order:
  1. Contract Gate     → scripts/run_contract_gate.py
  2. Test Selection Gate → scripts/run_test_selection_gate.py
  3. Runtime Test Gate → scripts/run_runtime_test_gate.py
  4. Governance Gate   → scripts/run_governance_gate.py
  5. Certification Gate (fast, only when cert paths touched) → scripts/run_certification_gate.py

Final artifact: outputs/pr_gate/pr_gate_result.json
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


_SCHEMA_VERSION = "1.0.0"
_OUTPUT_DIR = "outputs/pr_gate"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_gate_result(path: Path) -> dict:
    if not path.is_file():
        return {"status": "missing", "error": f"gate result not found at {path}"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json", "error": f"invalid JSON at {path}"}


def _run_gate(
    label: str,
    cmd: list[str],
    repo_root: str,
    gate_result_path: Path,
    executed_commands: list[str],
    gate_results: dict,
    env: dict | None = None,
) -> bool:
    print(f"\n[pr_gate] ── {label} ──────────────────────")
    executed_commands.append(" ".join(cmd))
    result = subprocess.run(cmd, cwd=repo_root, env=env or os.environ.copy())
    gate_result = _load_gate_result(gate_result_path)
    gate_results[label] = gate_result
    if result.returncode != 0:
        status = gate_result.get("status", "unknown")
        print(f"[pr_gate] {label} FAILED (exit={result.returncode}, status={status})", file=sys.stderr)
        return False
    print(f"[pr_gate] {label} passed")
    return True


def _emit_final_result(
    status: str,
    gate_results: dict,
    executed_commands: list[str],
    blocking_gate: str | None,
    failure_summary: dict | None,
    output_dir: Path,
    base_ref: str,
    head_ref: str,
) -> dict:
    payload: dict = {
        "artifact_type": "pr_gate_result",
        "schema_version": _SCHEMA_VERSION,
        "gate_name": "pr_gate",
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_pr_gate.py",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "gate_results": gate_results,
        "executed_commands": executed_commands,
    }
    if blocking_gate:
        payload["blocking_gate"] = blocking_gate
    if failure_summary:
        payload["failure_summary"] = failure_summary
    text = json.dumps(payload, sort_keys=True, indent=2)
    payload["artifact_hash"] = _sha256(text)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "pr_gate_result.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\n[pr_gate] final result written to {out_path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="PR Gate Orchestrator")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--output-dir", default=_OUTPUT_DIR)
    parser.add_argument("--gates-dir", default="outputs/gates")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--execution-context", default="pqx_governed")
    parser.add_argument("--event-name", default="pull_request")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    gates_dir = Path(args.gates_dir)
    repo_root = args.repo_root
    executed_commands: list[str] = []
    gate_results: dict = {}

    env = {
        **os.environ,
        "GITHUB_EVENT_NAME": args.event_name,
    }

    print(f"[pr_gate] Starting PR gate — base={args.base_ref} head={args.head_ref}")

    # Gate 1: Contract Gate
    ok = _run_gate(
        "contract_gate",
        [
            sys.executable, "scripts/run_contract_gate.py",
            "--base-ref", args.base_ref,
            "--head-ref", args.head_ref,
            "--output-dir", str(gates_dir),
            "--repo-root", repo_root,
            "--execution-context", args.execution_context,
        ],
        repo_root,
        gates_dir / "contract_gate_result.json",
        executed_commands,
        gate_results,
        env=env,
    )
    if not ok:
        _emit_final_result(
            "block", gate_results, executed_commands, "contract_gate",
            {
                "gate_name": "pr_gate",
                "failure_class": "gate_failure",
                "root_cause": "Contract Gate failed",
                "blocking_reason": "contract_gate returned non-zero",
                "next_action": "Review contract_gate_result.json for details",
                "affected_files": [],
                "failed_command": "scripts/run_contract_gate.py",
                "artifact_refs": [str(gates_dir / "contract_gate_result.json")],
            },
            output_dir, args.base_ref, args.head_ref,
        )
        sys.exit(1)

    # Gate 2: Test Selection Gate
    ok = _run_gate(
        "test_selection_gate",
        [
            sys.executable, "scripts/run_test_selection_gate.py",
            "--output-dir", str(gates_dir),
            "--repo-root", repo_root,
            "--event-name", args.event_name,
        ],
        repo_root,
        gates_dir / "test_selection_gate_result.json",
        executed_commands,
        gate_results,
    )
    if not ok:
        _emit_final_result(
            "block", gate_results, executed_commands, "test_selection_gate",
            {
                "gate_name": "pr_gate",
                "failure_class": "gate_failure",
                "root_cause": "Test Selection Gate failed",
                "blocking_reason": "test_selection_gate returned non-zero",
                "next_action": "Review test_selection_gate_result.json for details",
                "affected_files": [],
                "failed_command": "scripts/run_test_selection_gate.py",
                "artifact_refs": [str(gates_dir / "test_selection_gate_result.json")],
            },
            output_dir, args.base_ref, args.head_ref,
        )
        sys.exit(1)

    # Gate 3: Runtime Test Gate
    ok = _run_gate(
        "runtime_test_gate",
        [
            sys.executable, "scripts/run_runtime_test_gate.py",
            "--output-dir", str(gates_dir),
            "--repo-root", repo_root,
        ],
        repo_root,
        gates_dir / "runtime_test_gate_result.json",
        executed_commands,
        gate_results,
    )
    if not ok:
        _emit_final_result(
            "block", gate_results, executed_commands, "runtime_test_gate",
            {
                "gate_name": "pr_gate",
                "failure_class": "gate_failure",
                "root_cause": "Runtime Test Gate failed",
                "blocking_reason": "runtime_test_gate returned non-zero",
                "next_action": "Review runtime_test_gate_result.json and fix failing tests",
                "affected_files": [],
                "failed_command": "scripts/run_runtime_test_gate.py",
                "artifact_refs": [str(gates_dir / "runtime_test_gate_result.json")],
            },
            output_dir, args.base_ref, args.head_ref,
        )
        sys.exit(1)

    # Gate 4: Governance Gate
    ok = _run_gate(
        "governance_gate",
        [
            sys.executable, "scripts/run_governance_gate.py",
            "--base-ref", args.base_ref,
            "--head-ref", args.head_ref,
            "--output-dir", str(gates_dir),
            "--repo-root", repo_root,
        ],
        repo_root,
        gates_dir / "governance_gate_result.json",
        executed_commands,
        gate_results,
    )
    if not ok:
        _emit_final_result(
            "block", gate_results, executed_commands, "governance_gate",
            {
                "gate_name": "pr_gate",
                "failure_class": "gate_failure",
                "root_cause": "Governance Gate failed",
                "blocking_reason": "governance_gate returned non-zero",
                "next_action": "Review governance_gate_result.json for governance violations",
                "affected_files": [],
                "failed_command": "scripts/run_governance_gate.py",
                "artifact_refs": [str(gates_dir / "governance_gate_result.json")],
            },
            output_dir, args.base_ref, args.head_ref,
        )
        sys.exit(1)

    # Gate 5: Certification Gate (fast mode — only if cert paths touched)
    ok = _run_gate(
        "certification_gate",
        [
            sys.executable, "scripts/run_certification_gate.py",
            "--base-ref", args.base_ref,
            "--head-ref", args.head_ref,
            "--output-dir", str(gates_dir),
            "--repo-root", repo_root,
            "--mode", "fast",
        ],
        repo_root,
        gates_dir / "certification_gate_result.json",
        executed_commands,
        gate_results,
    )
    if not ok:
        _emit_final_result(
            "block", gate_results, executed_commands, "certification_gate",
            {
                "gate_name": "pr_gate",
                "failure_class": "gate_failure",
                "root_cause": "Certification Gate failed",
                "blocking_reason": "certification_gate returned non-zero",
                "next_action": "Review certification_gate_result.json for certification failures",
                "affected_files": [],
                "failed_command": "scripts/run_certification_gate.py",
                "artifact_refs": [str(gates_dir / "certification_gate_result.json")],
            },
            output_dir, args.base_ref, args.head_ref,
        )
        sys.exit(1)

    # All gates passed
    result = _emit_final_result(
        "allow", gate_results, executed_commands, None, None,
        output_dir, args.base_ref, args.head_ref,
    )
    print(f"\n[pr_gate] ✓ ALL GATES PASSED — PR is admissible")


if __name__ == "__main__":
    main()
