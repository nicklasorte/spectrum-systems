from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.governance.execution_change_impact import analyze_execution_change_impact

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_execution_change_impact_analysis.py"


def test_low_risk_non_governed_path_can_be_safe() -> None:
    artifact = analyze_execution_change_impact(repo_root=REPO_ROOT, changed_paths=["README.md"])
    assert artifact["risk_classification"] == "safe"
    assert artifact["blocking"] is False
    assert artifact["indeterminate"] is False
    assert artifact["safe_to_execute"] is True


def test_runtime_and_orchestration_paths_elevate_sensitivity() -> None:
    artifact = analyze_execution_change_impact(
        repo_root=REPO_ROOT,
        changed_paths=[
            "spectrum_systems/modules/runtime/pqx_slice_runner.py",
            "spectrum_systems/orchestration/cycle_runner.py",
            "tests/test_pqx_slice_runner.py",
        ],
        provided_reviews=["runtime-governance-review"],
        provided_eval_artifacts=["regression_result", "control_loop_certification_pack"],
    )
    assert artifact["highest_sensitivity"] == "critical"
    assert artifact["risk_classification"] in {"high_risk", "blocking"}
    assert "runtime-governance-review" in artifact["required_reviews"]


def test_unknown_governed_candidate_path_fails_closed_indeterminate() -> None:
    artifact = analyze_execution_change_impact(repo_root=REPO_ROOT, changed_paths=["spectrum_systems/new_surface.py"])
    assert artifact["indeterminate"] is True
    assert artifact["blocking"] is True
    assert artifact["safe_to_execute"] is False
    assert artifact["risk_classification"] == "indeterminate"


def test_critical_governed_paths_require_review_and_eval_evidence() -> None:
    artifact = analyze_execution_change_impact(
        repo_root=REPO_ROOT,
        changed_paths=["spectrum_systems/modules/runtime/pqx_slice_runner.py", "tests/test_pqx_slice_runner.py"],
    )
    assert artifact["blocking"] is True
    assert "runtime-governance-review" in artifact["required_reviews"]
    assert "regression_result" in artifact["required_eval_artifacts"]
    assert "attach_required_reviews" in artifact["required_followup_actions"]


def test_deterministic_repeat_runs_match_identity_fields() -> None:
    first = analyze_execution_change_impact(
        repo_root=REPO_ROOT,
        changed_paths=["README.md", "docs/governance/contract-impact-gate.md"],
    )
    second = analyze_execution_change_impact(
        repo_root=REPO_ROOT,
        changed_paths=["README.md", "docs/governance/contract-impact-gate.md"],
    )
    assert first["impact_id"] == second["impact_id"]
    assert first["changed_paths"] == second["changed_paths"]
    assert first["path_assessments"] == second["path_assessments"]


def test_schema_validation_fails_closed_for_malformed_artifact() -> None:
    artifact = analyze_execution_change_impact(repo_root=REPO_ROOT, changed_paths=["README.md"])
    artifact.pop("path_assessments")
    with pytest.raises(Exception):
        validate_artifact(artifact, "execution_change_impact_artifact")


def test_cli_exits_nonzero_on_blocking_result(tmp_path: Path) -> None:
    output = tmp_path / "impact.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--changed-path",
            "spectrum_systems/modules/runtime/pqx_slice_runner.py",
            "--output-path",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["blocking"] is True
