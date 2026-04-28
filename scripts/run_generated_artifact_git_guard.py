#!/usr/bin/env python3
"""Fail-closed guard preventing hand-merge of generated run-specific artifacts.

Generated run-specific artifacts (see ``config/generated_artifact_policy.json``
for the canonical denylist) are outputs of governed execution. They contain
timestamps, trace IDs, and run IDs that diverge between parallel branches
and so produce recurring Git merge conflicts when hand-resolved.

This guard:
  * loads the generated-artifact policy
    (``config/generated_artifact_policy.json``);
  * resolves the changed files for the current PR/push using the canonical
    changed-files resolver;
  * classifies each changed file against the policy
    (``denylist`` / ``allowlist`` / ``schema_paths`` /
    ``documentation_paths`` / ``test_fixture_paths`` / ``unknown``);
  * fails when denylisted run-specific artifacts are added or modified
    outside a permitted regeneration context;
  * always fails on a leftover Git conflict marker inside a tracked JSON
    file under the policy's denylist;
  * writes a deterministic ``generated_artifact_git_guard_result`` artifact.

Failure is closed:
  * missing policy file -> fail;
  * malformed policy file -> fail;
  * ambiguous classification (denylisted path inside an allowlist glob with
    no exception entry) -> fail;
  * unresolvable changed-file range -> fail.

This guard does not replace, weaken, or bypass any canonical owner. It is a
thin pre-merge safety net for the specific failure mode of hand-merging
governed run state. Canonical owners retain their existing authority.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)

DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "generated_artifact_policy.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "outputs" / "generated_artifact_git_guard" / "generated_artifact_git_guard_result.json"

CONFLICT_MARKER_RE = re.compile(r"^(<{7}|={7}|>{7}) ", re.MULTILINE)

REMEDIATION_MESSAGE = (
    "This is a generated run-specific artifact. Do not merge it. "
    "Regenerate it locally or in CI by running the regenerator script "
    "declared in config/generated_artifact_policy.json, or add an "
    "explicit allowlist entry with justification."
)


class GeneratedArtifactGuardError(ValueError):
    """Raised when the guard cannot complete deterministically."""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files (overrides git diff)")
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY_PATH.relative_to(REPO_ROOT)),
        help="Path to generated_artifact_policy.json (relative to repo root)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH.relative_to(REPO_ROOT)),
        help="Output artifact path (relative to repo root)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Override repo root (used in tests)",
    )
    return parser.parse_args(argv)


def load_policy(policy_path: Path) -> dict[str, Any]:
    if not policy_path.is_file():
        raise GeneratedArtifactGuardError(
            f"generated_artifact_policy missing at {policy_path}"
        )
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GeneratedArtifactGuardError(
            f"generated_artifact_policy malformed JSON at {policy_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GeneratedArtifactGuardError(
            f"generated_artifact_policy must be a JSON object at {policy_path}"
        )
    if payload.get("artifact_type") != "generated_artifact_policy":
        raise GeneratedArtifactGuardError(
            "generated_artifact_policy.artifact_type must be 'generated_artifact_policy'"
        )
    for key in ("denylist", "allowlist", "schema_paths", "documentation_paths", "test_fixture_paths"):
        value = payload.get(key)
        if value is None:
            raise GeneratedArtifactGuardError(
                f"generated_artifact_policy missing required key '{key}'"
            )
        if key in ("denylist", "allowlist"):
            if not isinstance(value, list):
                raise GeneratedArtifactGuardError(
                    f"generated_artifact_policy.{key} must be a list"
                )
            for entry in value:
                if not isinstance(entry, dict) or "path_glob" not in entry:
                    raise GeneratedArtifactGuardError(
                        f"generated_artifact_policy.{key} entries must be objects with path_glob"
                    )
        else:
            if not isinstance(value, list) or not all(isinstance(p, str) for p in value):
                raise GeneratedArtifactGuardError(
                    f"generated_artifact_policy.{key} must be a list of strings"
                )
    payload.setdefault("regeneration_exceptions", [])
    if not isinstance(payload["regeneration_exceptions"], list):
        raise GeneratedArtifactGuardError(
            "generated_artifact_policy.regeneration_exceptions must be a list"
        )
    return payload


def _matches(path: str, glob: str) -> bool:
    """Match `path` against `glob`; supports `**` recursive segments."""
    if "**" in glob:
        # Convert ** to a regex that matches across path segments.
        pattern = re.escape(glob).replace(re.escape("**"), ".*").replace(re.escape("*"), "[^/]*")
        return re.fullmatch(pattern, path) is not None
    return fnmatch.fnmatchcase(path, glob)


def _matches_any(path: str, globs: list) -> bool:
    return any(_matches(path, g) for g in globs)


def _denylist_entry_for(path: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    for entry in policy["denylist"]:
        if _matches(path, entry["path_glob"]):
            return entry
    return None


def _allowlist_entry_for(path: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    for entry in policy["allowlist"]:
        if _matches(path, entry["path_glob"]):
            return entry
    return None


def _exception_for(path: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    for entry in policy.get("regeneration_exceptions", []) or []:
        glob = entry.get("path_glob")
        if isinstance(glob, str) and _matches(path, glob):
            return entry
    return None


def classify_path(path: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Classify a single path against the policy.

    Returns a dict with keys:
      - classification: one of denylisted, allowlisted, schema, documentation,
        test_fixture, unknown, ambiguous
      - matched_entry: the matched policy entry (if any)
    """
    deny = _denylist_entry_for(path, policy)
    allow = _allowlist_entry_for(path, policy)
    if deny and allow:
        # Allowlist must explicitly override the denylist via a regeneration
        # exception; otherwise the classification is ambiguous and we fail closed.
        if _exception_for(path, policy):
            return {"classification": "allowlisted", "matched_entry": allow}
        return {
            "classification": "ambiguous",
            "matched_entry": {"denylist": deny, "allowlist": allow},
        }
    if deny:
        return {"classification": "denylisted", "matched_entry": deny}
    if allow:
        return {"classification": "allowlisted", "matched_entry": allow}
    if _matches_any(path, policy["schema_paths"]):
        return {"classification": "schema", "matched_entry": None}
    if _matches_any(path, policy["documentation_paths"]):
        return {"classification": "documentation", "matched_entry": None}
    if _matches_any(path, policy["test_fixture_paths"]):
        return {"classification": "test_fixture", "matched_entry": None}
    return {"classification": "unknown", "matched_entry": None}


def _has_conflict_markers(repo_root: Path, rel_path: str) -> bool:
    full = repo_root / rel_path
    if not full.is_file():
        return False
    try:
        text = full.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    return bool(CONFLICT_MARKER_RE.search(text))


def evaluate_changed_files(
    *,
    changed_files: list[str],
    policy: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []
    regenerator_seen: set[str] = set()

    # First pass: figure out which regenerator scripts are part of this change.
    for rel in changed_files:
        for entry in policy["denylist"]:
            regen = entry.get("regenerator")
            if regen and rel == regen:
                regenerator_seen.add(regen)

    for rel in changed_files:
        path_record = classify_path(rel, policy)
        record = {
            "path": rel,
            "classification": path_record["classification"],
            "matched_entry": path_record["matched_entry"],
        }
        classifications.append(record)

        if path_record["classification"] == "denylisted":
            entry = path_record["matched_entry"]
            regen = entry.get("regenerator") if isinstance(entry, dict) else None
            exception = _exception_for(rel, policy)
            allowed = False
            allow_reason = None
            if exception is not None:
                allowed = True
                allow_reason = "regeneration_exception"
            elif regen and regen in regenerator_seen:
                allowed = True
                allow_reason = "regenerator_changed_in_pr"
            if not allowed:
                findings.append(
                    {
                        "path": rel,
                        "reason_code": "GENERATED_ARTIFACT_HAND_MERGE_BLOCKED",
                        "policy_entry": entry,
                        "regenerator": regen,
                        "remediation": REMEDIATION_MESSAGE,
                    }
                )
            else:
                record["allow_reason"] = allow_reason

            if _has_conflict_markers(repo_root, rel):
                findings.append(
                    {
                        "path": rel,
                        "reason_code": "GENERATED_ARTIFACT_LEFTOVER_CONFLICT_MARKER",
                        "policy_entry": entry,
                        "regenerator": regen,
                        "remediation": REMEDIATION_MESSAGE,
                    }
                )

        elif path_record["classification"] == "ambiguous":
            findings.append(
                {
                    "path": rel,
                    "reason_code": "GENERATED_ARTIFACT_AMBIGUOUS_CLASSIFICATION",
                    "policy_entry": path_record["matched_entry"],
                    "remediation": (
                        "Path matches both denylist and allowlist. Add an explicit "
                        "regeneration_exceptions entry with justification, or tighten "
                        "the allowlist glob."
                    ),
                }
            )

        elif path_record["classification"] == "unknown":
            # Unknown only blocks for paths under artifacts/ — every artifact
            # path must be classified. Source code, configs, tests, and docs
            # outside our governed-artifact surface are intentionally not
            # required to register.
            if rel.startswith("artifacts/"):
                findings.append(
                    {
                        "path": rel,
                        "reason_code": "GENERATED_ARTIFACT_UNCLASSIFIED",
                        "remediation": (
                            "Artifact path is not classified by "
                            "config/generated_artifact_policy.json. Add it to denylist "
                            "(with regenerator) or allowlist (with rationale)."
                        ),
                    }
                )

    return {
        "classifications": classifications,
        "findings": findings,
        "regenerator_scripts_in_pr": sorted(regenerator_seen),
    }


def _build_result(
    *,
    base_ref: str,
    head_ref: str,
    changed_files: list[str],
    evaluation: dict[str, Any],
    policy_version: str,
) -> dict[str, Any]:
    findings = evaluation["findings"]
    return {
        "artifact_type": "generated_artifact_git_guard_result",
        "schema_version": "1.0.0",
        "policy_version": policy_version,
        "status": "fail" if findings else "pass",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "regenerator_scripts_in_pr": evaluation["regenerator_scripts_in_pr"],
        "classifications": evaluation["classifications"],
        "finding_count": len(findings),
        "findings": findings,
        "remediation_message": REMEDIATION_MESSAGE,
    }


def _write_result(output_path: Path, result: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    policy_path = (repo_root / args.policy).resolve()
    output_path = (repo_root / args.output).resolve()

    policy = load_policy(policy_path)

    try:
        changed_files = resolve_changed_files(
            repo_root=repo_root,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        raise GeneratedArtifactGuardError(str(exc)) from exc

    evaluation = evaluate_changed_files(
        changed_files=changed_files,
        policy=policy,
        repo_root=repo_root,
    )
    result = _build_result(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_files=changed_files,
        evaluation=evaluation,
        policy_version=str(policy.get("policy_version", "unknown")),
    )
    _write_result(output_path, result)

    if result["status"] == "fail":
        print("Generated-artifact git guard FAILED:")
        for finding in result["findings"]:
            print(
                f" - {finding['path']}: {finding['reason_code']}"
                + (f"  (regenerator: {finding.get('regenerator')})" if finding.get("regenerator") else "")
            )
        print()
        print(REMEDIATION_MESSAGE)
        print(f"\nFull guard artifact: {output_path}")
        return 1

    print(
        f"Generated-artifact git guard passed: "
        f"{len(changed_files)} changed file(s), {len(evaluation['classifications'])} classified, "
        "0 denylist violations."
    )
    print(f"Guard artifact: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GeneratedArtifactGuardError as exc:
        print(f"Generated-artifact git guard error: {exc}", file=sys.stderr)
        sys.exit(2)
