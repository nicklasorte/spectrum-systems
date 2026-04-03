from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.review_roadmap_generator import (
    ReviewRoadmapGeneratorError,
    build_review_roadmap,
)


def _snapshot() -> dict:
    snapshot = copy.deepcopy(load_example("repo_review_snapshot"))
    snapshot["roadmap_handoff"]["build_candidates"] = ["roadmap", "unscoped-expansion"]
    snapshot["roadmap_handoff"]["hardening_targets"] = ["eval-control"]
    snapshot["roadmap_handoff"]["merge_consolidation_targets"] = ["contracts"]
    snapshot["roadmap_handoff"]["defer_targets"] = ["docs"]
    return snapshot


def _program() -> dict:
    return {
        "program_id": "PRG-ROADMAP-EXECUTION",
        "allowed_targets": ["contracts", "roadmap", "eval-control", "docs"],
        "disallowed_targets": ["unscoped-expansion"],
        "priority_rules": [
            {"category": "hardening", "target": "*", "priority": 1},
            {"category": "consolidation", "target": "*", "priority": 2},
            {"category": "build", "target": "roadmap", "priority": 3},
            {"category": "defer", "target": "*", "priority": 4},
        ],
    }


def test_map_filters_disallowed_targets_from_program() -> None:
    roadmap = build_review_roadmap(
        snapshot=_snapshot(),
        control_decision={"system_response": "allow", "decision_id": "ECD-ALLOW"},
        program_artifact=_program(),
    )
    assert roadmap["filtered_out_targets"] == ["unscoped-expansion"]
    assert all(step["target"] != "unscoped-expansion" for step in roadmap["ordered_steps"])


def test_map_priority_rules_affect_ordering() -> None:
    roadmap = build_review_roadmap(
        snapshot=_snapshot(),
        control_decision={"system_response": "allow", "decision_id": "ECD-ALLOW"},
        program_artifact=_program(),
    )
    assert [step["category"] for step in roadmap["ordered_steps"]] == [
        "hardening",
        "consolidation",
        "build",
        "defer",
    ]


def test_invalid_program_constraints_fail_closed() -> None:
    bad_program = _program()
    bad_program["allowed_targets"] = ["roadmap"]
    bad_program["disallowed_targets"] = ["roadmap"]
    with pytest.raises(ReviewRoadmapGeneratorError, match="program constraint failure"):
        build_review_roadmap(
            snapshot=_snapshot(),
            control_decision={"system_response": "allow", "decision_id": "ECD-ALLOW"},
            program_artifact=bad_program,
        )
