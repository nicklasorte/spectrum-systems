"""Fail-closed local pre-PR governance closure loop with bounded deterministic auto-repair."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PrePRGovernanceClosureError(ValueError):
    """Raised when pre-PR governance closure cannot continue safely."""


@dataclass(frozen=True)
class PrePRGovernanceClosureResult:
    gate_decision: str
    preflight_artifact_path: str
    attempted_auto_repairs: tuple[str, ...]


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PrePRGovernanceClosureError(f"expected object payload: {path}")
    return payload


def _append_missing_schema_manifest_registration(*, repo_root: Path, changed_paths: list[str]) -> bool:
    schema_paths = [p for p in changed_paths if p.startswith("contracts/schemas/") and p.endswith(".schema.json")]
    if not schema_paths:
        return False
    manifest_path = repo_root / "contracts" / "standards-manifest.json"
    manifest = _load_json(manifest_path)
    contracts = manifest.get("contracts")
    if not isinstance(contracts, list):
        raise PrePRGovernanceClosureError("contracts/standards-manifest.json missing contracts array")
    existing = {str(item.get("artifact_type")) for item in contracts if isinstance(item, dict)}
    updated = False
    for schema_path in schema_paths:
        artifact_type = Path(schema_path).name.replace(".schema.json", "")
        if artifact_type in existing:
            continue
        contracts.append(
            {
                "artifact_type": artifact_type,
                "artifact_class": "governance",
                "schema_version": "1.0.0",
                "status": "active",
                "intended_consumers": ["runtime"],
                "introduced_in": "BATCH-HR-C",
                "last_updated_in": "BATCH-HR-C",
                "example_path": f"contracts/examples/{artifact_type}.json",
                "notes": "Auto-registered during bounded pre-PR governance closure",
            }
        )
        updated = True
    if updated:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return updated


def _bounded_auto_repair(*, repo_root: Path, preflight_report: dict[str, Any], changed_paths: list[str]) -> list[str]:
    attempted: list[str] = []
    missing_surface = preflight_report.get("missing_required_surface", [])
    if isinstance(missing_surface, list) and missing_surface:
        # Deterministic registration for manifest/schema surface misses.
        if _append_missing_schema_manifest_registration(repo_root=repo_root, changed_paths=changed_paths):
            attempted.append("missing_manifest_registration")
            attempted.append("missing_schema_registration")
    return attempted


def run_local_pre_pr_governance_closure(
    *,
    repo_root: Path,
    changed_paths: list[str],
    targeted_tests: list[str],
    command_runner=_run,
) -> PrePRGovernanceClosureResult:
    """Run local pre-PR governance closure loop and fail closed on unresolved BLOCK."""

    for test_path in targeted_tests:
        res = command_runner([sys.executable, "-m", "pytest", "-q", test_path], repo_root)
        if res.returncode != 0:
            raise PrePRGovernanceClosureError(f"targeted test failed: {test_path}")

    enforce = command_runner([sys.executable, "scripts/run_contract_enforcement.py"], repo_root)
    if enforce.returncode != 0:
        raise PrePRGovernanceClosureError("contract enforcement failed")

    output_dir = repo_root / "outputs" / "pre_pr_governance"
    preflight_cmd = [sys.executable, "scripts/run_contract_preflight.py", "--output-dir", str(output_dir)]
    for path in changed_paths:
        preflight_cmd.extend(["--changed-path", path])
    preflight = command_runner(preflight_cmd, repo_root)
    artifact_path = output_dir / "contract_preflight_result_artifact.json"
    if not artifact_path.is_file():
        raise PrePRGovernanceClosureError("preflight did not emit contract_preflight_result_artifact.json")

    artifact = _load_json(artifact_path)
    decision = str(((artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK")
    attempted: list[str] = []

    if decision == "BLOCK":
        report_path = output_dir / "contract_preflight_report.json"
        if report_path.is_file():
            report = _load_json(report_path)
            attempted = _bounded_auto_repair(repo_root=repo_root, preflight_report=report, changed_paths=changed_paths)
        if attempted:
            rerun = command_runner(preflight_cmd, repo_root)
            if rerun.returncode not in (0, 2):
                raise PrePRGovernanceClosureError("preflight rerun failed")
            artifact = _load_json(artifact_path)
            decision = str(((artifact.get("control_signal") or {}).get("strategy_gate_decision")) or "BLOCK")

    if decision == "BLOCK":
        raise PrePRGovernanceClosureError("strategy gate BLOCK after bounded local repair; PR progression blocked")

    if decision == "FREEZE":
        raise PrePRGovernanceClosureError("strategy gate FREEZE after local pre-PR governance closure")

    if preflight.returncode not in (0, 2):
        raise PrePRGovernanceClosureError("preflight process failed unexpectedly")

    return PrePRGovernanceClosureResult(
        gate_decision=decision,
        preflight_artifact_path=str(artifact_path),
        attempted_auto_repairs=tuple(attempted),
    )


__all__ = [
    "PrePRGovernanceClosureError",
    "PrePRGovernanceClosureResult",
    "run_local_pre_pr_governance_closure",
]
