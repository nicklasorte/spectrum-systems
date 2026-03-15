#!/usr/bin/env python3
"""
Validate that a run evidence bundle is complete and correlated by run_id.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

REQUIRED_FILES = [
    "run_manifest.json",
    "evaluation_results.json",
    "contract_validation_report.json",
    "provenance.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_bundle(bundle_path: Path) -> Dict[str, object]:
    errors: List[str] = []
    run_ids: Dict[str, str] = {}

    if not bundle_path.is_dir():
        errors.append(f"Evidence bundle is not a directory: {bundle_path}")
        return {"bundle": str(bundle_path), "status": "fail", "errors": errors, "run_ids": run_ids}

    for filename in REQUIRED_FILES:
        artifact_path = bundle_path / filename
        if not artifact_path.is_file():
            errors.append(f"Missing required artifact: {artifact_path}")
            continue

        try:
            data = load_json(artifact_path)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {artifact_path}: {exc}")
            continue

        run_id = data.get("run_id")
        if run_id is None:
            errors.append(f"Missing run_id in {artifact_path}")
            continue
        if not isinstance(run_id, str):
            errors.append(f"run_id must be a string in {artifact_path}")
            continue

        run_ids[filename] = run_id

    unique_run_ids = {value for value in run_ids.values()}
    if len(unique_run_ids) > 1:
        errors.append(f"run_id mismatch across artifacts: {run_ids}")

    status = "pass" if not errors else "fail"
    return {
        "bundle": str(bundle_path),
        "status": status,
        "errors": errors,
        "run_ids": run_ids,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate run evidence correlation by run_id.")
    parser.add_argument("bundle", help="Path to an evidence bundle directory")
    args = parser.parse_args(argv)

    bundle_path = Path(args.bundle).resolve()
    result = validate_bundle(bundle_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
