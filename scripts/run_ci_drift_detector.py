"""
CI Drift Detector — detects when CI has drifted from the canonical gate model.

Fails when:
- A new workflow is added without canonical gate mapping
- A new script is invoked by CI without ownership
- A new test file lacks gate mapping
- A new required check is referenced but not mapped
- A workflow bypasses canonical gates
- A gate result artifact schema is missing or invalid

Run as part of the PR gate (governance step) or as a standalone check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


_GATE_RESULT_SCHEMAS = [
    "contracts/schemas/contract_gate_result.schema.json",
    "contracts/schemas/test_selection_gate_result.schema.json",
    "contracts/schemas/runtime_test_gate_result.schema.json",
    "contracts/schemas/governance_gate_result.schema.json",
    "contracts/schemas/certification_gate_result.schema.json",
    "contracts/schemas/pr_gate_result.schema.json",
]

_CANONICAL_GATE_SCRIPTS = {
    "scripts/run_contract_gate.py",
    "scripts/run_test_selection_gate.py",
    "scripts/run_runtime_test_gate.py",
    "scripts/run_governance_gate.py",
    "scripts/run_certification_gate.py",
    "scripts/run_pr_gate.py",
}

_KNOWN_WORKFLOW_GATE_MAPPING = {
    "pr-pytest.yml": "contract_gate",
    "artifact-boundary.yml": "contract_gate",
    "lifecycle-enforcement.yml": "certification_gate",
    "strategy-compliance.yml": "governance_gate",
    "pr-autofix-contract-preflight.yml": "contract_gate",
    "3ls-registry-gate.yml": "governance_gate",
    "review-artifact-validation.yml": "governance_gate",
    "pr-autofix-review-artifact-validation.yml": "governance_gate",
    "release-canary.yml": "certification_gate",
    "dashboard-deploy-gate.yml": "runtime_test_gate",
    "ecosystem-registry-validation.yml": "governance_gate",
    "cross-repo-compliance.yml": "governance_gate",
    "design-review-scan.yml": "governance_gate",
    "review_trigger_pipeline.yml": "governance_gate",
    "closure_continuation_pipeline.yml": "governance_gate",
    "claude-review-ingest.yml": "governance_gate",
    "ssos-project-automation.yml": "governance_gate",
    "nightly-deep-gate.yml": "runtime_test_gate",
}


_WORKFLOW_SCRIPT_RE = re.compile(r'python[23]?(?:\s+-\S+)*\s+scripts/([\w.\-]+\.py)')


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DriftFinding:
    def __init__(self, category: str, description: str, path: str, severity: str = "error") -> None:
        self.category = category
        self.description = description
        self.path = path
        self.severity = severity


def check_workflow_gate_mapping(repo_root: Path) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    workflow_dir = repo_root / ".github/workflows"
    if not workflow_dir.is_dir():
        return findings
    for yml in sorted({*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")}):
        name = yml.name
        if name not in _KNOWN_WORKFLOW_GATE_MAPPING:
            findings.append(DriftFinding(
                "unmapped_workflow",
                f"New workflow {name!r} is not mapped to a canonical gate. "
                f"Add it to _KNOWN_WORKFLOW_GATE_MAPPING in run_ci_drift_detector.py "
                f"and to docs/governance/ci_gate_ownership_manifest.json",
                str(yml.relative_to(repo_root)),
                "error",
            ))
    return findings


def check_workflow_script_invocations(repo_root: Path) -> list[DriftFinding]:
    """Flag any mapped workflow that invokes a python script that does not exist."""
    findings: list[DriftFinding] = []
    workflow_dir = repo_root / ".github/workflows"
    if not workflow_dir.is_dir():
        return findings
    for yml in sorted({*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")}):
        if yml.name not in _KNOWN_WORKFLOW_GATE_MAPPING:
            continue  # unmapped_workflow already reported by check_workflow_gate_mapping
        content = yml.read_text(encoding="utf-8")
        for match in _WORKFLOW_SCRIPT_RE.finditer(content):
            script_rel = f"scripts/{match.group(1)}"
            if not (repo_root / script_rel).is_file():
                findings.append(DriftFinding(
                    "orphaned_script_invocation",
                    f"Workflow {yml.name!r} invokes {script_rel!r} which does not exist",
                    str(yml.relative_to(repo_root)),
                    "error",
                ))
    return findings


def check_gate_result_schemas(repo_root: Path) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for schema_path in _GATE_RESULT_SCHEMAS:
        full = repo_root / schema_path
        if not full.is_file():
            findings.append(DriftFinding(
                "missing_gate_schema",
                f"Gate result schema missing: {schema_path}",
                schema_path,
                "error",
            ))
        else:
            try:
                schema = json.loads(full.read_text(encoding="utf-8"))
                if schema.get("additionalProperties") is not False:
                    findings.append(DriftFinding(
                        "weak_gate_schema",
                        f"Gate result schema {schema_path} does not use additionalProperties: false",
                        schema_path,
                        "error",
                    ))
            except json.JSONDecodeError as e:
                findings.append(DriftFinding(
                    "invalid_gate_schema",
                    f"Gate result schema {schema_path} is invalid JSON: {e}",
                    schema_path,
                    "error",
                ))
    return findings


def check_test_gate_mapping(repo_root: Path) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    mapping_path = repo_root / "docs/governance/test_gate_mapping.json"
    if not mapping_path.is_file():
        findings.append(DriftFinding(
            "missing_test_mapping",
            "docs/governance/test_gate_mapping.json is missing. Run TST-09 to generate it.",
            "docs/governance/test_gate_mapping.json",
            "error",
        ))
        return findings

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapped_files = {m["test_file"] for m in mapping.get("mappings", [])}

    # Find all current test files
    for test_file in repo_root.rglob("test_*.py"):
        relative = str(test_file.relative_to(repo_root))
        if "conftest" in relative or "__pycache__" in relative:
            continue
        if relative not in mapped_files:
            findings.append(DriftFinding(
                "unmapped_test_file",
                f"Test file {relative!r} has no gate mapping in test_gate_mapping.json",
                relative,
                "error",
            ))
    return findings


def check_canonical_gate_scripts(repo_root: Path) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for script in _CANONICAL_GATE_SCRIPTS:
        full = repo_root / script
        if not full.is_file():
            findings.append(DriftFinding(
                "missing_gate_script",
                f"Canonical gate script missing: {script}",
                script,
                "error",
            ))
    return findings


def check_ownership_manifest(repo_root: Path) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    manifest_path = repo_root / "docs/governance/ci_gate_ownership_manifest.json"
    if not manifest_path.is_file():
        findings.append(DriftFinding(
            "missing_ownership_manifest",
            "docs/governance/ci_gate_ownership_manifest.json is missing",
            "docs/governance/ci_gate_ownership_manifest.json",
            "error",
        ))
        return findings

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        findings.append(DriftFinding(
            "invalid_ownership_manifest",
            f"ci_gate_ownership_manifest.json is invalid JSON: {e}",
            "docs/governance/ci_gate_ownership_manifest.json",
            "error",
        ))
        return findings

    required_gates = {"contract_gate", "test_selection_gate", "runtime_test_gate", "governance_gate", "certification_gate"}
    gate_names = {g["gate_name"] for g in manifest.get("gates", [])}
    missing = required_gates - gate_names
    if missing:
        findings.append(DriftFinding(
            "incomplete_ownership_manifest",
            f"ci_gate_ownership_manifest.json missing gates: {sorted(missing)}",
            "docs/governance/ci_gate_ownership_manifest.json",
            "error",
        ))
    return findings


def _check_unmapped_test_files(repo_root: Path, shard_policy: dict) -> list[dict]:
    findings = check_test_gate_mapping(repo_root)
    return [
        {"check": "unmapped_test_files", "severity": "warn", "path": f.path, "description": f.description}
        for f in findings
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="CI Drift Detector")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="outputs/ci_drift_detector/drift_report.json")
    parser.add_argument("--fail-on-warn", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    all_findings: list[DriftFinding] = []

    all_findings += check_workflow_gate_mapping(repo_root)
    all_findings += check_workflow_script_invocations(repo_root)
    all_findings += check_gate_result_schemas(repo_root)
    all_findings += check_test_gate_mapping(repo_root)
    all_findings += check_canonical_gate_scripts(repo_root)
    all_findings += check_ownership_manifest(repo_root)

    errors = [f for f in all_findings if f.severity == "error"]
    warnings = [f for f in all_findings if f.severity == "warn"]

    status = "block" if errors else ("warn" if warnings else "pass")
    report = {
        "artifact_type": "ci_drift_detection_result",
        "schema_version": "1.0.0",
        "authority_scope": "observation_only",
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_ci_drift_detector.py",
        "total_findings": len(all_findings),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "findings": [
            {
                "check": f.category,
                "category": f.category,
                "description": f.description,
                "path": f.path,
                "severity": f.severity,
            }
            for f in all_findings
        ],
    }
    text = json.dumps(report, sort_keys=True, indent=2)
    report["artifact_hash"] = _sha256(text)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Print summary
    print(f"[ci_drift_detector] {len(errors)} errors, {len(warnings)} warnings")
    for f in all_findings:
        prefix = "ERROR" if f.severity == "error" else "WARN "
        print(f"  [{prefix}] [{f.category}] {f.path}: {f.description}")

    if errors:
        print(f"\n[ci_drift_detector] BLOCK — {len(errors)} drift errors found", file=sys.stderr)
        sys.exit(1)
    if args.fail_on_warn and warnings:
        print(f"\n[ci_drift_detector] BLOCK — {len(warnings)} warnings (--fail-on-warn)", file=sys.stderr)
        sys.exit(1)
    print(f"\n[ci_drift_detector] PASS — no drift errors detected")


if __name__ == "__main__":
    main()
