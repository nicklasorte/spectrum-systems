from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.runtime.governed_repair_loop_execution import run_governed_repair_loop


def _run(case_id: str, tmp_path: Path, **overrides):
    payload = {
        "failure_case_id": case_id,
        "batch_id": "GRC-INTEGRATION-01",
        "umbrella_id": "GOVERNED_REPAIR_LOOP_CLOSURE",
        "run_id": f"run-{case_id.lower()}",
        "trace_id": f"trace-{case_id.lower()}",
        "retry_budget": 2,
        "complexity_score": 2,
        "risk_level": "medium",
        "tmp_dir": tmp_path / case_id.lower(),
    }
    payload.update(overrides)
    return run_governed_repair_loop(
        **payload,
    )


def test_full_loop_executes_end_to_end_for_aut05(tmp_path: Path) -> None:
    result = _run("AUT-05", tmp_path)
    assert result["status"] == "resumed"
    assert result["trace"]["packet"]["artifact_type"] == "execution_failure_packet"
    assert result["trace"]["candidate"]["artifact_type"] == "bounded_repair_candidate_artifact"
    assert result["trace"]["decision"]["decision_owner"] == "CDE"
    assert result["trace"]["gating_decision"]["owner"] == "TPA"
    assert result["trace"]["execution"]["owner"] == "PQX"
    assert result["trace"]["execution"]["canonical_artifact"]["artifact_type"] == "pqx_slice_execution_record"
    assert result["trace"]["execution"]["canonical_artifact"]["trace_id"] == "trace-aut-05"
    assert result["trace"]["review"]["review_owner"] == "RQX"
    assert result["trace"]["review"]["interpretation_owner"] == "RIL"
    assert result["trace"]["review"]["canonical_artifact"]["artifact_type"] == "review_result_artifact"
    assert result["trace"]["review"]["canonical_artifact"]["review_outcome"] == "approved"
    assert result["trace"]["resume"]["owner"] == "TLC"


def test_full_loop_executes_end_to_end_for_aut07_real_authenticity_failure(tmp_path: Path) -> None:
    result = _run("AUT-07", tmp_path)
    assert result["status"] == "resumed"
    failure_classes = {row["failure_class"] for row in result["trace"]["failure"]["blocking_reasons"]}
    assert "authenticity_lineage_mismatch" in failure_classes
    assert "cross_artifact_mismatch" in failure_classes


def test_full_loop_executes_end_to_end_for_aut10(tmp_path: Path) -> None:
    result = _run("AUT-10", tmp_path)
    assert result["status"] == "resumed"
    assert result["trace"]["failure"]["slice_id"] == "AUT-10"


def test_rejection_path_blocks_on_high_risk_complexity(tmp_path: Path) -> None:
    result = _run("AUT-05", tmp_path, complexity_score=9, risk_level="high")
    assert result["status"] == "blocked"
    assert result["stop_reason"] == "risk_budget_exceeded"


def test_retry_exhaustion_path_blocks(tmp_path: Path) -> None:
    result = _run("AUT-10", tmp_path, retry_budget=1)
    assert result["status"] == "blocked"
    assert result["stop_reason"] == "retry_budget_exhausted"


def test_policy_blocked_case_stops_without_execution(tmp_path: Path) -> None:
    result = _run("AUT-05", tmp_path, policy_blocked=True)
    assert result["status"] == "stopped"
    assert result["trace"]["packet"]["classified_failure_type"] == "policy_blocked"
    assert "execution" not in result["trace"]
