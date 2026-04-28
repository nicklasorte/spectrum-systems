from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.governance.system_registry_guard import parse_system_registry
from spectrum_systems.modules.governance.three_letter_system_enforcement import evaluate_three_letter_system_enforcement

REPO_ROOT = Path(__file__).resolve().parents[1]
_GOVERNANCE_FILES = [
    "spectrum_systems/modules/governance/three_letter_system_enforcement.py",
    "spectrum_systems/governance/registry_drift_validator.py",
    "scripts/run_three_letter_system_enforcement_audit.py",
]


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
                    "tests/test_artifact_boundary_workflow_pytest_policy_observation.py"
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

    assert result["final_decision"] == "FAIL"
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

    assert result["final_decision"] == "FAIL"
    assert "AMBIGUOUS_SYSTEM_OWNERSHIP" in result["violations"]


# ---------------------------------------------------------------------------
# Early-detection: authority leak guard on 3LS governance files themselves
# ---------------------------------------------------------------------------

def test_three_letter_system_enforcement_module_has_no_authority_leaks() -> None:
    """The 3LS enforcement module must not emit forbidden authority vocabulary.

    This test runs the authority_leak_guard logic directly against the
    governance files so violations are caught locally before CI. It is the
    canonical early-detection gate for the authority_shape_artifact_type and
    forbidden_value rule classes within the 3LS governance surface.
    """
    registry_path = REPO_ROOT / "contracts" / "governance" / "authority_registry.json"
    if not registry_path.exists():
        pytest.skip("authority_registry.json not found; skipping authority leak check")

    from scripts.authority_leak_rules import load_authority_registry, find_forbidden_vocabulary
    from scripts.authority_shape_detector import detect_authority_shapes

    registry = load_authority_registry(registry_path)

    all_violations: list[dict] = []
    for rel in _GOVERNANCE_FILES:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        all_violations.extend(find_forbidden_vocabulary(p, registry))
        all_violations.extend(detect_authority_shapes(p, registry))

    assert all_violations == [], (
        f"Authority leak violations found in 3LS governance files — "
        f"fix before CI: {json.dumps(all_violations, indent=2)}"
    )


def test_final_decision_values_do_not_use_control_vocabulary() -> None:
    """final_decision must use audit-outcome vocabulary (PASS/WARN/FAIL), not CDE control words.

    BLOCK and FREEZE are CDE authority values. Audit results must not use them.
    """
    schema_path = REPO_ROOT / "contracts" / "schemas" / "three_letter_system_enforcement_audit_result.schema.json"
    if not schema_path.exists():
        pytest.skip("schema file not found")

    schema = json.loads(schema_path.read_text())
    allowed = schema["properties"]["final_decision"]["enum"]

    forbidden_control_words = {"BLOCK", "FREEZE", "ALLOW", "PROMOTE"}
    leaking = forbidden_control_words & set(allowed)
    assert not leaking, (
        f"final_decision enum contains CDE control vocabulary: {leaking}. "
        f"Use audit-outcome words (PASS, WARN, FAIL) instead."
    )
