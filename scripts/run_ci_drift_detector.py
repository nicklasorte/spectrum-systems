#!/usr/bin/env python3
"""CI drift detector: check for mapping/integration gaps in the PR test
selection pipeline.

Produces a ci_drift_detection_result artifact.
Authority scope: observation_only.

Fail-closed: any exception → exit 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pr_test_selection import (  # noqa: E402
    assign_to_shard,
    SHARD_NAMES,
)

_DEFAULT_SHARD_POLICY_PATH = str(REPO_ROOT / "docs" / "governance" / "shard_policy.json")
_DEFAULT_OUTPUT = str(REPO_ROOT / "outputs" / "ci_drift" / "drift_detection_result.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect CI mapping/integration drift in the PR test selection pipeline.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help=f"Repository root path (default: auto-detected as {REPO_ROOT}).",
    )
    parser.add_argument(
        "--shard-policy-path",
        default=_DEFAULT_SHARD_POLICY_PATH,
        help=f"Path to shard policy JSON (default: {_DEFAULT_SHARD_POLICY_PATH}).",
    )
    parser.add_argument(
        "--output",
        default=_DEFAULT_OUTPUT,
        help=f"Path for the drift detection result JSON (default: {_DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


def _load_shard_policy(path: Path) -> dict[str, Any]:
    """Return parsed shard policy or empty dict if absent/unreadable."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _check_unmapped_test_files(
    repo_root: Path,
    shard_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Check 1: unmapped_test_files.

    Scan tests/test_*.py — flag files where no shard matches and the test
    is in a governed test directory.  Severity: warning.
    """
    findings: list[dict[str, Any]] = []
    tests_root = repo_root / "tests"
    if not tests_root.is_dir():
        return findings

    # Build governed test dir set from policy (if provided).
    governed_test_dirs: set[str] = set(
        shard_policy.get("governed_test_dirs", ["tests/"])
    )

    for test_file in sorted(tests_root.rglob("test_*.py")):
        rel_path = test_file.relative_to(repo_root).as_posix()
        assigned = assign_to_shard(rel_path)
        if assigned is not None:
            # At least one shard claims this file.
            continue
        # Check whether the file is in a governed test directory.
        in_governed_dir = any(rel_path.startswith(d) for d in governed_test_dirs)
        if in_governed_dir:
            findings.append(
                {
                    "check": "unmapped_test_files",
                    "severity": "warn",
                    "detail": (
                        f"Test file '{rel_path}' is in a governed test directory "
                        "but no shard pattern matches it.  Add a shard pattern or "
                        "an explicit override mapping."
                    ),
                }
            )
    return findings


def _check_new_governed_surface_without_test_mapping(
    repo_root: Path,
    shard_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Check 2: new_governed_surface_without_test_mapping.

    For each governed path that exists on disk but has no entry in the
    override map or shard patterns, report as a warning finding.
    """
    findings: list[dict[str, Any]] = []

    # Load the merged override map.
    try:
        from spectrum_systems.modules.runtime.pr_test_selection import load_override_map  # noqa: E402
        override_map = load_override_map(repo_root)
    except Exception:  # noqa: BLE001
        override_map = {}

    # Governed path prefixes from the canonical module.
    from spectrum_systems.modules.runtime.pr_test_selection import GOVERNED_PATH_PREFIXES  # noqa: E402

    # Walk governed directories looking for Python source files.
    governed_source_dirs = [
        d for d in GOVERNED_PATH_PREFIXES
        if not d.startswith(".") and not d.startswith("docs/")
    ]

    checked_paths: set[str] = set()
    for gov_prefix in governed_source_dirs:
        gov_dir = repo_root / gov_prefix.rstrip("/")
        if not gov_dir.is_dir():
            continue
        for src_file in sorted(gov_dir.rglob("*.py")):
            if src_file.name.startswith("test_"):
                continue
            rel_path = src_file.relative_to(repo_root).as_posix()
            if rel_path in checked_paths:
                continue
            checked_paths.add(rel_path)
            if rel_path in override_map:
                continue
            # Check if any shard pattern matches.
            from spectrum_systems.modules.runtime.pr_test_selection import SHARD_PATH_PATTERNS  # noqa: E402
            matched = False
            for patterns in SHARD_PATH_PATTERNS.values():
                if any(p in rel_path for p in patterns):
                    matched = True
                    break
            if not matched:
                findings.append(
                    {
                        "check": "new_governed_surface_without_test_mapping",
                        "severity": "warn",
                        "detail": (
                            f"Governed source file '{rel_path}' has no explicit test "
                            "override mapping and no shard pattern matches it.  "
                            "Add an entry to preflight_required_surface_test_overrides.json "
                            "or a shard pattern in pr_test_selection.py."
                        ),
                    }
                )

    return findings


def _check_missing_shard_result_schema(repo_root: Path) -> list[dict[str, Any]]:
    """Check 3: missing_shard_result_schema."""
    schema_path = repo_root / "contracts" / "schemas" / "pr_test_shard_result.schema.json"
    if not schema_path.is_file():
        return [
            {
                "check": "missing_shard_result_schema",
                "severity": "block",
                "detail": (
                    f"Schema file '{schema_path.relative_to(repo_root).as_posix()}' is missing.  "
                    "Create contracts/schemas/pr_test_shard_result.schema.json."
                ),
            }
        ]
    return []


def _check_missing_shard_result_example(repo_root: Path) -> list[dict[str, Any]]:
    """Check 4: missing_shard_result_example."""
    example_path = repo_root / "contracts" / "examples" / "pr_test_shard_result.example.json"
    if not example_path.is_file():
        return [
            {
                "check": "missing_shard_result_example",
                "severity": "block",
                "detail": (
                    f"Example artifact '{example_path.relative_to(repo_root).as_posix()}' is missing.  "
                    "Create contracts/examples/pr_test_shard_result.example.json."
                ),
            }
        ]
    return []


def _check_workflow_bypasses_canonical_selector(repo_root: Path) -> list[dict[str, Any]]:
    """Check 5: workflow_bypasses_canonical_selector.

    Verify that .github/workflows/pr-pytest.yml references one of the
    canonical shard runner / selector wrapper paths. Either of these is
    accepted because both share the canonical selector module
    ``spectrum_systems.modules.runtime.pr_test_selection``:

    * ``scripts/run_pr_test_shards.py`` — canonical PAR-BATCH-01 shard
      runner. Preferred, and used by APR.
    * ``scripts/select_pr_test_shard.py`` — legacy single-shard selector
      wrapper (still tested directly).
    """
    workflow_path = repo_root / ".github" / "workflows" / "pr-pytest.yml"
    if not workflow_path.is_file():
        return [
            {
                "check": "workflow_bypasses_canonical_selector",
                "severity": "warn",
                "detail": (
                    ".github/workflows/pr-pytest.yml does not exist; "
                    "cannot verify canonical shard selector reference."
                ),
            }
        ]
    try:
        content = workflow_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            {
                "check": "workflow_bypasses_canonical_selector",
                "severity": "warn",
                "detail": f"Could not read pr-pytest.yml: {exc}",
            }
        ]
    if (
        "scripts/run_pr_test_shards.py" not in content
        and "scripts/select_pr_test_shard.py" not in content
    ):
        return [
            {
                "check": "workflow_bypasses_canonical_selector",
                "severity": "warn",
                "detail": (
                    ".github/workflows/pr-pytest.yml does not reference any "
                    "canonical shard runner / selector wrapper "
                    "('scripts/run_pr_test_shards.py' or "
                    "'scripts/select_pr_test_shard.py').  The workflow must "
                    "invoke the canonical selector so that shard selection "
                    "is governed."
                ),
            }
        ]
    return []


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    shard_policy_path = Path(args.shard_policy_path)
    output_path = Path(args.output)

    shard_policy = _load_shard_policy(shard_policy_path)

    findings: list[dict[str, Any]] = []
    findings.extend(_check_unmapped_test_files(repo_root, shard_policy))
    findings.extend(_check_new_governed_surface_without_test_mapping(repo_root, shard_policy))
    findings.extend(_check_missing_shard_result_schema(repo_root))
    findings.extend(_check_missing_shard_result_example(repo_root))
    findings.extend(_check_workflow_bypasses_canonical_selector(repo_root))

    has_block = any(f["severity"] == "block" for f in findings)
    has_warn = any(f["severity"] == "warn" for f in findings)

    if has_block:
        status = "block"
    elif has_warn:
        status = "warn"
    else:
        status = "pass"

    artifact: dict[str, Any] = {
        "artifact_type": "ci_drift_detection_result",
        "schema_version": "1.0.0",
        "status": status,
        "findings": findings,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "authority_scope": "observation_only",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    if has_block:
        block_findings = [f for f in findings if f["severity"] == "block"]
        print(
            f"[run_ci_drift_detector] BLOCK {len(block_findings)} block finding(s):",
            file=sys.stderr,
        )
        for f in block_findings:
            print(f"  [{f['check']}] {f['detail']}", file=sys.stderr)
        return 1

    if has_warn:
        warn_findings = [f for f in findings if f["severity"] == "warn"]
        print(
            f"[run_ci_drift_detector] WARN {len(warn_findings)} warning(s); "
            f"no block findings → {output_path}"
        )
    else:
        print(f"[run_ci_drift_detector] PASS no findings → {output_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[run_ci_drift_detector] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
