"""Canonical changed-path resolution for governed preflight execution.

Deterministic ladder:
1. exact diff (base..head)
2. fetched diff (base..HEAD when explicit head is unavailable)
3. degraded mode (local working tree)
4. insufficient context -> block
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChangedPathResolutionResult:
    changed_paths: list[str]
    changed_path_detection_mode: str
    refs_attempted: list[str]
    fallback_used: bool
    warnings: list[str]
    trust_level: str
    resolution_mode: str
    bounded_runtime: bool
    insufficient_context: bool


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


def _run(command: list[str], cwd: Path) -> CommandResult:
    proc = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    return CommandResult(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _diff_name_only(repo_root: Path, base_ref: str, head_ref: str) -> tuple[list[str], str | None]:
    result = _run(["git", "diff", "--name-only", f"{base_ref}..{head_ref}"], cwd=repo_root)
    if result.returncode != 0:
        return [], result.combined_output
    paths = sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})
    return paths, None


def _ref_exists(repo_root: Path, ref: str) -> bool:
    if not ref or ref == "HEAD":
        return True
    probe = _run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], cwd=repo_root)
    return probe.returncode == 0


def _fetch_ref(repo_root: Path, ref: str) -> bool:
    if not ref or ref == "HEAD":
        return True
    if _ref_exists(repo_root, ref):
        return True

    direct_fetch = _run(["git", "fetch", "--no-tags", "--depth=1", "origin", ref], cwd=repo_root)
    if direct_fetch.returncode == 0 and _ref_exists(repo_root, ref):
        return True

    # Some providers reject direct object-id fetches in shallow checkouts.
    # Perform a bounded-history broad fetch before failing closed.
    _run(["git", "fetch", "--no-tags", "--depth=2000", "origin"], cwd=repo_root)
    return _ref_exists(repo_root, ref)


def _try_diff_with_ref_fetch(
    *,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    refs_attempted: list[str],
    warnings: list[str],
) -> tuple[list[str] | None, str | None]:
    refs_attempted.append(f"{base_ref}..{head_ref}")
    exact_paths, exact_error = _diff_name_only(repo_root, base_ref, head_ref)
    if not exact_error:
        return exact_paths, "base_head_diff"

    warnings.append(f"base/head diff unavailable: {exact_error}")
    fetched_base = _fetch_ref(repo_root, base_ref)
    fetched_head = _fetch_ref(repo_root, head_ref)
    if fetched_base and fetched_head:
        refs_attempted.append(f"{base_ref}..{head_ref} (post_fetch)")
        retried_paths, retry_error = _diff_name_only(repo_root, base_ref, head_ref)
        if not retry_error:
            return retried_paths, "base_head_fetch_retry"
        warnings.append(f"base/head diff still unavailable after fetch: {retry_error}")
    else:
        missing = []
        if not fetched_base:
            missing.append(base_ref)
        if not fetched_head:
            missing.append(head_ref)
        warnings.append(f"unable to fetch required refs: {', '.join(missing)}")
    return None, None


def _github_sha_pair() -> tuple[str, str, str] | None:
    event_name = (os.environ.get("GITHUB_EVENT_NAME") or "").strip()
    base_sha = (os.environ.get("GITHUB_BASE_SHA") or "").strip()
    head_sha = (os.environ.get("GITHUB_HEAD_SHA") or "").strip()
    before_sha = (os.environ.get("GITHUB_BEFORE_SHA") or "").strip()
    sha = (os.environ.get("GITHUB_SHA") or "").strip()

    if event_name == "pull_request" and base_sha and head_sha:
        return base_sha, head_sha, "github_pr_sha_pair"
    if event_name == "push" and before_sha and sha and before_sha != "0000000000000000000000000000000000000000":
        return before_sha, sha, "github_push_sha_pair"
    return None


def _local_workspace_changes(repo_root: Path) -> list[str]:
    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if status.returncode != 0:
        return []
    paths: list[str] = []
    for line in status.stdout.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if path:
            paths.append(path)
    return sorted(set(paths))


def resolve_changed_paths(
    *,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    explicit: list[str] | None = None,
) -> ChangedPathResolutionResult:
    refs_attempted: list[str] = []
    warnings: list[str] = []

    if explicit:
        return ChangedPathResolutionResult(
            changed_paths=sorted(set(explicit)),
            changed_path_detection_mode="explicit_paths",
            refs_attempted=[],
            fallback_used=False,
            warnings=[],
            trust_level="authoritative",
            resolution_mode="explicit",
            bounded_runtime=True,
            insufficient_context=False,
        )

    exact_paths, exact_mode = _try_diff_with_ref_fetch(
        repo_root=repo_root,
        base_ref=base_ref,
        head_ref=head_ref,
        refs_attempted=refs_attempted,
        warnings=warnings,
    )
    if exact_mode is not None and exact_paths is not None:
        return ChangedPathResolutionResult(
            changed_paths=exact_paths,
            changed_path_detection_mode=exact_mode,
            refs_attempted=refs_attempted,
            fallback_used=exact_mode != "base_head_diff",
            warnings=[],
            trust_level="authoritative" if exact_mode == "base_head_diff" else "bounded",
            resolution_mode="exact_diff",
            bounded_runtime=True,
            insufficient_context=False,
        )

    sha_pair = _github_sha_pair()
    if sha_pair:
        gh_base, gh_head, mode = sha_pair
        fetched_gh_base = _fetch_ref(repo_root, gh_base)
        fetched_gh_head = _fetch_ref(repo_root, gh_head)
        refs_attempted.append(f"{gh_base}..{gh_head}")
        gh_paths, gh_error = _diff_name_only(repo_root, gh_base, gh_head)
        if not gh_error:
            return ChangedPathResolutionResult(
                changed_paths=gh_paths,
                changed_path_detection_mode=mode,
                refs_attempted=refs_attempted,
                fallback_used=True,
                warnings=warnings if (fetched_gh_base and fetched_gh_head) else warnings + ["github refs required fetch"],
                trust_level="bounded",
                resolution_mode="fetched_diff",
                bounded_runtime=True,
                insufficient_context=False,
            )
        warnings.append(f"github event ref diff unavailable: {gh_error}")

    if head_ref != "HEAD":
        fetched_base = _fetch_ref(repo_root, base_ref)
        refs_attempted.append(f"{base_ref}..HEAD")
        fetched_paths, fetched_error = _diff_name_only(repo_root, base_ref, "HEAD")
        if not fetched_error:
            return ChangedPathResolutionResult(
                changed_paths=fetched_paths,
                changed_path_detection_mode="base_to_current_head_fallback",
                refs_attempted=refs_attempted,
                fallback_used=True,
                warnings=warnings + ["head ref unavailable; used current HEAD fallback"],
                trust_level="bounded",
                resolution_mode="fetched_diff",
                bounded_runtime=True,
                insufficient_context=False,
            )
        warnings.append(f"base..HEAD fallback unavailable: {fetched_error}")

    local_changes = _local_workspace_changes(repo_root)
    if local_changes:
        return ChangedPathResolutionResult(
            changed_paths=local_changes,
            changed_path_detection_mode="local_workspace_status",
            refs_attempted=refs_attempted,
            fallback_used=True,
            warnings=warnings + ["using git status porcelain fallback"],
            trust_level="degraded",
            resolution_mode="working_tree",
            bounded_runtime=False,
            insufficient_context=False,
        )

    refs_attempted.append("working_tree_vs_HEAD")
    working_tree = _run(["git", "diff", "--name-only", "HEAD"], cwd=repo_root)
    if working_tree.returncode == 0:
        working_paths = sorted({line.strip() for line in working_tree.stdout.splitlines() if line.strip()})
        if working_paths:
            return ChangedPathResolutionResult(
                changed_paths=working_paths,
                changed_path_detection_mode="working_tree_diff_head",
                refs_attempted=refs_attempted,
                fallback_used=True,
                warnings=warnings + ["using working tree diff fallback"],
                trust_level="degraded",
                resolution_mode="working_tree",
                bounded_runtime=False,
                insufficient_context=False,
            )

    return ChangedPathResolutionResult(
        changed_paths=[],
        changed_path_detection_mode="detection_failed_no_governed_paths",
        refs_attempted=refs_attempted,
        fallback_used=True,
        warnings=warnings + ["insufficient diff context; blocking preflight execution"],
        trust_level="insufficient",
        resolution_mode="insufficient",
        bounded_runtime=False,
        insufficient_context=True,
    )


__all__ = ["ChangedPathResolutionResult", "resolve_changed_paths"]
