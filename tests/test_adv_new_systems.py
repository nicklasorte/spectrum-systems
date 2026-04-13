
from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime import (
    ail_runtime,
    cal_runtime,
    chx_runtime,
    cvx_runtime,
    dep_runtime,
    dex_runtime,
    hix_runtime,
    pol_runtime,
    prx_runtime,
    qos_runtime,
    rca_runtime,
    sch_runtime,
    sim_runtime,
    simx_runtime,
)

RUNTIMES = [
    chx_runtime, cvx_runtime, dex_runtime, sim_runtime, prx_runtime, hix_runtime,
    cal_runtime, pol_runtime, ail_runtime, sch_runtime, dep_runtime, rca_runtime, qos_runtime, simx_runtime,
]


def _payload() -> dict:
    return {"trace_id": "trace-adv-001", "fail_reasons": []}


@pytest.mark.parametrize("module", RUNTIMES)
def test_runtime_happy_path_artifacts_validate(module) -> None:
    eval_artifact = module.build_eval_artifact(payload=_payload())
    readiness = module.build_readiness_artifact(eval_artifact=eval_artifact)
    replay = module.validate_replay(baseline=eval_artifact, replay=dict(eval_artifact))
    effectiveness = module.build_effectiveness_artifact(eval_artifact=eval_artifact, replay_result=replay)
    red = module.run_red_team_round(fixture={"authority_creep_attempt": False, "unbounded_input": False})

    assert eval_artifact["status"] == "pass"
    assert readiness["status"] == "candidate_ready"
    assert replay["is_match"] is True
    assert effectiveness["status"] in {"stable", "mildly_divergent"}
    assert red["status"] == "pass"


@pytest.mark.parametrize("module", RUNTIMES)
def test_runtime_fail_closed_on_non_mapping(module) -> None:
    with pytest.raises(ValueError):
        module.build_eval_artifact(payload="bad")


def test_cross_system_authority_boundary_regression() -> None:
    dex_eval = dex_runtime.build_eval_artifact(payload={"trace_id": "t", "fail_reasons": []})
    assert "no_policy_authority" in dex_runtime.build_readiness_artifact(eval_artifact=dex_eval)["details"]["non_authority_assertions"]

    sim_red = sim_runtime.run_red_team_round(fixture={"authority_creep_attempt": True})
    assert sim_red["details"]["exploit_detected"] is True
    assert sim_red["status"] == "materially_inconsistent"
