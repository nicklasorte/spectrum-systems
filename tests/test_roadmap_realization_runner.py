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
    tests = ["python -c \"raise SystemExit(0)\""]
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


def test_rf02_rf03_contracts_pass_schema_validation() -> None:
    validate_artifact(json.loads(Path("artifacts/roadmap_contracts/RF-02.json").read_text()), "roadmap_step_contract")
    validate_artifact(json.loads(Path("artifacts/roadmap_contracts/RF-03.json").read_text()), "roadmap_step_contract")


def test_rf03_dependency_order_is_enforced(tmp_path: Path) -> None:
    contract_dir = _write_contracts(tmp_path)
    result = realize_steps(
        step_ids=["RF-03", "RF-02"],
        contract_dir=contract_dir,
        result_path=tmp_path / "result.json",
        repo_root=Path("."),
    )
    assert "RF-03" in result["failed_steps"]


def test_forbidden_patterns_block_realization(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["forbidden_patterns"] = ["ALLOWED_STATUSES"]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(
        step_ids=["RF-02"],
        contract_dir=contract_dir,
        result_path=tmp_path / "result.json",
        repo_root=Path("."),
    )
    assert result["failed_steps"] == ["RF-02"]
    assert result["forbidden_pattern_hits"]["RF-02"]


def test_missing_runtime_entrypoint_blocks_realization(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.roadmap_realization_runtime:missing_function"]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(
        step_ids=["RF-02"],
        contract_dir=contract_dir,
        result_path=tmp_path / "result.json",
        repo_root=Path("."),
    )
    assert result["failed_steps"] == ["RF-02"]
    assert result["runtime_entrypoint_checks"]["RF-02"][0]["exists"] is False


def test_failing_behavioral_tests_block_status_advancement(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["target_tests"] = ["python -c \"raise SystemExit(1)\""]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result = realize_steps(
        step_ids=["RF-02"],
        contract_dir=contract_dir,
        result_path=tmp_path / "result.json",
        repo_root=Path("."),
    )
    updated = json.loads((contract_dir / "RF-02.json").read_text())
    assert result["failed_steps"] == ["RF-02"]
    assert updated["realization_status"] == "planned_only"


def test_passing_behavioral_tests_allow_status_advancement(tmp_path: Path) -> None:
    contract_dir = _write_contracts(tmp_path)
    result = realize_steps(
        step_ids=["RF-02", "RF-03"],
        contract_dir=contract_dir,
        result_path=tmp_path / "result.json",
        repo_root=Path("."),
    )
    rf02 = json.loads((contract_dir / "RF-02.json").read_text())
    rf03 = json.loads((contract_dir / "RF-03.json").read_text())
    assert result["failed_steps"] == []
    assert rf02["realization_status"] in {"runtime_realized", "verified"}
    assert rf03["realization_status"] in {"runtime_realized", "verified"}


def test_result_artifact_reflects_real_outcomes(tmp_path: Path) -> None:
    rf02 = _base_contract("RF-02")
    rf02["target_tests"] = ["python -c \"raise SystemExit(1)\""]
    contract_dir = _write_contracts(tmp_path, rf02=rf02)
    result_path = tmp_path / "roadmap_realization_result.json"
    result = realize_steps(
        step_ids=["RF-02", "RF-03"],
        contract_dir=contract_dir,
        result_path=result_path,
        repo_root=Path("."),
    )
    written = json.loads(result_path.read_text())
    assert written["artifact_type"] == "roadmap_realization_result"
    assert written["attempted_steps"] == ["RF-02", "RF-03"]
    assert written["overall_status"] == result["overall_status"] == "fail"
