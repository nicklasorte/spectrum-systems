"""
Runtime Test Gate runner — Gate 3 of 4.

Executes the selected pytest targets (and optionally Jest targets) and emits a
structured gate result artifact. Fail-closed: any test failure exits non-zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import time


_GATE_NAME = "runtime_test_gate"
_SCHEMA_VERSION = "1.0.0"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_result(status: str, details: dict, failure_summary: dict | None) -> dict:
    payload: dict = {
        "artifact_type": "runtime_test_gate_result",
        "schema_version": _SCHEMA_VERSION,
        "gate_name": _GATE_NAME,
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_runtime_test_gate.py",
        **details,
    }
    if failure_summary:
        payload["failure_summary"] = failure_summary
    text = json.dumps(payload, sort_keys=True, indent=2)
    payload["artifact_hash"] = _sha256(text)
    return payload


def _write_result(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "runtime_test_gate_result.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[runtime_test_gate] result written to {out_path}")


def _fail_closed(reason: str, root_cause: str, next_action: str,
                 affected_files: list[str], failed_command: str,
                 artifact_refs: list[str], output_dir: Path,
                 extra_details: dict | None = None) -> None:
    failure_summary = {
        "gate_name": _GATE_NAME,
        "failure_class": "runtime_test_failure",
        "root_cause": root_cause,
        "blocking_reason": reason,
        "next_action": next_action,
        "affected_files": affected_files,
        "failed_command": failed_command,
        "artifact_refs": artifact_refs,
    }
    result = _build_result("block", extra_details or {}, failure_summary)
    _write_result(result, output_dir)
    print(f"[runtime_test_gate] BLOCK: {reason}", file=sys.stderr)
    sys.exit(1)


def _load_json_file(path: Path, label: str, output_dir: Path) -> dict:
    if not path.is_file():
        _fail_closed(
            f"missing required artifact: {path}",
            f"{label} not found at {path}",
            "Ensure the Test Selection Gate ran successfully before the Runtime Test Gate",
            [],
            "scripts/run_runtime_test_gate.py",
            [str(path)],
            output_dir,
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _fail_closed(
            f"invalid JSON in {path}",
            f"{label} contains invalid JSON: {e}",
            f"Fix or regenerate {path}",
            [],
            "scripts/run_runtime_test_gate.py",
            [str(path)],
            output_dir,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Runtime Test Gate runner")
    parser.add_argument("--output-dir", default="outputs/gates")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pytest-args", nargs="*", default=[])
    parser.add_argument("--skip-jest", action="store_true", default=True,
                        help="Skip Jest execution (default: true; Jest runs separately)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    repo_root = Path(args.repo_root)

    # Load selected targets from upstream gate — use output_dir so --output-dir
    # (i.e. --gates-dir from run_pr_gate.py) is respected rather than a hard-coded path
    selection_result_path = output_dir / "test_selection_gate_result.json"
    selection_result = _load_json_file(
        selection_result_path, "test_selection_gate_result", output_dir
    )

    selected_targets: list[str] = selection_result.get("selected_targets") or []
    if not selected_targets:
        _fail_closed(
            "no selected_targets in test_selection_gate_result",
            "test_selection_gate_result.selected_targets is empty",
            "Verify test_selection_gate completed successfully",
            [],
            "scripts/run_runtime_test_gate.py",
            [str(selection_result_path)],
            output_dir,
        )

    executed_commands: list[str] = []
    details: dict = {
        "selected_targets": selected_targets,
        "target_count": len(selected_targets),
        "executed_commands": executed_commands,
        "executed": False,
    }

    # Run pytest
    start = time.monotonic()
    pytest_cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + list(args.pytest_args) + selected_targets
    executed_commands.append(" ".join(pytest_cmd))

    result_proc = subprocess.run(pytest_cmd, cwd=str(repo_root), capture_output=True, text=True)
    duration = time.monotonic() - start
    details["duration_seconds"] = round(duration, 2)
    details["executed"] = True
    details["pytest_exit_code"] = result_proc.returncode

    # Parse pytest output for summary counts
    stdout = result_proc.stdout
    lines = stdout.splitlines()
    passed = failed = errors = 0
    for line in reversed(lines):
        if "passed" in line or "failed" in line or "error" in line:
            import re
            m_pass = re.search(r"(\d+) passed", line)
            m_fail = re.search(r"(\d+) failed", line)
            m_err = re.search(r"(\d+) error", line)
            if m_pass:
                passed = int(m_pass.group(1))
            if m_fail:
                failed = int(m_fail.group(1))
            if m_err:
                errors = int(m_err.group(1))
            if m_pass or m_fail or m_err:
                break

    details.update({
        "pytest_passed": passed,
        "pytest_failed": failed,
        "pytest_errors": errors,
    })

    if result_proc.returncode != 0:
        # Extract failing tests from output
        failing_tests: list[str] = []
        for line in lines:
            if "FAILED" in line and "::" in line:
                failing_tests.append(line.strip())

        _fail_closed(
            f"{failed + errors} test(s) failed (exit={result_proc.returncode})",
            "\n".join(failing_tests[:10]) or result_proc.stderr.strip()[:500] or "pytest non-zero exit",
            "Fix failing tests before this PR can be promoted",
            selected_targets,
            " ".join(pytest_cmd),
            [str(selection_result_path)],
            output_dir,
            extra_details=details,
        )

    result = _build_result("allow", details, None)
    _write_result(result, output_dir)
    print(f"[runtime_test_gate] ALLOW — passed={passed} failed={failed} errors={errors} duration={duration:.1f}s")


if __name__ == "__main__":
    main()
