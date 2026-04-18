from __future__ import annotations

"""Canonical changed-file resolution for CI-facing governance guards.

Fallback order is deterministic and shared across migrated scripts:
1. Explicit CLI changed files (passthrough, normalized + deduplicated).
2. Requested git diff range: ``<base_ref>..<head_ref>``.
3. ``origin/main...HEAD`` when both commits are locally resolvable.
4. ``merge-base(origin/main, HEAD)..HEAD`` when merge-base resolves.
5. ``HEAD~1..HEAD`` when parent commit exists (shallow/rebased fallback).

If every step fails, resolution raises ``ChangedFilesResolutionError`` with
attempt details so callers can fail closed with actionable diagnostics.
Working-tree-only inspection is intentionally rejected because governance
guards require a trustworthy commit-range change set.
"""

import subprocess
from pathlib import Path


class ChangedFilesResolutionError(ValueError):
    """Raised when changed-file resolution cannot complete deterministically."""


def _run(command: list[str], *, repo_root: Path) -> tuple[int, str]:
    proc = subprocess.run(command, cwd=repo_root, check=False, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip() or proc.stderr.strip()


def _normalize(paths: list[str]) -> list[str]:
    return sorted({path.strip() for path in paths if path and path.strip()})


def _ref_exists(ref: str, *, repo_root: Path, runner: callable) -> bool:
    code, _ = runner(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], repo_root=repo_root)
    return code == 0


def _diff_name_only(range_expr: str, *, repo_root: Path, runner: callable) -> tuple[list[str] | None, str | None]:
    code, output = runner(["git", "diff", "--name-only", range_expr], repo_root=repo_root)
    if code != 0:
        return None, output
    return _normalize(output.splitlines()), None


def resolve_changed_files(
    *,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    explicit_changed_files: list[str],
    runner=None,
) -> list[str]:
    """Resolve changed files using a single fail-closed fallback policy."""
    active_runner = runner or _run

    explicit = _normalize(explicit_changed_files)
    if explicit:
        return explicit

    requested_range = f"{base_ref}..{head_ref}"
    files, error = _diff_name_only(requested_range, repo_root=repo_root, runner=active_runner)
    if files is not None:
        return files

    attempted_fallbacks: list[str] = [f"requested_range={requested_range} failed: {error}"]

    if _ref_exists("origin/main", repo_root=repo_root, runner=active_runner) and _ref_exists(
        "HEAD", repo_root=repo_root, runner=active_runner
    ):
        triple_dot_range = "origin/main...HEAD"
        files, triple_dot_error = _diff_name_only(triple_dot_range, repo_root=repo_root, runner=active_runner)
        if files is not None:
            return files
        attempted_fallbacks.append(
            f"fallback_origin_main_triple_dot={triple_dot_range} failed: {triple_dot_error}"
        )

        merge_base_code, merge_base_output = active_runner(
            ["git", "merge-base", "origin/main", "HEAD"], repo_root=repo_root
        )
        if merge_base_code == 0 and merge_base_output:
            merge_base = merge_base_output.splitlines()[0].strip()
            merge_range = f"{merge_base}..HEAD"
            files, merge_error = _diff_name_only(merge_range, repo_root=repo_root, runner=active_runner)
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

    if _ref_exists("HEAD~1", repo_root=repo_root, runner=active_runner):
        head_parent_range = "HEAD~1..HEAD"
        files, head_parent_error = _diff_name_only(head_parent_range, repo_root=repo_root, runner=active_runner)
        if files is not None:
            return files
        attempted_fallbacks.append(f"fallback_head_parent={head_parent_range} failed: {head_parent_error}")
    else:
        attempted_fallbacks.append("fallback_head_parent skipped: missing HEAD~1 commit")

    raise ChangedFilesResolutionError(
        "failed to resolve changed files; "
        f"requested_range={requested_range}; "
        "attempts=" + " | ".join(attempted_fallbacks)
    )
