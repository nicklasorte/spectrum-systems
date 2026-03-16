import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNER_PATH = REPO_ROOT / "governance" / "compliance-scans" / "run-cross-repo-compliance.js"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"


def _write_baseline_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "README.md").write_text("Spectrum Systems test repo")
    (repo_dir / "CLAUDE.md").write_text("claude")
    (repo_dir / "CODEX.md").write_text("codex")
    (repo_dir / "SYSTEMS.md").write_text("systems")
    (repo_dir / "docs").mkdir(exist_ok=True)
    (repo_dir / "tests").mkdir(exist_ok=True)
    workflows = repo_dir / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "ci.yml").write_text("name: test")


def _write_valid_manifest(repo_dir: Path, system_id: str = "sample-engine") -> None:
    manifest = {
        "system_id": system_id,
        "repo_name": system_id,
        "repo_type": "operational_engine",
        "governance_repo": "spectrum-systems",
        "governance_version": "1.0.0",
        "contracts": {
            "reviewer_comment_set": "1.0.0",
        },
    }
    (repo_dir / ".spectrum-governance.json").write_text(json.dumps(manifest))


def _make_config(repo_dir: Path, required_contracts: list | None = None) -> dict:
    return {
        "repos": [
            {
                "repo_name": "sample-engine",
                "repo_path": str(repo_dir),
                "expected_system_id": "sample-engine",
                "expected_repo_type": "operational_engine",
                "required_contracts": required_contracts or [],
            }
        ]
    }


def _run_scan(config_path: Path) -> dict:
    result = subprocess.run(
        ["node", str(SCANNER_PATH), str(config_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Original tests (preserved)
# ---------------------------------------------------------------------------

def test_reports_missing_governance_manifest(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "repos": [
                    {
                        "repo_name": "sample-engine",
                        "repo_path": str(repo_dir),
                        "expected_system_id": "SYS-TEST",
                        "expected_repo_type": "operational_engine",
                        "required_contracts": ["test_contract"],
                    }
                ]
            }
        )
    )

    report = _run_scan(config_path)
    repo_result = report["repos"][0]

    assert repo_result["compliant"] is False
    assert any(failure["type"] == "missing_governance_manifest" for failure in repo_result["failures"])


def test_validates_system_id_and_contract_pins(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)

    manifest = {
        "system_id": "SYS-OTHER",
        "governance_repo": "nicklasorte/spectrum-systems",
        "governance_version": "1.0.0",
        "contracts": {"present_contract": "1.0.0"},
    }
    (repo_dir / ".spectrum-governance.json").write_text(json.dumps(manifest))

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "repos": [
                    {
                        "repo_name": "sample-engine",
                        "repo_path": str(repo_dir),
                        "expected_system_id": "SYS-TEST",
                        "expected_repo_type": "operational_engine",
                        "required_contracts": ["present_contract", "missing_contract"],
                    }
                ]
            }
        )
    )

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {failure["type"] for failure in repo_result["failures"]}

    assert repo_result["compliant"] is False
    assert "system_id_mismatch" in failure_types
    assert "missing_required_contract_pin" in failure_types


# ---------------------------------------------------------------------------
# New tests: not_yet_enforceable state
# ---------------------------------------------------------------------------

def test_missing_repo_path_is_not_yet_enforceable(tmp_path: Path) -> None:
    """A repo whose path does not exist on disk should be 'not_yet_enforceable', not 'fail'."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "repos": [
                    {
                        "repo_name": "nonexistent-engine",
                        "repo_path": str(tmp_path / "does-not-exist"),
                        "expected_system_id": "nonexistent-engine",
                        "expected_repo_type": "operational_engine",
                        "required_contracts": [],
                    }
                ]
            }
        )
    )

    report = _run_scan(config_path)
    repo_result = report["repos"][0]

    assert repo_result["status"] == "not_yet_enforceable"
    assert repo_result["compliant"] is False
    assert repo_result["failures"] == []


def test_not_yet_enforceable_does_not_cause_overall_fail(tmp_path: Path) -> None:
    """When all repos are not_yet_enforceable, the report should have no 'fail' entries."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "repos": [
                    {
                        "repo_name": "repo-a",
                        "repo_path": str(tmp_path / "repo-a"),
                        "expected_system_id": "repo-a",
                        "expected_repo_type": "operational_engine",
                        "required_contracts": [],
                    },
                    {
                        "repo_name": "repo-b",
                        "repo_path": str(tmp_path / "repo-b"),
                        "expected_system_id": "repo-b",
                        "expected_repo_type": "operational_engine",
                        "required_contracts": [],
                    },
                ]
            }
        )
    )

    report = _run_scan(config_path)
    failing = [r for r in report["repos"] if r["status"] == "fail"]
    assert failing == []


# ---------------------------------------------------------------------------
# New tests: contract version pin validation
# ---------------------------------------------------------------------------

def test_contract_pin_version_mismatch_is_a_failure(tmp_path: Path) -> None:
    """Pinning a contract at a version that differs from standards-manifest should fail."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)

    # pdf_anchored_docx_comment_injection_contract is 1.0.1 in the standards manifest.
    manifest = {
        "system_id": "sample-engine",
        "repo_name": "sample-engine",
        "repo_type": "operational_engine",
        "governance_repo": "spectrum-systems",
        "governance_version": "1.0.0",
        "contracts": {
            "pdf_anchored_docx_comment_injection_contract": "1.0.0",  # wrong – should be 1.0.1
        },
    }
    (repo_dir / ".spectrum-governance.json").write_text(json.dumps(manifest))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert repo_result["status"] == "fail"
    assert "contract_version_pin_mismatch" in failure_types


def test_contract_pin_version_match_passes(tmp_path: Path) -> None:
    """Pinning all contracts at their canonical versions should produce no failures."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)

    manifest = {
        "system_id": "sample-engine",
        "repo_name": "sample-engine",
        "repo_type": "operational_engine",
        "governance_repo": "spectrum-systems",
        "governance_version": "1.0.0",
        "contracts": {
            "reviewer_comment_set": "1.0.0",
            "pdf_anchored_docx_comment_injection_contract": "1.0.1",  # correct
        },
    }
    (repo_dir / ".spectrum-governance.json").write_text(json.dumps(manifest))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir, ["reviewer_comment_set"])))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]

    assert repo_result["status"] in {"pass", "warning"}
    failure_types = {f["type"] for f in repo_result["failures"]}
    assert "contract_version_pin_mismatch" not in failure_types


def test_unknown_contract_pin_is_a_failure(tmp_path: Path) -> None:
    """Pinning a contract type that does not exist in the standards manifest should fail."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)

    manifest = {
        "system_id": "sample-engine",
        "repo_name": "sample-engine",
        "repo_type": "operational_engine",
        "governance_repo": "spectrum-systems",
        "governance_version": "1.0.0",
        "contracts": {
            "nonexistent_contract_xyz": "1.0.0",
        },
    }
    (repo_dir / ".spectrum-governance.json").write_text(json.dumps(manifest))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert repo_result["status"] == "fail"
    assert "unknown_contract_pin" in failure_types


# ---------------------------------------------------------------------------
# New tests: governance declaration validation
# ---------------------------------------------------------------------------

def _write_valid_governance_declaration(repo_dir: Path) -> None:
    """Write a minimal but valid .governance-declaration.json."""
    declaration = {
        "governance_declaration_version": "1.0.0",
        "architecture_source": "nicklasorte/spectrum-systems",
        "standards_manifest_version": "2026.03.0",
        "system_id": "SYS-001",
        "implementation_repo": "nicklasorte/sample-engine",
        "declared_at": "2026-03-16",
        "contract_pins": {
            "reviewer_comment_set": "1.0.0",
        },
        "schema_pins": {},
        "rule_version": None,
        "prompt_set_hash": None,
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": "2026-03-16",
        "external_storage_policy": "none",
    }
    (repo_dir / ".governance-declaration.json").write_text(json.dumps(declaration))


def test_valid_governance_declaration_passes(tmp_path: Path) -> None:
    """A well-formed governance declaration with correct pins should not add failures."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    _write_valid_manifest(repo_dir)
    _write_valid_governance_declaration(repo_dir)

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir, ["reviewer_comment_set"])))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert "invalid_governance_declaration" not in failure_types
    assert "governance_declaration_missing_field" not in failure_types
    assert "governance_declaration_unfilled_placeholder" not in failure_types


def test_governance_declaration_missing_required_field(tmp_path: Path) -> None:
    """A governance declaration missing a required field should produce a failure."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    _write_valid_manifest(repo_dir)

    # Missing 'system_id' field
    declaration = {
        "governance_declaration_version": "1.0.0",
        "architecture_source": "nicklasorte/spectrum-systems",
        "standards_manifest_version": "2026.03.0",
        # "system_id" intentionally omitted
        "implementation_repo": "nicklasorte/sample-engine",
        "declared_at": "2026-03-16",
        "contract_pins": {},
        "schema_pins": {},
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": "2026-03-16",
        "external_storage_policy": "none",
    }
    (repo_dir / ".governance-declaration.json").write_text(json.dumps(declaration))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert "governance_declaration_missing_field" in failure_types
    missing_fields = [f["field"] for f in repo_result["failures"] if f["type"] == "governance_declaration_missing_field"]
    assert "system_id" in missing_fields


def test_governance_declaration_unfilled_placeholder(tmp_path: Path) -> None:
    """A governance declaration with an unfilled placeholder value should produce a failure."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    _write_valid_manifest(repo_dir)

    declaration = {
        "governance_declaration_version": "1.0.0",
        "architecture_source": "nicklasorte/spectrum-systems",
        "standards_manifest_version": "2026.03.0",
        "system_id": "<YOUR_SYSTEM_ID>",  # unfilled placeholder
        "implementation_repo": "nicklasorte/sample-engine",
        "declared_at": "2026-03-16",
        "contract_pins": {},
        "schema_pins": {},
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": "2026-03-16",
        "external_storage_policy": "none",
    }
    (repo_dir / ".governance-declaration.json").write_text(json.dumps(declaration))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert "governance_declaration_unfilled_placeholder" in failure_types


def test_governance_declaration_contract_pin_version_mismatch(tmp_path: Path) -> None:
    """A governance declaration pinning a contract at the wrong version should fail."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    _write_valid_manifest(repo_dir)

    declaration = {
        "governance_declaration_version": "1.0.0",
        "architecture_source": "nicklasorte/spectrum-systems",
        "standards_manifest_version": "2026.03.0",
        "system_id": "SYS-001",
        "implementation_repo": "nicklasorte/sample-engine",
        "declared_at": "2026-03-16",
        "contract_pins": {
            "pdf_anchored_docx_comment_injection_contract": "1.0.0",  # wrong – should be 1.0.1
        },
        "schema_pins": {},
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": "2026-03-16",
        "external_storage_policy": "none",
    }
    (repo_dir / ".governance-declaration.json").write_text(json.dumps(declaration))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert "governance_declaration_contract_version_mismatch" in failure_types


def test_governance_declaration_schema_pin_missing_file(tmp_path: Path) -> None:
    """A governance declaration schema_pin pointing to a non-existent file should fail."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    _write_valid_manifest(repo_dir)

    declaration = {
        "governance_declaration_version": "1.0.0",
        "architecture_source": "nicklasorte/spectrum-systems",
        "standards_manifest_version": "2026.03.0",
        "system_id": "SYS-001",
        "implementation_repo": "nicklasorte/sample-engine",
        "declared_at": "2026-03-16",
        "contract_pins": {},
        "schema_pins": {
            "schemas/nonexistent-schema.json": "1.0.0",  # does not exist in repo
        },
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": "2026-03-16",
        "external_storage_policy": "none",
    }
    (repo_dir / ".governance-declaration.json").write_text(json.dumps(declaration))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert "governance_declaration_schema_pin_missing" in failure_types


def test_governance_declaration_schema_pin_valid_file(tmp_path: Path) -> None:
    """A governance declaration schema_pin pointing to a real file should not add failures."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    _write_valid_manifest(repo_dir)

    # Use a real schema file that exists in the governance repo.
    declaration = {
        "governance_declaration_version": "1.0.0",
        "architecture_source": "nicklasorte/spectrum-systems",
        "standards_manifest_version": "2026.03.0",
        "system_id": "SYS-001",
        "implementation_repo": "nicklasorte/sample-engine",
        "declared_at": "2026-03-16",
        "contract_pins": {},
        "schema_pins": {
            "contracts/schemas/reviewer_comment_set.schema.json": "1.0.0",
        },
        "evaluation_manifest_path": "eval/README.md",
        "last_evaluation_date": "2026-03-16",
        "external_storage_policy": "none",
    }
    (repo_dir / ".governance-declaration.json").write_text(json.dumps(declaration))

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir, ["reviewer_comment_set"])))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]
    failure_types = {f["type"] for f in repo_result["failures"]}

    assert "governance_declaration_schema_pin_missing" not in failure_types


# ---------------------------------------------------------------------------
# New tests: result status field
# ---------------------------------------------------------------------------

def test_compliant_repo_has_pass_status(tmp_path: Path) -> None:
    """A fully compliant repo with no warnings should have status 'pass'."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    # Ensure README contains the required spectrum-systems reference (hyphenated).
    (repo_dir / "README.md").write_text("Powered by spectrum-systems governance.")
    _write_valid_manifest(repo_dir)

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir, ["reviewer_comment_set"])))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]

    assert repo_result["compliant"] is True
    assert repo_result["status"] == "pass"


def test_repo_with_failures_has_fail_status(tmp_path: Path) -> None:
    """A repo with at least one failure should have status 'fail'."""
    repo_dir = tmp_path / "repo"
    _write_baseline_repo(repo_dir)
    # No manifest -> failure

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_make_config(repo_dir)))

    report = _run_scan(config_path)
    repo_result = report["repos"][0]

    assert repo_result["status"] == "fail"
    assert repo_result["compliant"] is False

