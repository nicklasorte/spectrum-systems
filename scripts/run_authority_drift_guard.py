#!/usr/bin/env python3
"""Fail-closed shift-left guard for authority drift (SHADOW_OWNERSHIP_OVERLAP).

Runs ``spectrum_systems.modules.runtime.authority_linter`` across changed
files BEFORE ``run_system_registry_guard.py``. Any drift fails the guard and
emits a deterministic ``authority_drift_guard_result`` artifact.

This guard never weakens existing checks — it only catches drift earlier so
the registry guard does not have to.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)
from spectrum_systems.guards.authority_linter import (  # noqa: E402
    AuthorityLinterError,
    lint_file,
    load_authority_matrix,
)


class AuthorityDriftGuardError(ValueError):
    """Raised when the guard cannot complete deterministically."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed authority drift guard")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--matrix",
        default="contracts/authority/authority_ownership_matrix.yaml",
        help="Authority ownership matrix path",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_drift_guard/authority_drift_guard_result.json",
        help="Output artifact path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        raise AuthorityDriftGuardError(str(exc)) from exc

    matrix_path = REPO_ROOT / args.matrix
    try:
        matrix = load_authority_matrix(matrix_path)
    except AuthorityLinterError as exc:
        raise AuthorityDriftGuardError(str(exc)) from exc

    findings: list[dict[str, object]] = []
    scanned: list[str] = []

    for rel in changed_files:
        full = REPO_ROOT / rel
        if not full.is_file():
            continue
        try:
            file_findings = lint_file(full, matrix=matrix)
        except AuthorityLinterError as exc:
            raise AuthorityDriftGuardError(f"failed to lint {rel}: {exc}") from exc
        if file_findings:
            findings.extend(file_findings)
        scanned.append(rel)

    status = "fail" if findings else "pass"
    reason_codes = sorted({str(f.get("reason_code", "unknown")) for f in findings})
    result = {
        "artifact_type": "authority_drift_guard_result",
        "schema_version": "1.0.0",
        "status": status,
        "changed_files": changed_files,
        "scanned_files": sorted(set(scanned)),
        "finding_count": len(findings),
        "findings": findings,
        "normalized_reason_codes": reason_codes,
    }

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": status,
        "changed_files": changed_files,
        "reason_codes": reason_codes,
        "finding_count": len(findings),
        "output": str(output_path),
    }
    if findings:
        summary["diagnostics"] = [
            {
                "path": f.get("path"),
                "line": f.get("line"),
                "system": f.get("system"),
                "verb": f.get("verb"),
                "canonical_owner": f.get("canonical_owner"),
                "suggested_fix": f.get("suggested_fix"),
            }
            for f in findings
        ]
    print(json.dumps(summary, indent=2))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
