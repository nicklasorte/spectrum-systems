"""
Certification Gate runner — Gate 5 (nightly/release, fast PR mode for cert-relevant paths).

Runs SEL replay, eval CI, governed failure injection, lineage validation, and
promotion readiness checks.

PR fast mode: runs smoke subset when cert-relevant paths are touched.
Nightly/deep mode: runs full certification suite.

Fail-closed: any certification failure blocks promotion.
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
import shutil


_GATE_NAME = "certification_gate"
_SCHEMA_VERSION = "1.0.0"

_CERT_RELEVANT_PATHS = frozenset([
    "spectrum_systems/modules/enforcement/",
    "spectrum_systems/modules/runtime/",
    "spectrum_systems/modules/evaluation/",
    "scripts/run_sel_",
    "scripts/run_eval_",
    "scripts/run_governed_failure",
    "contracts/examples/",
    "data/policy/eval_",
])


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_result(status: str, details: dict, failure_summary: dict | None) -> dict:
    payload: dict = {
        "artifact_type": "certification_gate_result",
        "schema_version": _SCHEMA_VERSION,
        "gate_name": _GATE_NAME,
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_certification_gate.py",
        **details,
    }
    if failure_summary:
        payload["failure_summary"] = failure_summary
    text = json.dumps(payload, sort_keys=True, indent=2)
    payload["artifact_hash"] = _sha256(text)
    return payload


def _write_result(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "certification_gate_result.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[certification_gate] result written to {out_path}")


def _fail_closed(reason: str, root_cause: str, next_action: str,
                 affected_files: list[str], failed_command: str,
                 artifact_refs: list[str], output_dir: Path,
                 extra_details: dict | None = None) -> None:
    failure_summary = {
        "gate_name": _GATE_NAME,
        "failure_class": "certification_failure",
        "root_cause": root_cause,
        "blocking_reason": reason,
        "next_action": next_action,
        "affected_files": affected_files,
        "failed_command": failed_command,
        "artifact_refs": artifact_refs,
    }
    result = _build_result("block", extra_details or {}, failure_summary)
    _write_result(result, output_dir)
    print(f"[certification_gate] BLOCK: {reason}", file=sys.stderr)
    sys.exit(1)


def _run(cmd: list[str], cwd: str, env: dict | None = None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    return result.returncode, result.stdout, result.stderr


def _get_changed_files(base_ref: str, head_ref: str, repo_root: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, head_ref],
            capture_output=True, text=True, cwd=repo_root
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        pass
    return []


def _paths_touch_cert(changed: list[str]) -> bool:
    return any(
        any(f.startswith(p) for p in _CERT_RELEVANT_PATHS)
        for f in changed
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Certification Gate runner")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--output-dir", default="outputs/gates")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mode", choices=["fast", "deep"], default="fast",
                        help="fast=PR smoke subset, deep=full nightly certification")
    parser.add_argument("--force", action="store_true",
                        help="Force gate to run even if cert-relevant paths not touched")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    repo_root = args.repo_root
    executed_commands: list[str] = []
    checks_run: list[str] = []
    details: dict = {
        "mode": args.mode,
        "base_ref": args.base_ref,
        "head_ref": args.head_ref,
        "executed_commands": executed_commands,
        "checks_run": checks_run,
    }

    # Check if cert-relevant paths are touched
    changed_files: list[str] = []
    if args.base_ref and args.head_ref:
        changed_files = _get_changed_files(args.base_ref, args.head_ref, repo_root)

    cert_paths_touched = args.force or args.mode == "deep" or _paths_touch_cert(changed_files)

    if not cert_paths_touched:
        details["skipped_reason"] = "no_cert_relevant_paths_touched"
        result = _build_result("allow", details, None)
        _write_result(result, output_dir)
        print("[certification_gate] ALLOW (skipped — no cert-relevant paths touched)")
        return

    # Eval CI gate
    eval_ci_out = Path(repo_root) / "outputs/eval_ci_gate"
    eval_ci_out.mkdir(parents=True, exist_ok=True)
    fixtures_dir = eval_ci_out / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    eval_case_src = Path(repo_root) / "contracts/examples/eval_case.json"
    eval_run_src = Path(repo_root) / "contracts/examples/eval_run.json"
    if not eval_case_src.is_file() or not eval_run_src.is_file():
        _fail_closed(
            "missing eval example fixtures",
            f"contracts/examples/eval_case.json or eval_run.json not found",
            "Ensure contracts/examples/ contains eval_case.json and eval_run.json",
            ["contracts/examples/eval_case.json", "contracts/examples/eval_run.json"],
            "scripts/run_certification_gate.py",
            [],
            output_dir,
            extra_details=details,
        )

    eval_case = json.loads(eval_case_src.read_text(encoding="utf-8"))
    eval_run = json.loads(eval_run_src.read_text(encoding="utf-8"))
    eval_run["eval_case_ids"] = [str(eval_case["eval_case_id"])]
    (fixtures_dir / "eval_run.json").write_text(json.dumps(eval_run, indent=2) + "\n", encoding="utf-8")
    (fixtures_dir / "eval_cases.json").write_text(json.dumps([eval_case], indent=2) + "\n", encoding="utf-8")

    cmd = [
        sys.executable, "scripts/run_eval_ci_gate.py",
        "--eval-run", str(fixtures_dir / "eval_run.json"),
        "--eval-cases", str(fixtures_dir / "eval_cases.json"),
        "--output-dir", str(eval_ci_out),
    ]
    executed_commands.append(" ".join(cmd))
    checks_run.append("eval_ci_gate")
    rc, out, err = _run(cmd, repo_root)
    if rc != 0:
        _fail_closed(
            "eval CI gate failed",
            err.strip() or out.strip() or "run_eval_ci_gate.py non-zero exit",
            "Fix eval CI gate failures — check outputs/eval_ci_gate/",
            [],
            "scripts/run_eval_ci_gate.py",
            [str(eval_ci_out)],
            output_dir,
            extra_details=details,
        )

    # SEL replay gate
    sel_out = Path(repo_root) / "outputs/sel_replay_gate"
    cde_bundle_dir = sel_out / "cde_bundle"
    sel_output_dir = sel_out / "sel_output"
    cde_bundle_dir.mkdir(parents=True, exist_ok=True)
    sel_output_dir.mkdir(parents=True, exist_ok=True)

    for fname in ["continuation_decision_record.json", "decision_bundle.json", "decision_evidence_pack.json"]:
        src = Path(repo_root) / f"contracts/examples/{fname}"
        if src.is_file():
            shutil.copy(src, cde_bundle_dir / fname)

    cmd = [
        sys.executable, "scripts/run_sel_orchestration.py",
        "--cde-bundle-dir", str(cde_bundle_dir),
        "--output-dir", str(sel_output_dir),
    ]
    executed_commands.append(" ".join(cmd))
    checks_run.append("sel_orchestration")
    rc, out, err = _run(cmd, repo_root)
    if rc != 0:
        _fail_closed(
            "SEL orchestration failed",
            err.strip() or out.strip(),
            "Fix SEL orchestration failures",
            [],
            "scripts/run_sel_orchestration.py",
            [str(sel_output_dir)],
            output_dir,
            extra_details=details,
        )

    decision_record = cde_bundle_dir / "continuation_decision_record.json"
    action_record = sel_output_dir / "enforcement_action_record.json"
    cmd = [
        sys.executable, "scripts/run_sel_replay_gate.py",
        "--output-dir", str(sel_output_dir),
        "--decision-record", str(decision_record),
        "--action-record", str(action_record),
    ]
    executed_commands.append(" ".join(cmd))
    checks_run.append("sel_replay_gate")
    rc, out, err = _run(cmd, repo_root)
    if rc != 0:
        _fail_closed(
            "SEL replay gate failed",
            err.strip() or out.strip(),
            "Fix SEL replay mismatch — decision record and action record are inconsistent",
            [],
            "scripts/run_sel_replay_gate.py",
            [str(sel_output_dir)],
            output_dir,
            extra_details=details,
        )

    # Governed failure injection (fast mode: basic; deep mode: full)
    failure_inj_out = Path(repo_root) / "outputs/governed_failure_injection"
    failure_inj_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "scripts/run_governed_failure_injection.py",
        "--output-dir", str(failure_inj_out),
    ]
    executed_commands.append(" ".join(cmd))
    checks_run.append("governed_failure_injection")
    rc, out, err = _run(cmd, repo_root)
    if rc != 0:
        _fail_closed(
            "governed failure injection gate failed",
            err.strip() or out.strip(),
            "Fix governed failure injection test failures",
            [],
            "scripts/run_governed_failure_injection.py",
            [str(failure_inj_out)],
            output_dir,
            extra_details=details,
        )

    # Deep mode only: lineage validation + promotion readiness
    if args.mode == "deep":
        cmd = [sys.executable, "scripts/run_lineage_validation.py"]
        executed_commands.append(" ".join(cmd))
        checks_run.append("lineage_validation")
        rc, out, err = _run(cmd, repo_root)
        if rc != 0:
            _fail_closed(
                "lineage validation failed",
                err.strip() or out.strip(),
                "Fix lineage chain violations",
                [],
                "scripts/run_lineage_validation.py",
                [],
                output_dir,
                extra_details=details,
            )

        cmd = [sys.executable, "scripts/run_done_certification.py"]
        executed_commands.append(" ".join(cmd))
        checks_run.append("done_certification")
        rc, out, err = _run(cmd, repo_root)
        if rc != 0:
            _fail_closed(
                "done certification check failed",
                err.strip() or out.strip(),
                "Fix done_certification_record issues",
                [],
                "scripts/run_done_certification.py",
                [],
                output_dir,
                extra_details=details,
            )

    details["checks_run"] = checks_run
    result = _build_result("allow", details, None)
    _write_result(result, output_dir)
    print(f"[certification_gate] ALLOW (mode={args.mode}) — checks={checks_run}")


if __name__ == "__main__":
    main()
