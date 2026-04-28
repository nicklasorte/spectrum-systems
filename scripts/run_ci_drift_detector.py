#!/usr/bin/env python3
"""Detect CI/test drift against canonical gate ownership (TST-25)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_GATE_SCRIPTS = {
    "scripts/run_pr_gate.py",
    "scripts/run_contract_gate.py",
    "scripts/run_test_selection_gate.py",
    "scripts/run_runtime_test_gate.py",
    "scripts/run_governance_gate.py",
    "scripts/run_certification_gate.py",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CI drift detector")
    parser.add_argument("--output", default="outputs/ci_drift_detector/ci_drift_detector_result.json")
    args = parser.parse_args()

    mapping = _load_json(REPO_ROOT / "docs/governance/test_gate_mapping.json")
    ownership = _load_json(REPO_ROOT / "docs/governance/ci_gate_ownership_manifest.json")
    failures: list[str] = []

    workflow_paths = sorted((REPO_ROOT / ".github/workflows").glob("*.yml"))
    for wf in workflow_paths:
        text = wf.read_text(encoding="utf-8")
        scripts = set(re.findall(r"scripts/[A-Za-z0-9_./-]+", text))
        if scripts and scripts.isdisjoint(CANONICAL_GATE_SCRIPTS) and "nightly-deep-gate.yml" not in wf.name:
            failures.append(f"workflow_bypasses_canonical_gates:{wf.relative_to(REPO_ROOT)}")

    for script in sorted({s for wf in workflow_paths for s in re.findall(r"scripts/[A-Za-z0-9_./-]+", wf.read_text(encoding='utf-8'))}):
        if script.startswith("scripts/") and script not in CANONICAL_GATE_SCRIPTS and "owned_ci_scripts" in ownership:
            if script not in ownership.get("owned_ci_scripts", []):
                failures.append(f"script_without_ownership:{script}")

    all_tests = [str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "tests").rglob("*") if p.is_file() and (p.name.startswith("test_") or ".test." in p.name)]
    mapped = set(mapping.get("tests", {}).keys())
    for t in all_tests:
        if t not in mapped:
            failures.append(f"test_without_gate_mapping:{t}")

    required_checks = _load_json(REPO_ROOT / "docs/governance/required_pr_checks.json")
    for check in required_checks.get("required_checks", []):
        cid = check.get("job_id")
        if cid and cid not in ownership.get("required_checks", {}):
            failures.append(f"required_check_without_mapping:{cid}")

    schema_refs = [
        "contracts/schemas/contract_gate_result.schema.json",
        "contracts/schemas/test_selection_gate_result.schema.json",
        "contracts/schemas/runtime_test_gate_result.schema.json",
        "contracts/schemas/governance_gate_result.schema.json",
        "contracts/schemas/certification_gate_result.schema.json",
        "contracts/schemas/pr_gate_result.schema.json",
    ]
    for ref in schema_refs:
        p = REPO_ROOT / ref
        if not p.is_file():
            failures.append(f"missing_gate_schema:{ref}")
            continue
        payload = _load_json(p)
        if payload.get("type") != "object" or payload.get("additionalProperties") is not False:
            failures.append(f"invalid_gate_schema_shape:{ref}")

    status = "allow" if not failures else "block"
    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"artifact_type": "ci_drift_detector_result", "status": status, "failures": failures}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "failure_count": len(failures), "output": str(output)}, indent=2))
    return 0 if status == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
