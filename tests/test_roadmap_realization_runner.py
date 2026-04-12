"""Focused tests for RF-02/RF-03 roadmap realization runner."""

from __future__ import annotations

import json
from importlib import util
from pathlib import Path

from spectrum_systems.contracts import validate_artifact

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "roadmap_realization_runner.py"
_SPEC = util.spec_from_file_location("roadmap_realization_runner", SCRIPT_PATH)
assert _SPEC and _SPEC.loader
_RUNNER = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_RUNNER)
realize_steps = _RUNNER.realize_steps


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _base_contract(step_id: str) -> dict:
    depends = ["RF-01"] if step_id == "RF-02" else ["RF-01", "RF-02"]
    tests = ["pytest tests/test_roadmap_realization_runner.py -k rf_contract_schema -q"]
    entrypoints = ["spectrum_systems.modules.runtime.roadmap_realization_runtime:next_realization_status"]
    if step_id == "RF-03":
        entrypoints.append("spectrum_systems.modules.runtime.roadmap_realization_runtime:enforce_realization_dependencies")

    return {
        "artifact_type": "roadmap_step_contract",
        "step_id": step_id,
        "owner": "PQX",
        "intent": f"Runtime realization checks for {step_id} with fail-closed gating.",
        "depends_on": depends,
        "target_modules": ["spectrum_systems/modules/runtime/roadmap_realization_runtime.py"],
        "target_contracts": [
            "contracts/schemas/roadmap_step_contract.schema.json",
            "contracts/schemas/roadmap_expansion_trace.schema.json",
        ],
        "target_tests": tests,
        "runtime_entrypoints": entrypoints,
        "forbidden_patterns": ["never-match-pattern"],
        "acceptance_checks": [
            {
                "check_id": f"{step_id.lower().replace('-', '')}_required",
                "description": "Required acceptance check for runner gating.",
                "required": True,
            }
        ],
        "realization_mode": "runtime_realization",
        "realization_status": "planned_only",
        "expansion_version": "1.0.0",
        "expansion_policy_hash": "152968011b794af977ccdfa9813025ef2271dbd6be90a48116d5a6b665b73839",
        "expansion_trace_ref": "contracts/examples/roadmap_expansion_trace.example.json#RF-03",
    }


def _write_contracts(tmp_path: Path, rf02: dict | None = None, rf03: dict | None = None) -> Path:
    contract_dir = tmp_path / "artifacts" / "roadmap_contracts"
    _write_json(contract_dir / "RF-02.json", rf02 or _base_contract("RF-02"))
    _write_json(contract_dir / "RF-03.json", rf03 or _base_contract("RF-03"))
    return contract_dir


def test_rf_contract_schema() -> None:
    validate_artifact(json.loads(Path("artifacts/roadmap_contracts/RF-02.json").read_text()), "roadmap_step_contract")
    validate_artifact(json.loads(Path("artifacts/roadmap_contracts/RF-03.json").read_text()), "roadmap_step_contract")


def test_malformed_contracts_rejected_fail_closed(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    del rf02["target_modules"]
    rf03 = _base_contract("RF-03")
    rf03["acceptance_checks"] = []
    contract_dir = _write_contracts(tmp_path, rf02=rf02, rf03=rf03)
    result = realize_steps(step_ids=["RF-02", "RF-03"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert result["overall_status"] == "fail"
    assert set(result["failed_steps"]) == {"RF-02", "RF-03"}
    assert result["attempted_steps"] == []
    assert set(result["contract_validation_failures"]) == {"RF-02", "RF-03"}


def test_dependency_bypass_attack_blocked(tmp_path: Path) -> None:
    contract_dir = _write_contracts(tmp_path)
    result = realize_steps(step_ids=["RF-03", "RF-02"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert "RF-03" in result["failed_steps"]
    assert "RF-03" in result["dependency_failures"]
    assert result["overall_status"] == "fail"


def test_forbidden_pattern_evasion_attack_blocked(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["forbidden_patterns"] = ["ALLOWED_STATUSES"]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(step_ids=["RF-02"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert result["overall_status"] == "fail"
    assert result["forbidden_pattern_hits"]["RF-02"]


def test_fake_test_success_attack_blocked(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["target_tests"] = ["pytest tests/test_roadmap_realization_runner.py -k rf_contract_schema -q && python -c \"raise SystemExit(0)\""]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(step_ids=["RF-02"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert result["overall_status"] == "fail"
    assert result["behavioral_test_policy_checks"]["RF-02"][0]["approved"] is False


def test_status_forging_attack_blocked(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["realization_status"] = "verified"
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(step_ids=["RF-02"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert result["overall_status"] == "pass"
    updates = result["status_updates"]
    assert updates[0]["from"] == "planned_only"
    assert json.loads((contract_dir / "RF-02.json").read_text())["realization_status"] == "verified"


def test_ownership_boundary_attack_blocked(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["target_modules"] = ["spectrum_systems/modules/control/illegal.py"]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(step_ids=["RF-02"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert result["overall_status"] == "fail"
    assert result["ownership_checks"]["RF-02"]["passed"] is False


def test_fail_closed_result_semantics_on_critical_failure(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.roadmap_realization_runtime:missing_function"]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(step_ids=["RF-02"], contract_dir=contract_dir, result_path=tmp_path / "result.json", repo_root=Path("."))
    assert result["overall_status"] == "fail"
    assert result["passed_steps"] == []
    assert result["status_updates"] == []
