from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_long_fabric import (
    STEP_CONTRACTS,
    assert_authority_boundaries,
    cde_phase_decision,
    execute_r100_np001,
    normalize_roadmap_contract,
    rerun_after_fix,
)


def _sample_roadmap() -> dict:
    return {
        "roadmap_id": "R100-MVP",
        "phases": [
            {
                "phase_id": "P1",
                "start": "2026-04-15T00:00:00Z",
                "end": "2026-04-16T00:00:00Z",
                "batches": ["B1", "B2", "B3"],
                "dependencies": [],
            },
            {
                "phase_id": "P2",
                "start": "2026-04-16T00:00:00Z",
                "end": "2026-04-17T00:00:00Z",
                "batches": ["B4", "B5"],
                "dependencies": ["P1"],
            },
        ],
    }


def test_normalization_hash_is_deterministic() -> None:
    a, ha = normalize_roadmap_contract(_sample_roadmap())
    b, hb = normalize_roadmap_contract(_sample_roadmap())
    assert a == b
    assert ha == hb


def test_execute_r100_emits_all_step_artifacts() -> None:
    results = execute_r100_np001(_sample_roadmap())
    for step, (contract, _owner) in STEP_CONTRACTS.items():
        assert step in results
        validate_artifact(results[step], contract)


def test_redteam_and_fix_rounds_exist_and_validate() -> None:
    results = execute_r100_np001(_sample_roadmap())
    for i in range(1, 8):
        rt_key = f"RT-E{i}"
        fx_key = f"FX-E{i}"
        assert rt_key in results
        assert fx_key in results
        validate_artifact(results[rt_key], results[rt_key]["artifact_type"])
        validate_artifact(results[fx_key], results[fx_key]["artifact_type"])


def test_cde_remains_sole_decision_authority() -> None:
    results = execute_r100_np001(_sample_roadmap())
    violations = assert_authority_boundaries(results)
    assert violations == []


def test_rerun_after_fix_reduces_remaining_exploits() -> None:
    results = execute_r100_np001(_sample_roadmap())
    rerun = rerun_after_fix(results)
    for i in range(1, 8):
        before = results[f"FX-E{i}"]["metrics"]["remaining_exploits"]
        after = rerun[f"FX-E{i}"]["metrics"]["remaining_exploits"]
        assert after <= before


def test_umbrella_boundary_decision_matrix_paths() -> None:
    assert cde_phase_decision(trust=0.9, debt=0.1, budget_pressure=0.1, capacity_pressure=0.1)["status"] == "continue"
    assert cde_phase_decision(trust=0.2, debt=0.2, budget_pressure=0.1, capacity_pressure=0.1)["status"] == "escalate"
    assert cde_phase_decision(trust=0.9, debt=0.9, budget_pressure=0.1, capacity_pressure=0.1)["status"] == "halt"
    assert cde_phase_decision(trust=0.9, debt=0.65, budget_pressure=0.1, capacity_pressure=0.1)["status"] == "recut"
    assert cde_phase_decision(trust=0.9, debt=0.45, budget_pressure=0.1, capacity_pressure=0.1)["status"] == "partial_continue"
