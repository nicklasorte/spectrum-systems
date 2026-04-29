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

Exit code is always 0 — MET does not fail-closed on conflict pressure.
Downstream gates (review, branch-protection) own enforcement.
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
    base_resolved = _run(["git", "rev-parse", base_ref]) or base_ref
    head_resolved = _run(["git", "rev-parse", head_ref]) or head_ref
    merge_base = _merge_base(base_ref, head_ref)
    head_changes = set(_changed_files(merge_base, head_ref)) if merge_base else set()
    base_changes = set(_changed_files(merge_base, base_ref)) if merge_base else set()
    parallel = sorted(head_changes & base_changes)

    items: list[ConflictPressureItem] = []
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

    overall_state = (
        "no_pressure_observed"
        if not items
        else "high_pressure_observed"
        if counts.get("high", 0) > 0
        else "medium_pressure_observed"
        if counts.get("medium", 0) > 0
        else "low_pressure_observed"
    )

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
        "reason_codes": [
            "merge_conflict_pressure_observation_only",
            "no_authority_outcome",
            "developer_owns_resolution",
        ],
        "status": "warn" if items else "ok",
        "warnings": [
            "Conflict pressure is an MET observation only; canonical conflict resolution belongs to the developer / PR flow.",
        ],
        "failure_prevented": "PR reaching the merge gate with unresolved conflicts that block branch advancement.",
        "signal_improved": "Per-file conflict risk and next recommended input are surfaced before the merge queue rejects the PR.",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_resolved": base_resolved,
        "head_resolved": head_resolved,
        "merge_base": merge_base,
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
