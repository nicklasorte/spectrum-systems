from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Phase 16 — Governance boundary schema and validation script
# ---------------------------------------------------------------------------

def test_governance_boundary_schema_exists():
    assert Path("ecosystem/spectrum-systems.file-types.schema.json").exists()


def test_governance_boundary_schema_valid():
    schema = json.loads(Path("ecosystem/spectrum-systems.file-types.schema.json").read_text())
    assert "allowed_extensions" in schema
    assert "allowed_root_directories" in schema
    assert "boundary_violations" in schema


def test_validate_governance_boundary_script_exists():
    assert Path("scripts/validate-governance-boundary.py").exists()


def test_phase_16_implementation_plan_exists():
    assert Path("docs/phase-16-implementation-plan.md").exists()


def test_phase_16_migration_guide_exists():
    assert Path("docs/phase-16-migration-guide.md").exists()


# ---------------------------------------------------------------------------
# Phase 17 — Ecosystem registry
# ---------------------------------------------------------------------------

def test_ecosystem_registry_is_list():
    registry = json.loads(Path("ecosystem/system-registry.json").read_text())
    assert isinstance(registry, list)
    assert len(registry) >= 1


def test_ecosystem_registry_has_spectrum_systems():
    registry = json.loads(Path("ecosystem/system-registry.json").read_text())
    repos = [r.get("repo", "") for r in registry]
    assert any("spectrum-systems" in r for r in repos)


def test_ecosystem_registry_governance_type():
    registry = json.loads(Path("ecosystem/system-registry.json").read_text())
    ss = next((r for r in registry if "spectrum-systems" in r.get("repo", "")), None)
    assert ss is not None
    assert ss.get("repo_type") == "governance"


# ---------------------------------------------------------------------------
# Phase 18 — Schema registry manifest
# ---------------------------------------------------------------------------

def test_schema_registry_manifest_exists():
    assert Path("contracts/governance/schema-registry-manifest.json").exists()


def test_schema_registry_manifest_valid():
    manifest = json.loads(Path("contracts/governance/schema-registry-manifest.json").read_text())
    assert "schemas" in manifest
    assert isinstance(manifest["schemas"], list)


# ---------------------------------------------------------------------------
# Phase 19 — Cross-repo scan policy
# ---------------------------------------------------------------------------

def test_cross_repo_scan_policy_exists():
    assert Path("contracts/governance/cross-repo-scan-policy.json").exists()


# ---------------------------------------------------------------------------
# Phase 20 — Downstream consent registry
# ---------------------------------------------------------------------------

def test_downstream_consent_registry_exists():
    assert Path("contracts/governance/downstream-consent-registry.json").exists()


# ---------------------------------------------------------------------------
# Phase 21 — Governance-guard activation record
# ---------------------------------------------------------------------------

def test_enforcement_activation_record_exists():
    assert Path("contracts/governance/enforcement-activation-record.json").exists()


def test_enforcement_activation_record_active():
    record = json.loads(Path("contracts/governance/enforcement-activation-record.json").read_text())
    assert record.get("status") == "active"


# ---------------------------------------------------------------------------
# Phase 22 — Violation response policy
# ---------------------------------------------------------------------------

def test_violation_response_policy_exists():
    assert Path("contracts/governance/violation-response-policy.json").exists()


def test_violation_response_policy_valid():
    policy = json.loads(Path("contracts/governance/violation-response-policy.json").read_text())
    assert "violation_classes" in policy
    assert isinstance(policy["violation_classes"], list)
    assert len(policy["violation_classes"]) > 0
