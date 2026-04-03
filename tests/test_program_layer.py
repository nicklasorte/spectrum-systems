from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.program_layer import (
    apply_program_constraints,
    build_program_progress,
    get_batch_program_mapping,
    resolve_program_for_batch,
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
