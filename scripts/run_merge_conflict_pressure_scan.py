#!/usr/bin/env python3
"""Merge-conflict pressure scanner (MET observation only).

Scans the current branch against a base ref (default ``main``) to detect
files that have been modified on both sides since the branch point. Writes
a non-owning observation artifact under
``artifacts/dashboard_metrics/merge_conflict_pressure_record.json`` so the
dashboard can surface conflict risk before the PR reaches the merge gate.

MET emits an observation only. Canonical conflict-resolution authority
remains with the developer / AEX-PQX-CDE-SEL loop. The scanner does not
rebase, merge, or rewrite history. It does not gate the PR. It surfaces a
signal so authors can pre-emptively pull main and resolve before the merge
queue blocks the change.

Usage:

    python scripts/run_merge_conflict_pressure_scan.py \\
        --base-ref main \\
        --head-ref HEAD \\
        --output artifacts/dashboard_metrics/merge_conflict_pressure_record.json

Exit code is always 0 — MET is non-owning on conflict pressure. Downstream
gates (review, branch-protection) retain canonical responsibility.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "dashboard_metrics" / "merge_conflict_pressure_record.json"


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    return result.stdout.strip()


def _changed_files(rev_a: str, rev_b: str) -> list[str]:
    out = _run(["git", "diff", "--name-only", f"{rev_a}...{rev_b}"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def _merge_base(rev_a: str, rev_b: str) -> str:
    return _run(["git", "merge-base", rev_a, rev_b])


@dataclass
class ConflictPressureItem:
    file_path: str
    head_changed: bool
    base_changed: bool
    risk: str  # "low" | "medium" | "high" | "unknown"
    reason: str
    next_recommended_input: str

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "head_changed": self.head_changed,
            "base_changed": self.base_changed,
            "risk": self.risk,
            "reason": self.reason,
            "next_recommended_input": self.next_recommended_input,
        }


# Files whose conflicts are typically content-merge (high risk) vs append-only
# (medium) vs auto-mergeable (low). The classifier is heuristic — MET surfaces
# the signal; canonical owners adjudicate.
HIGH_RISK_PATTERNS = (
    "apps/dashboard-3ls/app/api/intelligence/route.ts",
    "apps/dashboard-3ls/app/page.tsx",
    "docs/architecture/system_registry.md",
)
MEDIUM_RISK_PREFIXES = (
    "apps/dashboard-3ls/",
    "spectrum_systems/",
    "scripts/",
    "tests/",
    "docs/architecture/",
    "docs/reviews/",
    "contracts/",
)
LOW_RISK_PREFIXES = (
    "artifacts/",
    "outputs/",
    "state/",
    "data/",
    "governance/reports/",
    "docs/governance-reports/",
)


def _classify(file_path: str) -> str:
    if file_path in HIGH_RISK_PATTERNS:
        return "high"
    if any(file_path.startswith(p) for p in MEDIUM_RISK_PREFIXES):
        return "medium"
    if any(file_path.startswith(p) for p in LOW_RISK_PREFIXES):
        return "low"
    return "medium"


def _next_recommended_input(file_path: str, risk: str) -> str:
    if risk == "high":
        return (
            f"Pre-emptively `git merge origin/main` while still on the feature "
            f"branch and resolve {file_path} now. Re-run the cockpit tests after "
            f"resolving."
        )
    if risk == "medium":
        return (
            f"Rebase or merge main soon; {file_path} has parallel edits that "
            f"may need reconciliation."
        )
    return (
        f"{file_path} typically auto-merges (regenerated artifact / report); "
        f"no immediate action required."
    )


def scan(base_ref: str, head_ref: str) -> dict:
    # Verify both refs resolve before attempting merge-base. If git fails to
    # resolve a ref or compute a merge base, the cockpit must surface
    # 'unknown' rather than silently report no_pressure_observed — a clean
    # state from a command failure is a false negative.
    base_resolved = _run(["git", "rev-parse", base_ref])
    head_resolved = _run(["git", "rev-parse", head_ref])
    merge_base = _merge_base(base_ref, head_ref) if base_resolved and head_resolved else ""

    git_lookup_ok = bool(base_resolved and head_resolved and merge_base)

    items: list[ConflictPressureItem] = []
    if git_lookup_ok:
        head_changes = set(_changed_files(merge_base, head_ref))
        base_changes = set(_changed_files(merge_base, base_ref))
        parallel = sorted(head_changes & base_changes)
        for path in parallel:
            risk = _classify(path)
            reason = (
                "Both head and base have modified this file since the merge base; "
                "git will attempt auto-merge but content conflicts are possible."
            )
            items.append(
                ConflictPressureItem(
                    file_path=path,
                    head_changed=True,
                    base_changed=True,
                    risk=risk,
                    reason=reason,
                    next_recommended_input=_next_recommended_input(path, risk),
                )
            )

    counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for item in items:
        counts[item.risk] = counts.get(item.risk, 0) + 1

    if not git_lookup_ok:
        overall_state = "unknown"
        status = "unknown"
    elif not items:
        overall_state = "no_pressure_observed"
        status = "ok"
    elif counts.get("high", 0) > 0:
        overall_state = "high_pressure_observed"
        status = "warn"
    elif counts.get("medium", 0) > 0:
        overall_state = "medium_pressure_observed"
        status = "warn"
    else:
        overall_state = "low_pressure_observed"
        status = "warn"

    warnings = [
        "Conflict pressure is an MET observation only; canonical conflict resolution belongs to the developer / PR flow.",
    ]
    reason_codes = [
        "merge_conflict_pressure_observation_only",
        "no_authority_outcome",
        "developer_owns_resolution",
    ]
    if not git_lookup_ok:
        missing: list[str] = []
        if not base_resolved:
            missing.append(f"base ref '{base_ref}' did not resolve via git rev-parse")
        if not head_resolved:
            missing.append(f"head ref '{head_ref}' did not resolve via git rev-parse")
        if base_resolved and head_resolved and not merge_base:
            missing.append(
                f"git merge-base {base_ref} {head_ref} returned empty; refs may not "
                f"share history"
            )
        warnings.append(
            "Git ref lookup failed; conflict pressure reported as unknown rather "
            f"than no_pressure_observed. ({'; '.join(missing)})"
        )
        reason_codes.append("git_ref_lookup_failed")

    return {
        "artifact_type": "merge_conflict_pressure_record",
        "schema_version": "1.0.0",
        "record_id": f"MCP-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "owner_system": "MET",
        "data_source": "git_diff",
        "source_artifacts_used": [
            ".git/HEAD",
            f"git:{base_ref}",
            f"git:{head_ref}",
        ],
        "reason_codes": reason_codes,
        "status": status,
        "warnings": warnings,
        "failure_prevented": "PR reaching the merge gate with unresolved conflicts that block branch advancement.",
        "signal_improved": "Per-file conflict risk and next recommended input are surfaced before the merge queue rejects the PR.",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_resolved": base_resolved or "unknown",
        "head_resolved": head_resolved or "unknown",
        "merge_base": merge_base or "unknown",
        "overall_state": overall_state,
        "counts": counts,
        "items": [item.to_dict() for item in items],
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    result = scan(args.base_ref, args.head_ref)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({
        "status": result["status"],
        "overall_state": result["overall_state"],
        "counts": result["counts"],
        "output": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
