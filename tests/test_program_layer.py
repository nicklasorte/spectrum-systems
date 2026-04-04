from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.program_layer import (
    apply_program_constraints,
    build_program_constraint_signal,
    build_program_feedback_record,
    build_program_progress,
    detect_program_drift,
    get_batch_program_mapping,
    resolve_program_for_batch,
    validate_roadmap_against_program,
)


def _program_artifact() -> dict:
    return {
        "program_id": "PRG-ROADMAP-EXECUTION",
        "schema_version": "1.0.0",
        "title": "Program",
        "goal": "Constrain roadmap output",
        "batches": ["BATCH-D", "BATCH-E", "BATCH-F", "BATCH-G"],
        "success_criteria": ["deterministic output"],
        "blocking_conditions": [],
        "allowed_targets": ["contracts", "roadmap", "eval-control"],
        "disallowed_targets": ["unscoped-expansion"],
        "priority_rules": [
            {"category": "hardening", "target": "*", "priority": 1},
            {"category": "consolidation", "target": "*", "priority": 2},
            {"category": "build", "target": "roadmap", "priority": 3},
            {"category": "defer", "target": "*", "priority": 4},
        ],
        "status": "active",
        "created_at": "2026-04-03T00:00:00Z",
        "trace_id": "trace-prg-001",
        "source_refs": ["docs/roadmaps/system_roadmap.md"],
    }


def test_program_contract_examples_validate() -> None:
    validate_artifact(_program_artifact(), "program_artifact")


def test_batch_to_program_mapping_is_deterministic_and_complete_a_to_m() -> None:
    mapping = get_batch_program_mapping()
    assert len(mapping) == 13
    assert sorted(mapping.keys()) == [f"BATCH-{letter}" for letter in "ABCDEFGHIJKLM"]
    assert resolve_program_for_batch("batch-d") == "PRG-ROADMAP-EXECUTION"


def test_apply_program_constraints_filters_disallowed_and_applies_priority() -> None:
    constrained = apply_program_constraints(
        steps=[
            {"category": "build", "target": "unscoped-expansion"},
            {"category": "build", "target": "roadmap"},
            {"category": "consolidation", "target": "contracts"},
            {"category": "hardening", "target": "eval-control"},
        ],
        program_artifact=_program_artifact(),
    )
    assert constrained.filtered_out_targets == ["unscoped-expansion"]
    assert constrained.ordered_steps == [
        {"category": "hardening", "target": "eval-control"},
        {"category": "consolidation", "target": "contracts"},
        {"category": "build", "target": "roadmap"},
    ]


def test_program_progress_is_deterministic() -> None:
    first = build_program_progress(
        program_artifact=_program_artifact(),
        completed_batches=["BATCH-E", "BATCH-D"],
        trace_id="trace-prg-progress-001",
    )
    second = build_program_progress(
        program_artifact=_program_artifact(),
        completed_batches=["BATCH-D", "BATCH-E"],
        trace_id="trace-prg-progress-001",
    )
    assert first == second
    validate_artifact(first, "program_progress")
    assert first["progress_percentage"] == 50.0


def test_program_constraint_signal_is_deterministic_and_valid() -> None:
    first = build_program_constraint_signal(program_artifact=_program_artifact(), trace_id="trace-prg-constraint-001")
    second = build_program_constraint_signal(program_artifact=_program_artifact(), trace_id="trace-prg-constraint-001")
    assert first == second
    validate_artifact(first, "program_constraint_signal")


def test_validate_roadmap_against_program_detects_disallowed_target() -> None:
    signal = build_program_constraint_signal(
        program_artifact={**_program_artifact(), "allowed_targets": ["BATCH-D"], "batches": ["BATCH-D"]},
        trace_id="trace-prg-align-001",
    )
    result = validate_roadmap_against_program(
        roadmap_artifact={"roadmap_id": "RDX-TEST-1", "goal": "deterministic output", "batches": [{"batch_id": "BATCH-E"}]},
        program_constraint_signal=signal,
    )
    assert result["alignment_status"] == "invalid"
    assert result["fail_closed"] is True
    assert any(item["reason_code"] == "target_not_allowed" for item in result["violations"])
    validate_artifact(result, "program_roadmap_alignment_result")


def test_program_drift_signal_detects_priority_violation() -> None:
    signal = build_program_constraint_signal(
        program_artifact={**_program_artifact(), "allowed_targets": ["BATCH-D", "BATCH-E"], "batches": ["BATCH-D", "BATCH-E"]},
        trace_id="trace-prg-drift-001",
    )
    drift = detect_program_drift(
        program_constraint_signal=signal,
        executed_batches=["BATCH-E", "BATCH-D"],
        planned_batches=["BATCH-D", "BATCH-E"],
        trace_id="trace-prg-drift-001",
    )
    assert drift["drift_detected"] is True
    assert drift["drift_type"] == "priority_violation"
    validate_artifact(drift, "program_drift_signal")


def test_program_feedback_record_validates() -> None:
    record = build_program_feedback_record(
        program_id="PRG-ROADMAP-EXECUTION",
        completed_batches=["BATCH-D"],
        blocked_batches=["BATCH-E"],
        recurring_failures=["missing_required_signal"],
        drift_signals=["priority_violation"],
        risk_signals=["risk_level:high"],
        improvement_recommendations=["reorder batches"],
        trace_id="trace-prg-feedback-001",
    )
    validate_artifact(record, "program_feedback_record")
