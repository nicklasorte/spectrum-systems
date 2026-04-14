from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.governance.system_registry_guard import parse_system_registry
from spectrum_systems.modules.governance.three_letter_system_enforcement import evaluate_three_letter_system_enforcement


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _registry_text() -> str:
    return """
# System Registry (Canonical)

## System Map
- **TPA** — trust policy
- **TLC** — orchestration
- **PRG** — governance

## System Definitions

### TPA
- **acronym:** `TPA`
- **full_name:** Trust Policy Application
- **role:** trust policy owner
- **owns:**
  - trust policy
- **consumes:**
  - evidence
- **produces:**
  - decisions
- **must_not_do:**
  - closure decisions

### TLC
- **acronym:** `TLC`
- **full_name:** Top-level Conductor
- **role:** orchestration owner
- **owns:**
  - orchestration
- **consumes:**
  - plans
- **produces:**
  - orchestration records
- **must_not_do:**
  - trust policy

### PRG
- **acronym:** `PRG`
- **full_name:** Program Governance
- **role:** governance owner
- **owns:**
  - governance
- **consumes:**
  - evidence
- **produces:**
  - governance records
- **must_not_do:**
  - execution
""".strip()


def _policy() -> dict:
    return {
        "policy_version": "1.0.0",
        "system_like_path_prefixes": ["scripts/", "spectrum_systems/modules/", ".github/workflows/", "docs/governance/", "contracts/governance/"],
        "reserved_or_transitional_paths": ["docs/reviews/"],
        "systems": {
            "TPA": {
                "owned_paths": ["scripts/run_contract_preflight.py"],
                "criticality": "high",
                "minimum_required_tests": [
                    "tests/test_contract_preflight.py",
                    "tests/test_pytest_trust_gap_audit.py",
                    "tests/test_system_registry_guard.py"
                ],
                "artifact_boundary_coverage_mandatory": False,
                "pytest_visibility_mandatory": True,
                "system_registry_review_mandatory": True,
            },
            "TLC": {
                "owned_paths": [".github/workflows/artifact-boundary.yml"],
                "criticality": "high",
                "minimum_required_tests": [
                    "tests/test_artifact_boundary_workflow_pytest_enforcement.py"
                ],
                "artifact_boundary_coverage_mandatory": True,
                "pytest_visibility_mandatory": False,
                "system_registry_review_mandatory": False,
            },
        },
    }


def test_flags_unowned_system_like_paths(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())

    result = evaluate_three_letter_system_enforcement(
        repo_root=tmp_path,
        changed_files=["scripts/run_unknown_governance.py"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
        generated_at="2026-04-14T00:00:00Z",
    )

    assert result["final_decision"] == "BLOCK"
    assert "UNOWNED_SYSTEM_LIKE_PATH" in result["violations"]


def test_reserved_paths_are_respected(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())

    result = evaluate_three_letter_system_enforcement(
        repo_root=tmp_path,
        changed_files=["docs/reviews/new_review.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
        generated_at="2026-04-14T00:00:00Z",
    )

    assert result["final_decision"] == "PASS"


def test_detects_ownership_drift(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    policy = _policy()
    policy["systems"]["PRG"] = {
        "owned_paths": ["scripts/run_contract_preflight.py"],
        "criticality": "high",
        "minimum_required_tests": ["tests/test_system_registry_guard.py"],
        "artifact_boundary_coverage_mandatory": False,
        "pytest_visibility_mandatory": False,
        "system_registry_review_mandatory": True,
    }

    result = evaluate_three_letter_system_enforcement(
        repo_root=tmp_path,
        changed_files=["scripts/run_contract_preflight.py"],
        policy=policy,
        registry_model=parse_system_registry(registry_path),
        generated_at="2026-04-14T00:00:00Z",
    )

    assert "OWNERSHIP_DRIFT" in result["violations"]


def test_detects_missing_required_gates(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    policy = _policy()
    policy["systems"]["TPA"]["minimum_required_tests"] = ["tests/test_contract_preflight.py"]

    result = evaluate_three_letter_system_enforcement(
        repo_root=tmp_path,
        changed_files=["scripts/run_contract_preflight.py"],
        policy=policy,
        registry_model=parse_system_registry(registry_path),
        generated_at="2026-04-14T00:00:00Z",
    )

    assert "MISSING_REQUIRED_GATES" in result["violations"]


def test_fail_closed_on_ambiguous_ownership(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    policy = _policy()
    policy["systems"]["PRG"] = {
        "owned_paths": ["scripts/"],
        "criticality": "high",
        "minimum_required_tests": ["tests/test_system_registry_guard.py"],
        "artifact_boundary_coverage_mandatory": False,
        "pytest_visibility_mandatory": False,
        "system_registry_review_mandatory": True,
    }

    result = evaluate_three_letter_system_enforcement(
        repo_root=tmp_path,
        changed_files=["scripts/run_contract_preflight.py"],
        policy=policy,
        registry_model=parse_system_registry(registry_path),
        generated_at="2026-04-14T00:00:00Z",
    )

    assert result["final_decision"] == "BLOCK"
    assert "AMBIGUOUS_SYSTEM_OWNERSHIP" in result["violations"]
