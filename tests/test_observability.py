"""
Tests for the Ecosystem Observability Layer.

Covers:
- generate_ecosystem_health_report.py:
  - maturity scoring logic (all states per category)
  - score aggregation and level mapping
  - health summary computation
  - per-repo record building
  - missing governance artifact detection
  - write outputs (JSON and markdown files produced)
- generate_ecosystem_architecture_graph.py:
  - node building from registry
  - edge building (consumes, layer_depends_on)
  - write outputs (JSON and mmd files produced)
- JSON schema validation of generated artifacts
- docs/governance-observability.md existence and content
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import generate_ecosystem_health_report as health_mod  # noqa: E402
import generate_ecosystem_architecture_graph as arch_mod  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_repo_entry(
    repo_name: str,
    repo_type: str = "operational_engine",
    status: str = "active",
    layer: str = "Layer 3",
    manifest_required: bool = True,
    contracts: Optional[List[str]] = None,
    system_id: Optional[str] = None,
    description: str = "An operational engine for spectrum automation workflows.",
) -> dict:
    entry = {
        "repo_name": repo_name,
        "repo_type": repo_type,
        "status": status,
        "layer": layer,
        "manifest_required": manifest_required,
        "contracts": contracts or [],
        "description": description,
    }
    if system_id is not None:
        entry["system_id"] = system_id
    return entry


def _make_manifest(repo_name: str, contracts: Optional[Dict[str, str]] = None) -> dict:
    return {
        "system_id": repo_name,
        "repo_name": repo_name,
        "repo_type": "operational_engine",
        "contracts": contracts or {"sample_contract": "1.0.0"},
    }


def _make_standards(artifact_types: Optional[List[str]] = None) -> Dict[str, dict]:
    types = artifact_types or ["sample_contract", "other_contract"]
    return {
        t: {"artifact_type": t, "schema_version": "1.0.0", "stability": "stable"}
        for t in types
    }


# ─────────────────────────────────────────────────────────────────────────────
# Maturity scoring — governance_artifacts category
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreGovernanceArtifacts:
    def test_compliant_when_manifest_not_required(self):
        entry = _make_repo_entry("gov-repo", manifest_required=False)
        result = health_mod.score_governance_artifacts("gov-repo", entry, {})
        assert result == "compliant"

    def test_compliant_when_manifest_present(self):
        entry = _make_repo_entry("engine-a", manifest_required=True)
        manifests = {"engine-a": _make_manifest("engine-a")}
        result = health_mod.score_governance_artifacts("engine-a", entry, manifests)
        assert result == "compliant"

    def test_partial_when_manifest_missing_but_planned(self):
        entry = _make_repo_entry("engine-b", manifest_required=True, status="planned")
        result = health_mod.score_governance_artifacts("engine-b", entry, {})
        assert result == "partial"

    def test_partial_when_manifest_missing_but_experimental(self):
        entry = _make_repo_entry("engine-c", manifest_required=True, status="experimental")
        result = health_mod.score_governance_artifacts("engine-c", entry, {})
        assert result == "partial"

    def test_missing_when_active_but_no_manifest(self):
        entry = _make_repo_entry("engine-d", manifest_required=True, status="active")
        result = health_mod.score_governance_artifacts("engine-d", entry, {})
        assert result == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# Maturity scoring — contract_compliance category
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreContractCompliance:
    def test_compliant_when_pass(self):
        graph = {"engine-a": {"validation_status": "pass"}}
        result = health_mod.score_contract_compliance("engine-a", graph)
        assert result == "compliant"

    def test_partial_when_warning(self):
        graph = {"engine-a": {"validation_status": "warning"}}
        result = health_mod.score_contract_compliance("engine-a", graph)
        assert result == "partial"

    def test_partial_when_not_yet_enforceable(self):
        graph = {"engine-a": {"validation_status": "not_yet_enforceable"}}
        result = health_mod.score_contract_compliance("engine-a", graph)
        assert result == "partial"

    def test_partial_when_governance_repo(self):
        graph = {"gov-repo": {"validation_status": "governance-repo"}}
        result = health_mod.score_contract_compliance("gov-repo", graph)
        assert result == "partial"

    def test_missing_when_repo_not_in_graph(self):
        result = health_mod.score_contract_compliance("unknown-repo", {})
        assert result == "missing"

    def test_missing_when_fail(self):
        graph = {"engine-a": {"validation_status": "fail"}}
        result = health_mod.score_contract_compliance("engine-a", graph)
        assert result == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# Maturity scoring — schema_alignment category
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreSchemaAlignment:
    def test_compliant_when_no_manifest_required(self):
        entry = _make_repo_entry("gov-repo", manifest_required=False)
        result = health_mod.score_schema_alignment("gov-repo", entry, {}, {})
        assert result == "compliant"

    def test_missing_when_manifest_required_but_absent(self):
        entry = _make_repo_entry("engine-a", manifest_required=True)
        result = health_mod.score_schema_alignment("engine-a", entry, {}, {})
        assert result == "missing"

    def test_compliant_when_all_versions_match(self):
        entry = _make_repo_entry("engine-a", manifest_required=True)
        manifests = {"engine-a": _make_manifest("engine-a", {"sample_contract": "1.0.0"})}
        standards = _make_standards(["sample_contract"])
        result = health_mod.score_schema_alignment("engine-a", entry, standards, manifests)
        assert result == "compliant"

    def test_missing_when_contract_not_in_standards(self):
        entry = _make_repo_entry("engine-a", manifest_required=True)
        manifests = {"engine-a": _make_manifest("engine-a", {"unknown_contract": "1.0.0"})}
        standards = _make_standards(["other_contract"])
        result = health_mod.score_schema_alignment("engine-a", entry, standards, manifests)
        assert result == "missing"

    def test_missing_when_version_drift(self):
        entry = _make_repo_entry("engine-a", manifest_required=True)
        manifests = {"engine-a": _make_manifest("engine-a", {"sample_contract": "2.0.0"})}
        standards = _make_standards(["sample_contract"])  # canonical is 1.0.0
        result = health_mod.score_schema_alignment("engine-a", entry, standards, manifests)
        assert result == "missing"

    def test_partial_when_some_contracts_mismatch(self):
        entry = _make_repo_entry("engine-a", manifest_required=True)
        manifests = {
            "engine-a": _make_manifest(
                "engine-a",
                {"sample_contract": "1.0.0", "other_contract": "9.9.9"},
            )
        }
        standards = _make_standards(["sample_contract", "other_contract"])
        result = health_mod.score_schema_alignment("engine-a", entry, standards, manifests)
        assert result == "partial"


# ─────────────────────────────────────────────────────────────────────────────
# Maturity scoring — ci_enforcement category
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreCiEnforcement:
    def test_compliant_for_governance_repo(self):
        entry = _make_repo_entry("gov-repo", repo_type="governance")
        result = health_mod.score_ci_enforcement("gov-repo", entry)
        assert result == "compliant"

    def test_compliant_for_active_engine(self):
        entry = _make_repo_entry("engine-a", status="active")
        result = health_mod.score_ci_enforcement("engine-a", entry)
        assert result == "compliant"

    def test_partial_for_experimental(self):
        entry = _make_repo_entry("engine-a", status="experimental")
        result = health_mod.score_ci_enforcement("engine-a", entry)
        assert result == "partial"

    def test_missing_for_planned(self):
        entry = _make_repo_entry("engine-a", status="planned")
        result = health_mod.score_ci_enforcement("engine-a", entry)
        assert result == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# Maturity scoring — evaluation_evidence category
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreEvaluationEvidence:
    def test_missing_when_no_system_or_maturity_entry(self):
        result = health_mod.score_evaluation_evidence("engine-a", None, None)
        assert result == "missing"

    def test_compliant_when_maturity_level_5(self):
        maturity = {"system_id": "engine-a", "current_level": 5, "evidence": []}
        result = health_mod.score_evaluation_evidence("engine-a", None, maturity)
        assert result == "compliant"

    def test_partial_when_maturity_level_3(self):
        maturity = {"system_id": "engine-a", "current_level": 3, "evidence": []}
        result = health_mod.score_evaluation_evidence("engine-a", None, maturity)
        assert result == "partial"

    def test_partial_when_evidence_present_low_level(self):
        maturity = {"system_id": "engine-a", "current_level": 2, "evidence": ["some evidence"]}
        result = health_mod.score_evaluation_evidence("engine-a", None, maturity)
        assert result == "partial"

    def test_missing_when_level_below_3_no_evidence(self):
        maturity = {"system_id": "engine-a", "current_level": 2, "evidence": []}
        result = health_mod.score_evaluation_evidence("engine-a", None, maturity)
        assert result == "missing"

    def test_uses_system_entry_when_no_maturity(self):
        system = {"system_id": "engine-a", "maturity_level": 6}
        result = health_mod.score_evaluation_evidence("engine-a", system, None)
        assert result == "compliant"


# ─────────────────────────────────────────────────────────────────────────────
# Maturity scoring — documentation category
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreDocumentation:
    def test_compliant_with_long_description(self):
        entry = {"description": "A long and informative description of this operational engine."}
        result = health_mod.score_documentation(entry)
        assert result == "compliant"

    def test_partial_with_short_description(self):
        entry = {"description": "Short desc."}
        result = health_mod.score_documentation(entry)
        assert result == "partial"

    def test_missing_with_no_description(self):
        result = health_mod.score_documentation({})
        assert result == "missing"

    def test_missing_with_empty_description(self):
        result = health_mod.score_documentation({"description": ""})
        assert result == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# Maturity level computation
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeMaturityLevel:
    def test_all_compliant_is_level_10(self):
        scores = {cat: "compliant" for cat in health_mod.MATURITY_CATEGORIES}
        raw, max_raw = health_mod.compute_maturity_score(scores)
        level = health_mod.raw_to_maturity_level(raw, max_raw)
        assert level == 10

    def test_all_missing_is_level_1(self):
        scores = {cat: "missing" for cat in health_mod.MATURITY_CATEGORIES}
        raw, max_raw = health_mod.compute_maturity_score(scores)
        level = health_mod.raw_to_maturity_level(raw, max_raw)
        assert level == 1

    def test_all_partial_is_between_1_and_10(self):
        scores = {cat: "partial" for cat in health_mod.MATURITY_CATEGORIES}
        raw, max_raw = health_mod.compute_maturity_score(scores)
        level = health_mod.raw_to_maturity_level(raw, max_raw)
        assert 1 <= level <= 10

    def test_level_clamped_minimum_1(self):
        level = health_mod.raw_to_maturity_level(0, 20)
        assert level == 1

    def test_level_clamped_maximum_10(self):
        level = health_mod.raw_to_maturity_level(20, 20)
        assert level == 10


# ─────────────────────────────────────────────────────────────────────────────
# Health summary computation
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeHealthSummary:
    def _make_record(
        self,
        repo_name: str,
        governance_status: str = "compliant",
        contract_status: str = "pass",
        schema_status: str = "compliant",
        ci_status: str = "compliant",
        cat_gov: str = "compliant",
        maturity_level: int = 8,
    ) -> dict:
        return {
            "repo_name": repo_name,
            "system_id": repo_name,
            "repo_type": "operational_engine",
            "architecture_layer": "Layer 3",
            "status": "active",
            "governance_status": governance_status,
            "contract_status": contract_status,
            "schema_status": schema_status,
            "ci_status": ci_status,
            "maturity_score": {
                "raw": 10,
                "max": 20,
                "categories": {
                    cat: cat_gov if cat == "governance_artifacts" else "compliant"
                    for cat in health_mod.MATURITY_CATEGORIES
                },
            },
            "maturity_level": maturity_level,
            "notes": "",
        }

    def test_healthy_when_all_pass(self):
        records = [
            self._make_record("repo-a"),
            self._make_record("repo-b"),
        ]
        summary = health_mod.compute_health_summary(records)
        assert summary["overall_health"] == "healthy"

    def test_failing_when_governance_fail(self):
        records = [self._make_record("repo-a", governance_status="fail")]
        summary = health_mod.compute_health_summary(records)
        assert summary["overall_health"] == "failing"

    def test_failing_when_contract_fail(self):
        records = [self._make_record("repo-a", contract_status="fail")]
        summary = health_mod.compute_health_summary(records)
        assert summary["overall_health"] == "failing"

    def test_warning_when_contract_warning(self):
        records = [self._make_record("repo-a", contract_status="warning")]
        summary = health_mod.compute_health_summary(records)
        assert summary["overall_health"] == "warning"

    def test_warning_when_not_yet_enforceable(self):
        records = [self._make_record("repo-a", contract_status="not_yet_enforceable")]
        summary = health_mod.compute_health_summary(records)
        assert summary["overall_health"] == "warning"

    def test_repos_missing_artifacts_detected(self):
        records = [self._make_record("repo-a", cat_gov="missing")]
        summary = health_mod.compute_health_summary(records)
        assert "repo-a" in summary["repos_missing_required_artifacts"]

    def test_total_repos_correct(self):
        records = [self._make_record(f"repo-{i}") for i in range(5)]
        summary = health_mod.compute_health_summary(records)
        assert summary["total_repos"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# Build repo record
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildRepoRecord:
    def test_compliant_repo_builds_correctly(self):
        repo_entry = _make_repo_entry(
            "engine-a",
            manifest_required=True,
            system_id="engine-a",
        )
        manifests = {"engine-a": _make_manifest("engine-a", {"sample_contract": "1.0.0"})}
        standards = _make_standards(["sample_contract"])
        contract_graph_repos = {"engine-a": {"validation_status": "pass", "failures": [], "warnings": []}}
        system_entry = {"system_id": "engine-a", "maturity_level": 5}
        maturity_entry = {"system_id": "engine-a", "current_level": 5, "evidence": ["some"]}

        record = health_mod.build_repo_record(
            repo_name="engine-a",
            repo_entry=repo_entry,
            system_entry=system_entry,
            maturity_entry=maturity_entry,
            contract_graph_repos=contract_graph_repos,
            standards=standards,
            manifests=manifests,
            policy_results_by_repo={},
        )

        assert record["repo_name"] == "engine-a"
        assert record["governance_status"] == "compliant"
        assert record["contract_status"] == "pass"
        assert record["schema_status"] == "compliant"
        assert record["maturity_level"] == 10
        assert "categories" in record["maturity_score"]

    def test_missing_manifest_detected(self):
        repo_entry = _make_repo_entry("engine-b", manifest_required=True, status="active")
        record = health_mod.build_repo_record(
            repo_name="engine-b",
            repo_entry=repo_entry,
            system_entry=None,
            maturity_entry=None,
            contract_graph_repos={},
            standards={},
            manifests={},
            policy_results_by_repo={},
        )
        assert record["maturity_score"]["categories"]["governance_artifacts"] == "missing"

    def test_policy_failure_sets_governance_fail(self):
        repo_entry = _make_repo_entry("engine-c", manifest_required=False)
        policy_results = [
            {
                "policy_id": "GOV-001",
                "severity": "error",
                "status": "fail",
                "subject": "engine-c",
                "message": "Governance failure",
            }
        ]
        record = health_mod.build_repo_record(
            repo_name="engine-c",
            repo_entry=repo_entry,
            system_entry=None,
            maturity_entry=None,
            contract_graph_repos={},
            standards={},
            manifests={},
            policy_results_by_repo={"engine-c": policy_results},
        )
        assert record["governance_status"] == "fail"

    def test_not_yet_enforceable_when_no_graph_and_manifest_required(self):
        repo_entry = _make_repo_entry("engine-d", manifest_required=True, status="active")
        manifests = {"engine-d": _make_manifest("engine-d")}
        record = health_mod.build_repo_record(
            repo_name="engine-d",
            repo_entry=repo_entry,
            system_entry=None,
            maturity_entry=None,
            contract_graph_repos={},
            standards={},
            manifests=manifests,
            policy_results_by_repo={},
        )
        assert record["contract_status"] == "not_yet_enforceable"


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end: generate_ecosystem_health_report.main()
# ─────────────────────────────────────────────────────────────────────────────

class TestEcosystemHealthReportGeneration:
    def test_main_returns_zero(self):
        exit_code = health_mod.main()
        assert exit_code == 0

    def test_health_json_exists(self):
        health_mod.main()
        assert health_mod.HEALTH_JSON_PATH.is_file(), "ecosystem-health.json was not generated"

    def test_health_json_valid_schema(self):
        health_mod.main()
        schema_path = REPO_ROOT / "governance" / "schemas" / "ecosystem-health.schema.json"
        assert schema_path.is_file(), "ecosystem-health.schema.json is missing"

        report = json.loads(health_mod.HEALTH_JSON_PATH.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)

    def test_health_json_has_required_fields(self):
        health_mod.main()
        report = json.loads(health_mod.HEALTH_JSON_PATH.read_text(encoding="utf-8"))
        assert "schema_version" in report
        assert "generated_at" in report
        assert "summary" in report
        assert "repos" in report
        assert isinstance(report["repos"], list)
        assert len(report["repos"]) > 0

    def test_each_repo_record_has_required_fields(self):
        health_mod.main()
        report = json.loads(health_mod.HEALTH_JSON_PATH.read_text(encoding="utf-8"))
        required = [
            "repo_name", "repo_type", "architecture_layer",
            "governance_status", "contract_status", "schema_status",
            "ci_status", "maturity_score", "maturity_level",
        ]
        for rec in report["repos"]:
            for field in required:
                assert field in rec, f"repo {rec.get('repo_name')} missing field '{field}'"

    def test_health_report_md_exists(self):
        health_mod.main()
        assert health_mod.HEALTH_REPORT_PATH.is_file(), "ecosystem-health-report.md was not generated"

    def test_health_report_md_contains_key_sections(self):
        health_mod.main()
        content = health_mod.HEALTH_REPORT_PATH.read_text(encoding="utf-8")
        assert "# Ecosystem Health Report" in content
        assert "## Governance Compliance" in content
        assert "## Contract Alignment" in content
        assert "## Repository Coverage" in content

    def test_dashboard_md_exists(self):
        health_mod.main()
        assert health_mod.DASHBOARD_PATH.is_file(), "ecosystem-dashboard.md was not generated"

    def test_dashboard_md_contains_table(self):
        health_mod.main()
        content = health_mod.DASHBOARD_PATH.read_text(encoding="utf-8")
        assert "# Ecosystem Dashboard" in content
        assert "| Repo |" in content


# ─────────────────────────────────────────────────────────────────────────────
# Architecture graph — node builders
# ─────────────────────────────────────────────────────────────────────────────

class TestArchGraphNodes:
    def test_build_repo_nodes(self):
        repos = [
            {"repo_name": "engine-a", "repo_type": "operational_engine", "layer": "Layer 3", "system_id": "engine-a", "status": "active"},
            {"repo_name": "gov-repo", "repo_type": "governance", "layer": "Layer 2", "system_id": "", "status": "active"},
        ]
        nodes = arch_mod.build_nodes(repos)
        assert len(nodes) == 2
        ids = {n["id"] for n in nodes}
        assert "engine-a" in ids
        assert "gov-repo" in ids
        for node in nodes:
            assert node["node_type"] == "repository"

    def test_build_contract_nodes(self):
        contracts = [
            {"artifact_type": "contract_a", "schema_version": "1.0.0", "stability": "stable"},
            {"artifact_type": "contract_b", "schema_version": "2.0.0", "stability": "experimental"},
        ]
        nodes = arch_mod.build_contract_nodes(contracts)
        assert len(nodes) == 2
        ids = {n["id"] for n in nodes}
        assert "contract_a" in ids
        assert "contract_b" in ids
        for node in nodes:
            assert node["node_type"] == "contract"

    def test_repo_nodes_sorted_by_name(self):
        repos = [
            {"repo_name": "z-engine", "repo_type": "operational_engine", "layer": "Layer 3", "system_id": "", "status": "active"},
            {"repo_name": "a-engine", "repo_type": "operational_engine", "layer": "Layer 3", "system_id": "", "status": "active"},
        ]
        nodes = arch_mod.build_nodes(repos)
        assert nodes[0]["id"] == "a-engine"
        assert nodes[1]["id"] == "z-engine"


# ─────────────────────────────────────────────────────────────────────────────
# Architecture graph — edge builders
# ─────────────────────────────────────────────────────────────────────────────

class TestArchGraphEdges:
    def test_consumes_edge_created_from_registry(self):
        repos = [
            _make_repo_entry("engine-a", contracts=["contract_a"], layer="Layer 3"),
        ]
        contract_ids = {"contract_a"}
        edges = arch_mod.build_edges(repos, {}, contract_ids)
        consumes = [e for e in edges if e["relationship"] == "consumes"]
        assert any(e["from"] == "engine-a" and e["to"] == "contract_a" for e in consumes)

    def test_produces_edge_from_contract_graph(self):
        repos = [_make_repo_entry("engine-a", layer="Layer 3")]
        contract_graph = {
            "repos": [
                {
                    "repo_name": "engine-a",
                    "contracts_consumed": [],
                    "contracts_produced": [{"contract": "contract_a"}],
                }
            ]
        }
        contract_ids = {"contract_a"}
        edges = arch_mod.build_edges(repos, contract_graph, contract_ids)
        produces = [e for e in edges if e["relationship"] == "produces"]
        assert any(e["from"] == "engine-a" and e["to"] == "contract_a" for e in produces)

    def test_layer_depends_on_edge_created(self):
        repos = [
            _make_repo_entry("pipeline", repo_type="pipeline", layer="Layer 4"),
            _make_repo_entry("engine-a", layer="Layer 3"),
        ]
        edges = arch_mod.build_edges(repos, {}, set())
        layer_edges = [e for e in edges if e["relationship"] == "layer_depends_on"]
        assert any(
            e["from"] == "pipeline" and e["to"] == "engine-a"
            for e in layer_edges
        )

    def test_no_duplicate_edges(self):
        # Same contract declared in both registry and contract graph
        repos = [_make_repo_entry("engine-a", contracts=["contract_a"], layer="Layer 3")]
        contract_graph = {
            "repos": [
                {
                    "repo_name": "engine-a",
                    "contracts_consumed": [{"contract": "contract_a"}],
                    "contracts_produced": [],
                }
            ]
        }
        contract_ids = {"contract_a"}
        edges = arch_mod.build_edges(repos, contract_graph, contract_ids)
        consumes = [e for e in edges if e["relationship"] == "consumes" and e["from"] == "engine-a" and e["to"] == "contract_a"]
        assert len(consumes) == 1, "duplicate consumes edge detected"

    def test_unknown_contract_not_added(self):
        repos = [_make_repo_entry("engine-a", contracts=["unknown_contract"], layer="Layer 3")]
        edges = arch_mod.build_edges(repos, {}, {"known_contract"})
        assert not any(e["to"] == "unknown_contract" for e in edges)


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end: generate_ecosystem_architecture_graph.main()
# ─────────────────────────────────────────────────────────────────────────────

class TestEcosystemArchGraphGeneration:
    def test_main_returns_zero(self):
        exit_code = arch_mod.main()
        assert exit_code == 0

    def test_graph_json_exists(self):
        arch_mod.main()
        assert arch_mod.OUTPUT_JSON.is_file(), "ecosystem-architecture-graph.json was not generated"

    def test_graph_json_valid_schema(self):
        arch_mod.main()
        schema_path = REPO_ROOT / "governance" / "schemas" / "ecosystem-architecture-graph.schema.json"
        assert schema_path.is_file(), "ecosystem-architecture-graph.schema.json is missing"
        graph = json.loads(arch_mod.OUTPUT_JSON.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(graph)

    def test_graph_json_has_nodes_and_edges(self):
        arch_mod.main()
        graph = json.loads(arch_mod.OUTPUT_JSON.read_text(encoding="utf-8"))
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]["repositories"]) > 0
        assert len(graph["nodes"]["contracts"]) > 0
        assert len(graph["edges"]) > 0

    def test_mermaid_file_exists(self):
        arch_mod.main()
        assert arch_mod.OUTPUT_MERMAID.is_file(), "ecosystem-architecture-graph.mmd was not generated"

    def test_mermaid_file_starts_with_graph_lr(self):
        arch_mod.main()
        content = arch_mod.OUTPUT_MERMAID.read_text(encoding="utf-8")
        assert content.startswith("graph LR")

    def test_all_ecosystem_repos_present_in_graph(self):
        arch_mod.main()
        graph = json.loads(arch_mod.OUTPUT_JSON.read_text(encoding="utf-8"))
        graph_repo_ids = {n["id"] for n in graph["nodes"]["repositories"]}

        registry_path = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_repo_names = {r["repo_name"] for r in registry.get("repositories", [])}

        assert registry_repo_names == graph_repo_ids


# ─────────────────────────────────────────────────────────────────────────────
# Documentation
# ─────────────────────────────────────────────────────────────────────────────

class TestObservabilityDocumentation:
    def test_governance_observability_doc_exists(self):
        doc_path = REPO_ROOT / "docs" / "governance-observability.md"
        assert doc_path.is_file(), "docs/governance-observability.md is missing"

    def test_doc_covers_required_topics(self):
        doc_path = REPO_ROOT / "docs" / "governance-observability.md"
        content = doc_path.read_text(encoding="utf-8")
        assert "Maturity Scoring" in content
        assert "Generated Artifacts" in content
        assert "CI Integration" in content
        assert "Architecture" in content

    def test_ecosystem_health_schema_exists(self):
        schema_path = REPO_ROOT / "governance" / "schemas" / "ecosystem-health.schema.json"
        assert schema_path.is_file(), "governance/schemas/ecosystem-health.schema.json is missing"

    def test_arch_graph_schema_exists(self):
        schema_path = REPO_ROOT / "governance" / "schemas" / "ecosystem-architecture-graph.schema.json"
        assert schema_path.is_file(), "governance/schemas/ecosystem-architecture-graph.schema.json is missing"
