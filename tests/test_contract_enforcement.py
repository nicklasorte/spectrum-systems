"""
Tests for scripts/run_contract_enforcement.py.

Covers:
- valid contract pin set (all passes)
- missing contract in canonical manifest (contract-exists failure)
- version drift detection (version-pin failure)
- producer/consumer inconsistency (consumer-consistency warning)
- not-yet-enforceable repo handling
- dependency graph generation (structure and fields)
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_contract_enforcement.py"

# Import the module directly so we can unit-test individual functions.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_contract_enforcement import (  # noqa: E402
    build_contract_dependency_graph,
    check_consumer_consistency,
    check_repo_contracts,
    run_enforcement,
    load_ecosystem_registry,
    load_governance_manifests,
    load_standards_contracts,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _standards(contracts: list | None = None) -> Dict[str, dict]:
    base = [
        {
            "artifact_type": "alpha_contract",
            "schema_version": "1.0.0",
            "status": "stable",
            "intended_consumers": ["repo-a"],
        },
        {
            "artifact_type": "beta_contract",
            "schema_version": "2.0.0",
            "status": "stable",
            "intended_consumers": ["repo-b"],
        },
    ]
    entries = contracts if contracts is not None else base
    return {c["artifact_type"]: c for c in entries}


def _registry(repos: list | None = None) -> Dict[str, dict]:
    base = [
        {
            "repo_name": "repo-a",
            "repo_type": "operational_engine",
            "manifest_required": True,
        },
        {
            "repo_name": "repo-b",
            "repo_type": "operational_engine",
            "manifest_required": True,
        },
    ]
    entries = repos if repos is not None else base
    return {r["repo_name"]: r for r in entries}


def _manifest(repo_name: str, contracts: dict, system_id: str = "") -> dict:
    return {
        "repo_name": repo_name,
        "system_id": system_id or repo_name,
        "repo_type": "operational_engine",
        "governance_repo": "spectrum-systems",
        "governance_version": "1.0.0",
        "contracts": contracts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: check_repo_contracts
# ─────────────────────────────────────────────────────────────────────────────

def test_valid_contract_pins_produce_no_failures() -> None:
    """A manifest with valid, correctly-versioned contract pins should have no failures."""
    standards = _standards()
    manifest = _manifest("repo-a", {"alpha_contract": "1.0.0"})
    failures, warnings = check_repo_contracts("repo-a", "repo-a", manifest, standards)
    assert failures == []
    assert warnings == []


def test_missing_contract_in_standards_manifest() -> None:
    """Pinning a contract not in the standards manifest should produce a contract-exists failure."""
    standards = _standards()
    manifest = _manifest("repo-a", {"nonexistent_contract": "1.0.0"})
    failures, warnings = check_repo_contracts("repo-a", "repo-a", manifest, standards)
    assert len(failures) == 1
    f = failures[0]
    assert f["rule"] == "contract-exists"
    assert f["contract"] == "nonexistent_contract"
    assert f["repo"] == "repo-a"


def test_version_drift_detected() -> None:
    """Pinning a contract at the wrong version should produce a version-pin failure."""
    standards = _standards()
    manifest = _manifest("repo-a", {"alpha_contract": "0.9.0"})  # canonical is 1.0.0
    failures, warnings = check_repo_contracts("repo-a", "repo-a", manifest, standards)
    assert len(failures) == 1
    f = failures[0]
    assert f["rule"] == "version-pin"
    assert "alpha_contract" in f["contract"]
    assert "1.0.0" in f["error"]   # expected
    assert "0.9.0" in f["error"]   # found


def test_version_drift_message_contains_repo_and_system_id() -> None:
    """Enforcement output must carry repo and system_id for traceability."""
    standards = _standards()
    manifest = _manifest("repo-a", {"alpha_contract": "0.5.0"}, system_id="SYS-ALPHA")
    failures, _ = check_repo_contracts("repo-a", "SYS-ALPHA", manifest, standards)
    assert failures[0]["repo"] == "repo-a"
    assert failures[0]["system_id"] == "SYS-ALPHA"


def test_multiple_contracts_both_valid() -> None:
    """Multiple valid pins should produce no failures."""
    standards = _standards()
    manifest = _manifest("repo-x", {"alpha_contract": "1.0.0", "beta_contract": "2.0.0"})
    failures, warnings = check_repo_contracts("repo-x", "repo-x", manifest, standards)
    assert failures == []


def test_empty_contracts_section_is_valid() -> None:
    """A manifest with no contracts declared should be valid."""
    manifest = _manifest("repo-a", {})
    failures, warnings = check_repo_contracts("repo-a", "repo-a", manifest, _standards())
    assert failures == []
    assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: check_consumer_consistency
# ─────────────────────────────────────────────────────────────────────────────

def test_consumer_consistency_pass_when_contract_declared() -> None:
    """No warning if intended_consumer properly declares the contract."""
    standards = _standards()
    registry = _registry()
    manifests = {
        "repo-a": _manifest("repo-a", {"alpha_contract": "1.0.0"}),
        "repo-b": _manifest("repo-b", {"beta_contract": "2.0.0"}),
    }
    failures, warnings = check_consumer_consistency(standards, manifests, registry)
    assert failures == []
    assert warnings == []


def test_consumer_consistency_warning_when_contract_missing() -> None:
    """A warning should be raised if an intended_consumer doesn't declare the contract."""
    standards = _standards()
    registry = _registry()
    # repo-a is supposed to consume alpha_contract but doesn't declare it
    manifests = {
        "repo-a": _manifest("repo-a", {}),
        "repo-b": _manifest("repo-b", {"beta_contract": "2.0.0"}),
    }
    failures, warnings = check_consumer_consistency(standards, manifests, registry)
    assert failures == []
    assert len(warnings) == 1
    w = warnings[0]
    assert w["rule"] == "consumer-consistency"
    assert w["repo"] == "repo-a"
    assert w["contract"] == "alpha_contract"


def test_consumer_consistency_skips_repo_without_manifest() -> None:
    """Intended consumers without a governance manifest are skipped (not-yet-enforceable)."""
    standards = _standards()
    registry = _registry()
    # repo-a has no manifest yet — should be skipped, not warned
    manifests = {
        "repo-b": _manifest("repo-b", {"beta_contract": "2.0.0"}),
    }
    failures, warnings = check_consumer_consistency(standards, manifests, registry)
    # Only repo-b is checked; repo-a is absent from manifests → skip
    consumer_repos = {w["repo"] for w in warnings}
    assert "repo-a" not in consumer_repos


def test_consumer_consistency_skips_non_manifest_required_repos() -> None:
    """Repos with manifest_required=false are excluded from consumer checks."""
    standards = _standards([
        {
            "artifact_type": "gamma_contract",
            "schema_version": "1.0.0",
            "status": "stable",
            "intended_consumers": ["governance-repo"],
        }
    ])
    registry = {"governance-repo": {"repo_name": "governance-repo", "manifest_required": False}}
    manifests: dict = {}
    failures, warnings = check_consumer_consistency(standards, manifests, registry)
    assert failures == []
    assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: not-yet-enforceable handling
# ─────────────────────────────────────────────────────────────────────────────

def test_not_yet_enforceable_repo_is_not_a_failure() -> None:
    """A governed repo without a governance manifest should not produce any failures."""
    registry = _registry()
    standards = _standards()
    manifests: dict = {}  # no manifests present

    failures, warnings, nyes, per_repo = run_enforcement(registry, standards, manifests)
    assert failures == []
    assert "repo-a" in nyes
    assert "repo-b" in nyes


def test_not_yet_enforceable_repos_appear_in_dependency_graph() -> None:
    """Not-yet-enforceable repos must appear in the dependency graph with the correct status."""
    registry = _registry()
    standards = _standards()
    manifests: dict = {}
    _, _, nyes, per_repo = run_enforcement(registry, standards, manifests)

    graph = build_contract_dependency_graph(registry, manifests, standards, per_repo, "2026-03-17T00:00:00Z")
    statuses = {r["repo_name"]: r["validation_status"] for r in graph["repos"]}
    assert statuses["repo-a"] == "not_yet_enforceable"
    assert statuses["repo-b"] == "not_yet_enforceable"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: dependency graph structure
# ─────────────────────────────────────────────────────────────────────────────

def test_dependency_graph_required_fields() -> None:
    """The dependency graph must contain all required top-level fields."""
    registry = _registry()
    standards = _standards()
    manifests = {
        "repo-a": _manifest("repo-a", {"alpha_contract": "1.0.0"}),
    }
    _, _, _, per_repo = run_enforcement(registry, standards, manifests)
    graph = build_contract_dependency_graph(registry, manifests, standards, per_repo, "2026-03-17T00:00:00Z")

    assert "schema_version" in graph
    assert "generated_at" in graph
    assert "source_manifest" in graph
    assert "repos" in graph
    assert "contract_index" in graph


def test_dependency_graph_repo_entry_fields() -> None:
    """Each repo entry in the graph must carry the required fields."""
    registry = _registry()
    standards = _standards()
    manifests = {
        "repo-a": _manifest("repo-a", {"alpha_contract": "1.0.0"}, system_id="SYS-A"),
        "repo-b": _manifest("repo-b", {"beta_contract": "2.0.0"}, system_id="SYS-B"),
    }
    _, _, _, per_repo = run_enforcement(registry, standards, manifests)
    graph = build_contract_dependency_graph(registry, manifests, standards, per_repo, "2026-03-17T00:00:00Z")

    for repo in graph["repos"]:
        assert "repo_name" in repo
        assert "repo_type" in repo
        assert "system_id" in repo
        assert "contracts_consumed" in repo
        assert "contracts_produced" in repo
        assert "validation_status" in repo


def test_dependency_graph_contract_index_reverse_lookup() -> None:
    """The contract_index must be a reverse lookup from contract to consumers."""
    registry = _registry()
    standards = _standards()
    manifests = {
        "repo-a": _manifest("repo-a", {"alpha_contract": "1.0.0"}),
        "repo-b": _manifest("repo-b", {"alpha_contract": "1.0.0", "beta_contract": "2.0.0"}),
    }
    _, _, _, per_repo = run_enforcement(registry, standards, manifests)
    graph = build_contract_dependency_graph(registry, manifests, standards, per_repo, "2026-03-17T00:00:00Z")

    idx = graph["contract_index"]
    assert "alpha_contract" in idx
    assert set(idx["alpha_contract"]["consumers"]) == {"repo-a", "repo-b"}
    assert "beta_contract" in idx
    assert idx["beta_contract"]["consumers"] == ["repo-b"]


def test_dependency_graph_drift_flag() -> None:
    """A drifted pin should have drift=True in the consumed contracts list."""
    standards = _standards()
    registry = _registry()
    manifests = {
        "repo-a": _manifest("repo-a", {"alpha_contract": "0.9.0"}),  # drift
        "repo-b": _manifest("repo-b", {"beta_contract": "2.0.0"}),   # no drift
    }
    _, _, _, per_repo = run_enforcement(registry, standards, manifests)
    graph = build_contract_dependency_graph(registry, manifests, standards, per_repo, "2026-03-17T00:00:00Z")

    repo_a = next(r for r in graph["repos"] if r["repo_name"] == "repo-a")
    alpha = next(c for c in repo_a["contracts_consumed"] if c["contract"] == "alpha_contract")
    assert alpha["drift"] is True
    assert alpha["pinned_version"] == "0.9.0"
    assert alpha["canonical_version"] == "1.0.0"

    repo_b = next(r for r in graph["repos"] if r["repo_name"] == "repo-b")
    beta = next(c for c in repo_b["contracts_consumed"] if c["contract"] == "beta_contract")
    assert beta["drift"] is False


def test_dependency_graph_validation_status_fail() -> None:
    """A repo with a contract failure should have validation_status='fail' in the graph."""
    standards = _standards()
    registry = _registry()
    manifests = {
        "repo-a": _manifest("repo-a", {"nonexistent_contract": "1.0.0"}),
        "repo-b": _manifest("repo-b", {"beta_contract": "2.0.0"}),
    }
    failures, warnings, nyes, per_repo = run_enforcement(registry, standards, manifests)
    graph = build_contract_dependency_graph(registry, manifests, standards, per_repo, "2026-03-17T00:00:00Z")

    repo_a = next(r for r in graph["repos"] if r["repo_name"] == "repo-a")
    assert repo_a["validation_status"] == "fail"


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: run against the actual repo data
# ─────────────────────────────────────────────────────────────────────────────

def test_enforcement_script_runs_successfully() -> None:
    """The enforcement script should exit 0 on the current example manifests."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    # Warnings are acceptable; hard failures (exit 1) are not.
    assert result.returncode == 0, (
        f"Contract enforcement script exited {result.returncode}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_enforcement_script_generates_contract_graph(tmp_path: Path) -> None:
    """Running the script should produce the contract-dependency-graph.json artifact."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0

    graph_path = REPO_ROOT / "governance" / "reports" / "contract-dependency-graph.json"
    assert graph_path.exists(), "contract-dependency-graph.json was not created"

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert "repos" in graph
    assert "contract_index" in graph
    assert "schema_version" in graph
    assert "generated_at" in graph


def test_enforcement_script_generates_enforcement_report() -> None:
    """Running the script should produce the contract-enforcement-report.md."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0

    report_path = REPO_ROOT / "docs" / "governance-reports" / "contract-enforcement-report.md"
    assert report_path.exists(), "contract-enforcement-report.md was not created"

    content = report_path.read_text(encoding="utf-8")
    assert "# Cross-Repo Contract Enforcement Report" in content
    assert "## Summary" in content
    assert "## Repos Inspected" in content
    assert "## Enforcement Failures" in content
    assert "## Warnings" in content
    assert "## Not Yet Enforceable" in content


def test_enforcement_output_format_for_failures() -> None:
    """Failure lines must match the canonical [contract-enforcement] format."""
    standards = _standards()
    registry = _registry()
    manifests = {
        "repo-a": _manifest("repo-a", {"alpha_contract": "0.5.0"}, system_id="SYS-A"),
    }
    failures, _, _, _ = run_enforcement(registry, standards, manifests)
    assert failures, "Expected at least one failure"
    from run_contract_enforcement import format_enforcement_line
    line = format_enforcement_line(failures[0])
    assert line.startswith("[contract-enforcement]")
    assert "repo=repo-a" in line
    assert "system_id=SYS-A" in line
    assert "rule=version-pin" in line


def test_enforcement_no_error_failures_on_example_manifests() -> None:
    """The seeded example governance manifests must not trigger enforcement failures."""
    from run_contract_enforcement import (
        load_ecosystem_registry,
        load_governance_manifests,
        load_standards_contracts,
    )
    registry = load_ecosystem_registry()
    standards = load_standards_contracts()
    manifests = load_governance_manifests()

    failures, warnings, nyes, _ = run_enforcement(registry, standards, manifests)
    assert failures == [], (
        "Enforcement failures detected on example manifests:\n"
        + "\n".join(
            f"  repo={f['repo']} contract={f['contract']} rule={f['rule']} error={f['error']}"
            for f in failures
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Integration test: canonical consumer-consistency drift guard
# ─────────────────────────────────────────────────────────────────────────────

def test_canonical_intended_consumers_are_declared_by_governed_repos() -> None:
    """Every intended consumer with an enforceable manifest must pin the contract."""
    standards = load_standards_contracts()
    registry = load_ecosystem_registry()
    manifests = load_governance_manifests()

    _, warnings = check_consumer_consistency(standards, manifests, registry)

    consumer_warnings = [w for w in warnings if w.get("rule") == "consumer-consistency"]
    assert consumer_warnings == []


def test_standards_manifest_registers_bbc_eval_governance_contracts() -> None:
    standards = load_standards_contracts()
    for contract in (
        "eval_dataset",
        "eval_admission_policy",
        "eval_registry_snapshot",
    ):
        assert contract in standards
        assert standards[contract]["schema_version"] == "1.0.0"


def test_standards_manifest_registers_enforcement_result_contract() -> None:
    standards = load_standards_contracts()
    assert "enforcement_result" in standards
    assert standards["enforcement_result"]["schema_version"] == "1.1.0"
    assert standards["enforcement_result"]["example_path"] == "contracts/examples/enforcement_result.json"
