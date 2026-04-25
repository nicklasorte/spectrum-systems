#!/usr/bin/env python3
"""Audit removable/merge-candidate 3LS systems from practice mappings."""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO_ROOT / "contracts/examples/top_engineer_practice_mapping_record.example.json"
OUTPUT_PATH = REPO_ROOT / "docs/reviews/removable_3ls_systems_audit.md"
TESTS_DIR = REPO_ROOT / "tests"


def run_audit() -> dict[str, list[str]]:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    systems = mapping["systems"]

    failures_to_systems: dict[str, list[str]] = defaultdict(list)
    for s in systems:
        fp = s.get("failure_prevented", "").strip()
        failures_to_systems[fp].append(s["system_id"])

    duplicate_responsibility = [
        ", ".join(sorted(ids)) + f" => {failure}"
        for failure, ids in failures_to_systems.items()
        if len(ids) > 1
    ]

    no_unique_failure = [
        s["system_id"]
        for s in systems
        if len(failures_to_systems[s.get("failure_prevented", "").strip()]) > 1
    ]

    no_artifacts = [s["system_id"] for s in systems if not s.get("debugability_surface")]

    no_tests = []
    for s in systems:
        sid = s["system_id"].lower()
        if not list(TESTS_DIR.glob(f"*{sid}*.py")):
            no_tests.append(s["system_id"])

    fold_candidates = [s for s in no_unique_failure if s not in no_artifacts]

    display_only = [s["system_id"] for s in systems if s["system_id"] == "MAP"]

    return {
        "no_unique_failure_prevented": sorted(set(no_unique_failure)),
        "duplicate_responsibility": sorted(duplicate_responsibility),
        "no_artifacts": sorted(no_artifacts),
        "no_tests": sorted(no_tests),
        "fold_candidates": sorted(set(fold_candidates)),
        "display_only_candidates": sorted(display_only),
    }


def write_markdown(findings: dict[str, list[str]]) -> None:
    lines = [
        "# Removable 3LS Systems Audit",
        "",
        "This audit identifies candidate systems for merge/removal without deleting any system in this change.",
        "",
    ]
    for key, values in findings.items():
        lines.append(f"## {key.replace('_', ' ').title()}")
        if values:
            lines.extend([f"- {v}" for v in values])
        else:
            lines.append("- none")
        lines.append("")
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    findings = run_audit()
    write_markdown(findings)
    print(f"Wrote removable system audit to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
