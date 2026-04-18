from spectrum_systems.modules.runtime.bne02_full_wave import evaluate_promotion_gate
from spectrum_systems.modules.governance.promotion_requirements import (
    issue_promotion_gate_decision_from_evidence,
)


def test_promotion_gate_blocks_when_requirements_missing() -> None:
    result = evaluate_promotion_gate(
        trace_id="trace-1",
        run_id="run-1",
        eval_pass=True,
        lineage_complete=False,
        judgment_present=False,
        policy_aligned=True,
    )
    assert result["gate_status"] == "fail"
    assert set(result["blocking_reasons"]) == {"missing_lineage_complete", "missing_judgment_present"}


def test_promotion_gate_allows_when_all_requirements_present() -> None:
    result = evaluate_promotion_gate(
        trace_id="trace-2",
        run_id="run-2",
        eval_pass=True,
        lineage_complete=True,
        judgment_present=True,
        policy_aligned=True,
    )
    assert result["gate_status"] == "pass"
    assert result["blocking_reasons"] == []


def test_canonical_owner_emits_promotion_authority_decision() -> None:
    evidence = evaluate_promotion_gate(
        trace_id="trace-3",
        run_id="run-3",
        eval_pass=True,
        lineage_complete=True,
        judgment_present=True,
        policy_aligned=True,
    )
    decision = issue_promotion_gate_decision_from_evidence(
        evidence=evidence,
        run_id="run-3",
        trace_id="trace-3",
    )
    assert decision["artifact_type"] == "promotion_gate_decision_artifact"
    assert decision["terminal_state"] == "ready_for_merge"


def test_canonical_owner_emits_blocked_promotion_decision_with_valid_certification_status() -> None:
    evidence = evaluate_promotion_gate(
        trace_id="trace-4",
        run_id="run-4",
        eval_pass=True,
        lineage_complete=False,
        judgment_present=True,
        policy_aligned=True,
    )
    decision = issue_promotion_gate_decision_from_evidence(
        evidence=evidence,
        run_id="run-4",
        trace_id="trace-4",
    )
    assert decision["artifact_type"] == "promotion_gate_decision_artifact"
    assert decision["terminal_state"] == "blocked"
    assert decision["certification_status"] == "missing_or_incomplete"
