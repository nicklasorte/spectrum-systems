"""BLF-01 baseline gate regression coverage.

Pins each of the four target failures to a regression check:

1. test_authority_leak_guard_local — original test re-asserted (smoke).
2. test_contract_impact_analysis  — fixture isolates host signing config.
3. test_github_pr_autofix_review_artifact_validation — same fixture isolation.
4. test_roadmap_realization_runner._normalize_pytest_invocation — pins behavioral
   subprocess pytest invocations to the runner's interpreter.

Also exercises scripts/run_blf_01_baseline_gate.py over the in-repo BLF-01
artifact directory (positive case) and three governed-failure scenarios
(missing classification, missing root cause, missing validation command).
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib import util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "blf_01_baseline_failure_fix"
GATE_SCRIPT = REPO_ROOT / "scripts" / "run_blf_01_baseline_gate.py"
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "roadmap_realization_runner.py"


def _load_runner_module():
    spec = util.spec_from_file_location("blf_runner_under_test", RUNNER_SCRIPT)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contract_impact_analysis_helper_pins_signing() -> None:
    text = (REPO_ROOT / "tests" / "test_contract_impact_analysis.py").read_text(encoding="utf-8")
    assert '"commit.gpgsign", "false"' in text, (
        "tests/test_contract_impact_analysis.py::_init_repo must pin "
        "commit.gpgsign=false locally so the host signing config cannot leak in."
    )
    assert '"tag.gpgsign", "false"' in text, (
        "tests/test_contract_impact_analysis.py::_init_repo must also pin tag.gpgsign=false."
    )


def test_github_pr_autofix_helper_pins_signing() -> None:
    text = (REPO_ROOT / "tests" / "test_github_pr_autofix_review_artifact_validation.py").read_text(
        encoding="utf-8"
    )
    assert "'commit.gpgsign', 'false'" in text, (
        "tests/test_github_pr_autofix_review_artifact_validation.py::_init_git_repo must pin "
        "commit.gpgsign=false locally so the host signing config cannot leak in."
    )
    assert "'tag.gpgsign', 'false'" in text


def test_runner_pins_pytest_invocation() -> None:
    runner = _load_runner_module()
    norm = runner._normalize_pytest_invocation
    assert norm(["pytest", "tests/test_x.py", "-q"]) == [sys.executable, "-m", "pytest", "tests/test_x.py", "-q"]
    assert norm(["python", "-m", "pytest", "tests/test_x.py"]) == [sys.executable, "-m", "pytest", "tests/test_x.py"]
    assert norm(["python3", "-m", "pytest", "tests/test_x.py"]) == [sys.executable, "-m", "pytest", "tests/test_x.py"]
    assert norm(["/usr/bin/python3", "-m", "pytest", "tests/test_x.py"]) == [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_x.py",
    ]
    # Non-pytest commands must not be rewritten — the runner's authority is bounded to
    # behavioral pytest proofs, not arbitrary shell invocations.
    assert norm(["echo", "hello"]) == ["echo", "hello"]
    assert norm([]) == []


def _run_gate_subprocess(artifact_dir: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(GATE_SCRIPT), "--artifact-dir", str(artifact_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc.returncode, payload


def test_blf_gate_passes_for_in_repo_artifacts() -> None:
    rc, payload = _run_gate_subprocess(ARTIFACT_DIR)
    assert payload["status"] == "pass", payload
    assert rc == 0, payload
    assert payload["reason_codes"] == []


def test_blf_gate_fails_when_classification_record_missing(tmp_path: Path) -> None:
    for name in ("failure_inventory.json", "root_cause_analysis.json", "fix_decisions.json",
                 "control_validation.json", "replay_validation.json", "delivery_report.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert payload["status"] == "fail"
    assert any(code.startswith("missing_required_record:failure_classification.json") for code in payload["reason_codes"]), payload


def test_blf_gate_fails_when_root_cause_dropped(tmp_path: Path) -> None:
    for name in ("failure_inventory.json", "failure_classification.json", "fix_decisions.json",
                 "control_validation.json", "replay_validation.json", "delivery_report.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    rca = json.loads((ARTIFACT_DIR / "root_cause_analysis.json").read_text(encoding="utf-8"))
    rca["analyses"] = [a for a in rca["analyses"] if "test_contract_impact_analysis" not in a["failure_name"]]
    (tmp_path / "root_cause_analysis.json").write_text(json.dumps(rca))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert payload["status"] == "fail"
    assert any(code.startswith("root_cause_missing:test_contract_impact_analysis") for code in payload["reason_codes"]), payload


def test_blf_gate_fails_when_validation_commands_dropped(tmp_path: Path) -> None:
    for name in ("failure_inventory.json", "failure_classification.json",
                 "root_cause_analysis.json", "fix_decisions.json",
                 "replay_validation.json", "delivery_report.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    control = json.loads((ARTIFACT_DIR / "control_validation.json").read_text(encoding="utf-8"))
    control["commands"] = []
    (tmp_path / "control_validation.json").write_text(json.dumps(control))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert payload["status"] == "fail"
    assert "control_validation_missing_commands" in payload["reason_codes"], payload


def test_blf_gate_fails_when_pass_status_with_residual_blockers(tmp_path: Path) -> None:
    for name in ("failure_inventory.json", "failure_classification.json",
                 "root_cause_analysis.json", "fix_decisions.json",
                 "control_validation.json", "replay_validation.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    delivery = json.loads((ARTIFACT_DIR / "delivery_report.json").read_text(encoding="utf-8"))
    delivery["remaining_blockers"] = ["fake_blocker_for_test"]
    (tmp_path / "delivery_report.json").write_text(json.dumps(delivery))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert payload["status"] == "fail"
    assert "delivery_status_pass_with_remaining_blockers" in payload["reason_codes"], payload


def test_blf_gate_fails_when_h01_ready_but_blockers_remain(tmp_path: Path) -> None:
    for name in ("failure_inventory.json", "failure_classification.json",
                 "root_cause_analysis.json", "fix_decisions.json",
                 "control_validation.json", "replay_validation.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    delivery = json.loads((ARTIFACT_DIR / "delivery_report.json").read_text(encoding="utf-8"))
    delivery["status"] = "blocked"
    delivery["remaining_blockers"] = ["forced_blocker"]
    delivery["h01_readiness"] = "ready"
    (tmp_path / "delivery_report.json").write_text(json.dumps(delivery))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert "h01_ready_but_blockers_remain" in payload["reason_codes"], payload


def test_blf_gate_rejects_unknown_fix_decision(tmp_path: Path) -> None:
    for name in ("failure_inventory.json", "failure_classification.json",
                 "root_cause_analysis.json", "control_validation.json",
                 "replay_validation.json", "delivery_report.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    fixes = json.loads((ARTIFACT_DIR / "fix_decisions.json").read_text(encoding="utf-8"))
    fixes["decisions"][0]["fix_decision"] = "make_it_green_quietly"
    (tmp_path / "fix_decisions.json").write_text(json.dumps(fixes))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert any(code.startswith("unknown_fix_decision:") for code in payload["reason_codes"]), payload


@pytest.mark.parametrize(
    "field",
    ["status", "h01_readiness"],
)
def test_blf_gate_rejects_invalid_delivery_field(tmp_path: Path, field: str) -> None:
    for name in ("failure_inventory.json", "failure_classification.json",
                 "root_cause_analysis.json", "fix_decisions.json",
                 "control_validation.json", "replay_validation.json"):
        (tmp_path / name).write_text((ARTIFACT_DIR / name).read_text(encoding="utf-8"))
    delivery = json.loads((ARTIFACT_DIR / "delivery_report.json").read_text(encoding="utf-8"))
    delivery[field] = "questionable"
    (tmp_path / "delivery_report.json").write_text(json.dumps(delivery))
    rc, payload = _run_gate_subprocess(tmp_path)
    assert rc == 1
    assert payload["status"] == "fail"
    assert any(code.startswith(f"invalid_{'delivery_status' if field == 'status' else 'h01_readiness'}:") for code in payload["reason_codes"]), payload
