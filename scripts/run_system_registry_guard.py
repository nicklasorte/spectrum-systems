#!/usr/bin/env python3
"""Run deterministic System Registry Guard (SRG) checks over changed files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.system_registry_guard import (  # noqa: E402
    SystemRegistryGuardError,
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)


def _run(command: list[str]) -> tuple[int, str]:
    proc = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip() or proc.stderr.strip()


def _ref_exists(ref: str) -> bool:
    code, _ = _run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"])
    return code == 0


def _diff_name_only(range_expr: str) -> tuple[list[str] | None, str | None]:
    code, output = _run(["git", "diff", "--name-only", range_expr])
    if code != 0:
        return None, output
    files = sorted(set(line.strip() for line in output.splitlines() if line.strip()))
    return files, None


def _resolve_changed_files(base_ref: str, head_ref: str, explicit: list[str]) -> list[str]:
    if explicit:
        return sorted(set(path.strip() for path in explicit if path.strip()))

    requested_range = f"{base_ref}..{head_ref}"
    files, error = _diff_name_only(requested_range)
    if files is not None:
        return files

    attempted_fallbacks: list[str] = [f"requested_range={requested_range} failed: {error}"]

    if _ref_exists("origin/main") and _ref_exists("HEAD"):
        fallback_range = "origin/main...HEAD"
        files, fallback_error = _diff_name_only(fallback_range)
        if files is not None:
            return files
        attempted_fallbacks.append(f"fallback_origin_main_triple_dot={fallback_range} failed: {fallback_error}")

        merge_base_code, merge_base_output = _run(["git", "merge-base", "origin/main", "HEAD"])
        if merge_base_code == 0 and merge_base_output:
            merge_base = merge_base_output.splitlines()[0].strip()
            merge_range = f"{merge_base}..HEAD"
            files, merge_error = _diff_name_only(merge_range)
            if files is not None:
                return files
            attempted_fallbacks.append(f"fallback_merge_base={merge_range} failed: {merge_error}")
        else:
            attempted_fallbacks.append(
                "fallback_merge_base=origin/main HEAD failed: "
                + (merge_base_output or "merge-base resolution failed")
            )
    else:
        attempted_fallbacks.append("fallback_origin_main_triple_dot skipped: missing origin/main or HEAD commit")
        attempted_fallbacks.append("fallback_merge_base skipped: missing origin/main or HEAD commit")

    if _ref_exists("HEAD~1"):
        head_parent_range = "HEAD~1..HEAD"
        files, head_parent_error = _diff_name_only(head_parent_range)
        if files is not None:
            return files
        attempted_fallbacks.append(f"fallback_head_parent={head_parent_range} failed: {head_parent_error}")
    else:
        attempted_fallbacks.append("fallback_head_parent skipped: missing HEAD~1 commit")

    raise SystemRegistryGuardError(
        "failed to resolve changed files; "
        f"requested_range={requested_range}; "
        "attempts=" + " | ".join(attempted_fallbacks)
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed system registry ownership guard")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--output",
        default="outputs/system_registry_guard/system_registry_guard_result.json",
        help="Output artifact path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    changed_files = _resolve_changed_files(args.base_ref, args.head_ref, list(args.changed_files or []))

    policy = load_guard_policy(REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json")
    registry = parse_system_registry(REPO_ROOT / "docs" / "architecture" / "system_registry.md")
    result = evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        policy=policy,
        registry_model=registry,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": result["status"],
                "changed_files": result["changed_files"],
                "reason_codes": result["normalized_reason_codes"],
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
