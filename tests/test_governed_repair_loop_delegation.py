from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime import governed_repair_loop_execution as loop_module
from spectrum_systems.modules.runtime.governed_repair_foundation import (
    build_bounded_repair_candidate,
    build_cde_repair_continuation_input,
    build_execution_failure_packet,
    build_tpa_repair_gating_input,
)


def _run(case_id: str, tmp_path: Path, **overrides):
    payload = {
        "failure_case_id": case_id,
        "batch_id": "GRC-INTEGRATION-02",
        "umbrella_id": "GOVERNED_REPAIR_LOOP_CLOSURE",
        "run_id": f"run-{case_id.lower()}",
        "trace_id": f"trace-{case_id.lower()}",
        "retry_budget": 2,
        "complexity_score": 2,
        "risk_level": "medium",
        "tmp_dir": tmp_path / case_id.lower(),
    }
    payload.update(overrides)
    return loop_module.run_governed_repair_loop(**payload)


def test_schema_valid_stage_artifacts_and_linkage_for_aut05(tmp_path: Path) -> None:
    result = _run("AUT-05", tmp_path)
    trace = result["trace"]

    validate_artifact(trace["packet"], "execution_failure_packet")
    validate_artifact(trace["candidate"], "bounded_repair_candidate_artifact")
    validate_artifact(trace["continuation_input"], "cde_repair_continuation_input")
    validate_artifact(trace["gating_input"], "tpa_repair_gating_input")
    validate_artifact(trace["resume"]["resume_record"], "resume_record")

    packet = trace["packet"]
    candidate = trace["candidate"]
    continuation_input = trace["continuation_input"]
    gating_input = trace["gating_input"]
    execution = trace["execution"]
    execution_artifact = execution["canonical_artifact"]
    review = trace["review"]
    review_artifact = review["canonical_artifact"]
    resume = trace["resume"]["resume_record"]

    assert candidate["failure_packet_ref"] == f"execution_failure_packet:{packet['failure_packet_id']}"
    assert continuation_input["failure_packet_ref"] == f"execution_failure_packet:{packet['failure_packet_id']}"
    assert continuation_input["repair_candidate_ref"] == f"bounded_repair_candidate_artifact:{candidate['candidate_id']}"
    assert trace["decision"]["continuation_input_ref"] == (
        f"cde_repair_continuation_input:{continuation_input['continuation_input_id']}"
    )

    assert gating_input["repair_candidate_ref"] == f"bounded_repair_candidate_artifact:{candidate['candidate_id']}"
    assert gating_input["failure_packet_ref"] == f"execution_failure_packet:{packet['failure_packet_id']}"
    assert trace["gating_decision"]["gating_input_ref"] == f"tpa_repair_gating_input:{gating_input['gating_input_id']}"

    assert execution["approved_slice_ref"] == trace["gating_decision"]["approved_slice"]["slice_id"]
    assert execution["gating_input_ref"] == trace["gating_decision"]["gating_input_ref"]
    assert review["execution_record_ref"] == execution["pqx_slice_execution_record"]
    assert execution_artifact["gating_input_ref"] == trace["gating_decision"]["gating_input_ref"]
    assert execution_artifact["lineage_refs"]["failure_packet_ref"] == (
        f"execution_failure_packet:{packet['failure_packet_id']}"
    )
    assert execution_artifact["lineage_refs"]["repair_candidate_ref"] == (
        f"bounded_repair_candidate_artifact:{candidate['candidate_id']}"
    )
    assert review_artifact["execution_record_ref"] == execution["pqx_slice_execution_record"]
    assert review_artifact["interpretation_linkage"]["owner"] == "RIL"
    assert resume["trigger_ref"] == execution["pqx_slice_execution_record"]


def test_builder_contract_replay_matches_emitted_artifacts_for_aut05(tmp_path: Path) -> None:
    result = _run("AUT-05", tmp_path)
    trace = result["trace"]

    expected_packet = build_execution_failure_packet(
        readiness_result=trace["failure"],
        execution_refs=["slice_execution:AUT-05"],
        trace_refs=["trace:trace-aut-05:failure"],
        enforcement_refs=["system_enforcement_result_artifact:sel:AUT-05"],
        validation_refs=["validation_ref:AUT-05:readiness"],
        batch_id="GRC-INTEGRATION-02",
        umbrella_id="GOVERNED_REPAIR_LOOP_CLOSURE",
        roadmap_context_ref="contracts/roadmap/roadmap_structure.json",
    )
    expected_candidate = build_bounded_repair_candidate(failure_packet=expected_packet)
    expected_continuation = build_cde_repair_continuation_input(
        failure_packet=expected_packet,
        repair_candidate=expected_candidate,
    )
    expected_gating_input = build_tpa_repair_gating_input(
        failure_packet=expected_packet,
        repair_candidate=expected_candidate,
        retry_budget_remaining=1,
        complexity_score=2,
        risk_level="medium",
    )

    assert trace["packet"] == expected_packet
    assert trace["candidate"] == expected_candidate
    assert trace["continuation_input"] == expected_continuation
    assert trace["gating_input"] == expected_gating_input


def test_aut07_real_artifacts_are_materialized_and_linked(tmp_path: Path) -> None:
    result = _run("AUT-07", tmp_path)
    trace = result["trace"]

    for artifact_ref in trace["failure"]["checked_artifact_refs"]:
        assert Path(artifact_ref).is_file()

    validate_artifact(trace["packet"], "execution_failure_packet")
    validate_artifact(trace["candidate"], "bounded_repair_candidate_artifact")
    assert trace["candidate"]["failure_packet_ref"] == (
        f"execution_failure_packet:{trace['packet']['failure_packet_id']}"
    )


def test_forbidden_paths_halt_execution_and_resume(tmp_path: Path) -> None:
    high_risk = _run("AUT-05", tmp_path, complexity_score=9, risk_level="high")
    assert high_risk["status"] == "blocked"
    assert high_risk["stop_reason"] == "risk_budget_exceeded"
    assert "execution" not in high_risk["trace"]
    assert "resume" not in high_risk["trace"]

    retry_exhausted = _run("AUT-10", tmp_path, retry_budget=1)
    assert retry_exhausted["status"] == "blocked"
    assert retry_exhausted["stop_reason"] == "retry_budget_exhausted"
    assert "execution" not in retry_exhausted["trace"]
    assert "resume" not in retry_exhausted["trace"]

    policy_blocked = _run("AUT-05", tmp_path, policy_blocked=True)
    assert policy_blocked["status"] == "stopped"
    assert policy_blocked["trace"]["packet"]["classified_failure_type"] == "policy_blocked"
    assert "execution" not in policy_blocked["trace"]
    assert "resume" not in policy_blocked["trace"]


def test_no_resume_when_review_reports_not_repaired(tmp_path: Path, monkeypatch) -> None:
    original = loop_module.evaluate_slice_artifact_readiness

    def _blocked_repaired_readiness(*, command: str, **kwargs):
        if "decision['control_decision']" in command:
            blocked = original(command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision)\"", **kwargs)
            blocked["status"] = "blocked"
            return blocked
        return original(command=command, **kwargs)

    monkeypatch.setattr(loop_module, "evaluate_slice_artifact_readiness", _blocked_repaired_readiness)
    result = _run("AUT-05", tmp_path)

    assert result["status"] == "not_repaired"
    assert result["trace"]["review"]["repaired"] is False
    assert "resume" not in result["trace"]


def test_owner_purity_across_delegated_stages(tmp_path: Path) -> None:
    result = _run("AUT-05", tmp_path)
    trace = result["trace"]

    assert trace["failure"]["owning_system"] == "RIL"
    assert trace["packet"]["artifact_type"] == "execution_failure_packet"
    assert trace["candidate"]["artifact_type"] == "bounded_repair_candidate_artifact"
    assert trace["decision"]["decision_owner"] == "CDE"
    assert trace["gating_decision"]["owner"] == "TPA"
    assert trace["execution"]["owner"] == "PQX"
    assert trace["review"]["review_owner"] == "RQX"
    assert trace["review"]["interpretation_owner"] == "RIL"
    assert trace["resume"]["owner"] == "TLC"


def test_replay_from_canonical_artifacts_is_deterministic(tmp_path: Path) -> None:
    result = _run("AUT-07", tmp_path)
    trace = result["trace"]
    replay = loop_module.replay_governed_repair_loop_from_artifacts(
        artifacts={
            "packet": trace["packet"],
            "candidate": trace["candidate"],
            "continuation_input": trace["continuation_input"],
            "gating_input": trace["gating_input"],
            "execution_record": trace["execution"]["canonical_artifact"],
            "review_result": trace["review"]["canonical_artifact"],
            "resume_record": trace["resume"]["resume_record"],
        }
    )
    assert replay["status"] == "resumed"
    assert replay["explanation"].startswith("deterministic:")


def test_integrity_corruption_fails_closed(tmp_path: Path) -> None:
    result = _run("AUT-10", tmp_path)
    trace = result["trace"]
    corrupted = dict(trace["review"]["canonical_artifact"])
    corrupted["trace_id"] = "trace-corrupted"
    with pytest.raises(loop_module.GovernedRepairLoopExecutionError, match="trace linkage mismatch"):
        loop_module.replay_governed_repair_loop_from_artifacts(
            artifacts={
                "packet": trace["packet"],
                "candidate": trace["candidate"],
                "continuation_input": trace["continuation_input"],
                "gating_input": trace["gating_input"],
                "execution_record": trace["execution"]["canonical_artifact"],
                "review_result": corrupted,
                "resume_record": trace["resume"]["resume_record"],
            }
        )
