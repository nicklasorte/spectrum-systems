import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNER_PATH = REPO_ROOT / "governance" / "compliance-scans" / "run-cross-repo-compliance.js"


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


def _run_scan(config_path: Path) -> dict:
    result = subprocess.run(
        ["node", str(SCANNER_PATH), str(config_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return json.loads(result.stdout)


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
