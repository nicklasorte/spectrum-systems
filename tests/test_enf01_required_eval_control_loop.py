from __future__ import annotations

from spectrum_systems.modules.runtime.required_eval_coverage import (
    enforce_required_eval_coverage,
    load_required_eval_registry,
)


def _control_decision_from_enforcement(decision: str) -> str:
    if decision == "allow":
        return "allow"
    if decision == "freeze":
        return "freeze"
    return "block"


def _eval_pack(*, trace_complete: bool = True) -> list[dict]:
    return [
        {
            "eval_id": "complexity_justification_valid",
            "passed": True,
            "complexity_justification_record": {
                "failure_prevented": "ungoverned expansion drift",
                "signal_improved": "required_eval_precondition_coverage_rate",
                "measurable_metric": "required_eval_precondition_coverage_rate",
                "why_not_existing_owner": "Existing owner artifacts do not encode ENF-01 complexity precondition evidence.",
                "duplicate_of_system": None,
                "justification_status": "approved",
            },
        },
        {
            "eval_id": "core_loop_alignment_valid",
            "passed": True,
            "core_loop_alignment_record": {
                "maps_to_stages": ["execution", "evaluation", "control", "enforcement"],
                "strengthens_existing_loop": True,
                "introduces_parallel_loop": False,
                "loop_impact_score": 0.9,
            },
        },
        {
            "eval_id": "debuggability_valid",
            "passed": True,
            "debuggability_record": {
                "trace_complete": trace_complete,
                "lineage_complete": True,
                "replay_expected": True,
                "replay_supported": True,
                "failure_modes_defined": ["missing_required_eval_artifact"],
                "reason_codes_defined": True,
            },
        },
    ]


def test_enf01_near_end_to_end_allows_when_artifacts_and_required_evals_pass() -> None:
    registry = load_required_eval_registry()
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=[
            "complexity_justification_valid",
            "core_loop_alignment_valid",
            "debuggability_valid",
        ],
        eval_results=_eval_pack(),
        trace_id="trace-e2e-enf01",
        run_id="run-e2e-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=registry,
    )

    assert output["coverage_registry"]["required_evals_present"] == [
        "complexity_justification_valid",
        "core_loop_alignment_valid",
        "debuggability_valid",
    ]
    assert output["enforcement"]["decision"] == "allow"
    assert _control_decision_from_enforcement(output["enforcement"]["decision"]) == "allow"


def test_enf01_near_end_to_end_blocks_when_debuggability_evidence_fails() -> None:
    registry = load_required_eval_registry()
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=[
            "complexity_justification_valid",
            "core_loop_alignment_valid",
            "debuggability_valid",
        ],
        eval_results=_eval_pack(trace_complete=False),
        trace_id="trace-e2e-enf01",
        run_id="run-e2e-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=registry,
    )

    assert output["enforcement"]["decision"] == "block"
    assert _control_decision_from_enforcement(output["enforcement"]["decision"]) == "block"
