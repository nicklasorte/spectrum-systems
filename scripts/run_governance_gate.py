"""
Governance Gate runner — Gate 4 of 4 (PR path).

Validates strategy compliance, system registry, review artifacts, and ecosystem
registry for paths touched by this PR. Only runs checks for paths that are
actually touched — no unnecessary full-suite invocation on every PR.

Fail-closed: any governance violation on a touched path blocks the PR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


_GATE_NAME = "governance_gate"
_SCHEMA_VERSION = "1.0.0"

_STRATEGY_PATHS = frozenset([
    "docs/roadmaps/", "docs/roadmap/", "docs/architecture/",
    "scripts/check_strategy_compliance.py",
    "contracts/schemas/roadmap_output.schema.json",
])
_REGISTRY_PATHS = frozenset([
    "docs/architecture/system_registry.md",
    "docs/governance/",
    "contracts/schemas/",
    "evals/eval_case_library.json",
    "spectrum_systems/governance/",
])
_REVIEW_PATHS = frozenset([
    "design-reviews/",
    "docs/reviews/",
])
_ECOSYSTEM_PATHS = frozenset([
    "ecosystem/ecosystem-registry.json",
    "ecosystem/ecosystem-registry.schema.json",
    "contracts/standards-manifest.json",
    "design-packages/",
])


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_result(status: str, details: dict, failure_summary: dict | None) -> dict:
    payload: dict = {
        "artifact_type": "governance_gate_result",
        "schema_version": _SCHEMA_VERSION,
        "gate_name": _GATE_NAME,
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_governance_gate.py",
        **details,
    }
    if failure_summary:
        payload["failure_summary"] = failure_summary
    text = json.dumps(payload, sort_keys=True, indent=2)
    payload["artifact_hash"] = _sha256(text)
    return payload


def _write_result(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "governance_gate_result.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[governance_gate] result written to {out_path}")


def _fail_closed(reason: str, root_cause: str, next_action: str,
                 affected_files: list[str], failed_command: str,
                 artifact_refs: list[str], output_dir: Path,
                 extra_details: dict | None = None) -> None:
    failure_summary = {
        "gate_name": _GATE_NAME,
        "failure_class": "governance_violation",
        "root_cause": root_cause,
        "blocking_reason": reason,
        "next_action": next_action,
        "affected_files": affected_files,
        "failed_command": failed_command,
        "artifact_refs": artifact_refs,
    }
    result = _build_result("block", extra_details or {}, failure_summary)
    _write_result(result, output_dir)
    print(f"[governance_gate] BLOCK: {reason}", file=sys.stderr)
    sys.exit(1)


def _get_changed_files(base_ref: str, head_ref: str, repo_root: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        capture_output=True, text=True, cwd=repo_root
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff --name-only failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def _paths_touch(changed: list[str], prefixes: frozenset[str]) -> bool:
    return any(
        any(f.startswith(p) or f == p.rstrip("/") for p in prefixes)
        for f in changed
    )


def _run(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def main() -> None:
    parser = argparse.ArgumentParser(description="Governance Gate runner")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--output-dir", default="outputs/gates")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-all", action="store_true",
                        help="Run all governance checks regardless of changed paths")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    repo_root = args.repo_root
    executed_commands: list[str] = []
    checks_run: list[str] = []
    checks_skipped: list[str] = []
    details: dict = {
        "base_ref": args.base_ref,
        "head_ref": args.head_ref,
        "executed_commands": executed_commands,
        "checks_run": checks_run,
        "checks_skipped": checks_skipped,
    }

    try:
        changed_files = _get_changed_files(args.base_ref, args.head_ref, repo_root)
    except RuntimeError as exc:
        if not args.run_all:
            _fail_closed(
                f"git diff failed — cannot determine changed files",
                str(exc),
                "Ensure base_ref and head_ref are valid, reachable commits in a full checkout",
                [],
                f"git diff --name-only {args.base_ref} {args.head_ref}",
                [],
                output_dir,
                extra_details=details,
            )
        changed_files = []
    details["changed_file_count"] = len(changed_files)

    # Strategy compliance check (path-gated)
    if args.run_all or _paths_touch(changed_files, _STRATEGY_PATHS):
        cmd = [sys.executable, "scripts/check_strategy_compliance.py"]
        executed_commands.append(" ".join(cmd))
        checks_run.append("strategy_compliance")
        rc, out, err = _run(cmd, repo_root)
        if rc != 0:
            _fail_closed(
                "strategy compliance check failed",
                err.strip() or out.strip() or "check_strategy_compliance.py non-zero exit",
                "Fix strategy compliance violations in the changed roadmap/architecture docs",
                [f for f in changed_files if any(f.startswith(p) for p in _STRATEGY_PATHS)],
                "scripts/check_strategy_compliance.py",
                [],
                output_dir,
                extra_details=details,
            )
    else:
        checks_skipped.append("strategy_compliance")

    # 3LS registry compliance check (path-gated)
    if args.run_all or _paths_touch(changed_files, _REGISTRY_PATHS):
        # Run registry drift validator inline
        cmd = [
            sys.executable, "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from spectrum_systems.governance.registry_drift_validator import main as m; m() if hasattr(m, '__call__') else None"
        ]
        # Fallback to direct script if module not available
        drift_script = Path(repo_root) / "spectrum_systems/governance/registry_drift_validator.py"
        if drift_script.is_file():
            cmd = [sys.executable, str(drift_script)]
        executed_commands.append(" ".join(cmd))
        checks_run.append("registry_drift")
        rc, out, err = _run(cmd, repo_root)
        # Only hard-fail on schema-missing violations
        if rc != 0:
            _fail_closed(
                "registry drift validation failed",
                err.strip() or out.strip(),
                "Fix missing schema contracts for systems in the registry",
                [f for f in changed_files if any(f.startswith(p) for p in _REGISTRY_PATHS)],
                "spectrum_systems/governance/registry_drift_validator.py",
                [],
                output_dir,
                extra_details=details,
            )
    else:
        checks_skipped.append("registry_drift")

    # Review artifact validation (path-gated)
    if args.run_all or _paths_touch(changed_files, _REVIEW_PATHS):
        cmd = [sys.executable, "scripts/run_review_artifact_validation.py", "--repo-root", repo_root, "--allow-full-pytest"]
        executed_commands.append(" ".join(cmd))
        checks_run.append("review_artifact_validation")
        rc, out, err = _run(cmd, repo_root)
        if rc != 0:
            _fail_closed(
                "review artifact validation failed",
                err.strip() or out.strip(),
                "Fix review artifact violations in design-reviews/",
                [f for f in changed_files if any(f.startswith(p) for p in _REVIEW_PATHS)],
                "scripts/run_review_artifact_validation.py",
                [],
                output_dir,
                extra_details=details,
            )
    else:
        checks_skipped.append("review_artifact_validation")

    # Ecosystem registry validation (path-gated)
    if args.run_all or _paths_touch(changed_files, _ECOSYSTEM_PATHS):
        cmd = [sys.executable, "scripts/validate_ecosystem_registry.py"]
        executed_commands.append(" ".join(cmd))
        checks_run.append("ecosystem_registry")
        rc, out, err = _run(cmd, repo_root)
        if rc != 0:
            _fail_closed(
                "ecosystem registry validation failed",
                err.strip() or out.strip(),
                "Fix ecosystem registry issues",
                [f for f in changed_files if any(f.startswith(p) for p in _ECOSYSTEM_PATHS)],
                "scripts/validate_ecosystem_registry.py",
                [],
                output_dir,
                extra_details=details,
            )
    else:
        checks_skipped.append("ecosystem_registry")

    details["checks_run"] = checks_run
    details["checks_skipped"] = checks_skipped

    result = _build_result("allow", details, None)
    _write_result(result, output_dir)
    print(f"[governance_gate] ALLOW — checks_run={checks_run} checks_skipped={checks_skipped}")


if __name__ == "__main__":
    main()
