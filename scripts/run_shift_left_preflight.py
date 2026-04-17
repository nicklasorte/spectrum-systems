#!/usr/bin/env python3
"""Mandatory SLH preflight wrapper for governed execution and pytest entrypoints."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.shift_left_hardening_superlayer import (  # noqa: E402
    classify_fix,
    detect_fail_open_conditions,
    generate_shift_left_remediation_hint,
    plan_targeted_rerun,
)


CANONICAL_OUTPUT = REPO_ROOT / "outputs" / "shift_left_hardening" / "superlayer_result.json"
CANONICAL_REMEDIATION_OUTPUT = REPO_ROOT / "outputs" / "shift_left_hardening" / "remediation_hint_record.json"


def _created_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run mandatory SLH preflight before execution.")
    parser.add_argument("--output", type=Path, default=CANONICAL_OUTPUT, help="SLH output artifact path")
    parser.add_argument("--remediation-output", type=Path, default=CANONICAL_REMEDIATION_OUTPUT, help="Remediation artifact path")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--targeted-rerun", action="append", default=[], help="Targeted pytest subset required before full pytest")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute after SLH pass. Prefix with --")
    return parser.parse_args()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_targeted_rerun(targets: list[str]) -> tuple[bool, str]:
    if not targets:
        return True, ""
    command = [sys.executable, "-m", "pytest", "-q", *targets]
    proc = _run(command)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "targeted rerun failed").strip()
    return True, ""


def main() -> int:
    args = _parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.remediation_output.parent.mkdir(parents=True, exist_ok=True)

    slh_cmd = [
        sys.executable,
        "scripts/run_shift_left_hardening_superlayer.py",
        "--output",
        str(args.output),
        "--base-ref",
        args.base_ref,
        "--head-ref",
        args.head_ref,
    ]
    if args.changed_file:
        slh_cmd.extend(["--changed-files", *args.changed_file])

    slh_proc = _run(slh_cmd)
    if slh_proc.returncode not in {0, 1}:
        print(slh_proc.stderr or slh_proc.stdout, file=sys.stderr)
        return 2
    if not args.output.is_file():
        print("SLH preflight failed: missing superlayer output artifact", file=sys.stderr)
        return 2

    slh_payload = _load_json(args.output)
    mini_cert = slh_payload.get("mini_certification_decision", {})
    checks = {
        "sl_core": slh_payload.get("shift_left_guard_chain", {}),
        "eval": slh_payload.get("eval_completeness", {}),
        "replay": slh_payload.get("replay_integrity", {}),
        "lineage": slh_payload.get("lineage_integrity", {}),
        "observability": slh_payload.get("observability_completeness", {}),
        "hidden_state": slh_payload.get("hidden_state_detection", {}),
    }
    fail_open_findings = detect_fail_open_conditions(checks=checks)

    if mini_cert.get("status") != "pass" or fail_open_findings:
        reason_codes = [str(code) for code in mini_cert.get("reason_codes", [])] + fail_open_findings
        failure_hint = "runtime"
        for candidate in ("lineage", "observability", "taxonomy", "registry", "control", "dependency_graph"):
            if any(candidate in code for code in reason_codes):
                failure_hint = candidate
                break
        remediation = generate_shift_left_remediation_hint(
            failure_class=failure_hint,
            reason_codes=reason_codes,
            impacted_files=[str(path) for path in slh_payload.get("repo_derived_signals", {}).get("changed_files", [])],
            created_at=_created_at(),
        )
        args.remediation_output.write_text(json.dumps(remediation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "blocked", "reason_codes": reason_codes, "remediation_ref": str(args.remediation_output)}, indent=2))
        return 1

    command = [token for token in args.command if token != "--"]
    if command and command[0] == "pytest":
        classified = classify_fix(failure_signature="runtime.parity", created_at=_created_at())
        rerun_plan = plan_targeted_rerun(fix_class=str(classified.get("fix_class") or "runtime_fix"), created_at=_created_at())
        if not args.targeted_rerun:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "full pytest blocked until targeted rerun subset is declared and passes",
                        "required_targeted_rerun": rerun_plan.get("rerun_steps", []),
                    },
                    indent=2,
                )
            )
            return 1
        ok, err = _ensure_targeted_rerun(args.targeted_rerun)
        if not ok:
            print(json.dumps({"status": "blocked", "reason": "targeted rerun failed", "details": err}, indent=2))
            return 1

    if not command:
        print(json.dumps({"status": "pass", "slh_preflight": "passed", "output": str(args.output)}, indent=2))
        return 0

    proc = _run(command)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
