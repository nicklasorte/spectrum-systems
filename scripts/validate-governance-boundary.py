#!/usr/bin/env python3
"""Reads the governance boundary schema and checks the repo for boundary violations."""
import json
import sys
from pathlib import Path


def load_schema(schema_path: Path) -> dict:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def check_boundary(repo_root: Path, schema: dict) -> list[str]:
    findings = []
    boundary_paths = schema.get("boundary_violations", [])
    for boundary_path in boundary_paths:
        target = repo_root / boundary_path
        if target.exists():
            findings.append(
                f"BOUNDARY FINDING: '{boundary_path}' exists in governance repo — "
                "should be migrated to spectrum-pipeline-engine"
            )
    return findings


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "ecosystem" / "spectrum-systems.file-types.schema.json"

    if not schema_path.exists():
        print(f"ERROR: Schema not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    schema = load_schema(schema_path)
    findings = check_boundary(repo_root, schema)

    if findings:
        for finding in findings:
            print(finding)
        print(
            f"\nGovernance boundary check: {len(findings)} finding(s) detected.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Governance boundary check passed — no findings detected.")
    sys.exit(0)


if __name__ == "__main__":
    main()
