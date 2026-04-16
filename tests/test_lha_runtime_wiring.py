from __future__ import annotations

from spectrum_systems.modules.runtime.rwa_runtime_wiring import (
    execute_lha_final_proof_matrix,
    execute_lha_red_team_loops,
    execute_lha_trustworthy_run,
)


def test_lha_step_matrix_runs_for_20_50_100() -> None:
    run20 = execute_lha_trustworthy_run(20)
    run50 = execute_lha_trustworthy_run(50)
    run100 = execute_lha_trustworthy_run(100)

    assert run20["status"] == "pass"
    assert run50["status"] == "pass"
    assert run100["status"] == "pass"

    assert run20["tests"]["tst_13"]["status"] == "pass"
    assert run50["tests"]["tst_14"]["status"] == "pass"
    assert run100["tests"]["tst_15"]["status"] == "pass"
    assert run100["tests"]["tst_17"]["status"] == "pass"


def test_lha_owner_boundaries_and_controls_are_fail_closed() -> None:
    run = execute_lha_trustworthy_run(100)

    assert run["boundary_lint"]["owner"] == "CON"
    assert run["boundary_lint"]["status"] == "pass"

    assert run["control"]["bounded"]["owner"] == "CDE"
    assert run["control"]["recertification"]["owner"] == "CDE"
    assert run["control"]["false_green"]["owner"] == "CDE"

    assert run["freshness"]["owner"] == "CTX"
    assert run["freshness"]["status"] == "pass"
    assert run["delayed_drift"]["owner"] == "CTX"


def test_lha_red_team_loop_has_fix_and_regression_per_round() -> None:
    loops = execute_lha_red_team_loops()
    assert len(loops) == 15

    for idx in range(0, len(loops), 3):
        review = loops[idx]
        fix = loops[idx + 1]
        regression = loops[idx + 2]
        assert review["owner"] == "RIL"
        assert fix["owner"] == "FRE"
        assert regression["owner"] == "TST"
        assert regression["rerun"] is True


def test_lha_final_proof_matrix_passes() -> None:
    proof = execute_lha_final_proof_matrix()
    assert proof["artifact_type"] == "final_lha_proof_matrix_record"
    assert proof["status"] == "pass"
    assert proof["final_rerun"]["status"] == "pass"
    assert set(proof["matrix"]) == {20, 50, 100}
