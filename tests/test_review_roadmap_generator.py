from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.review_roadmap_generator import (
    ReviewRoadmapGeneratorError,
    build_review_roadmap,
)


def _snapshot() -> dict:
    return copy.deepcopy(load_example("repo_review_snapshot"))


def test_review_roadmap_extracts_structured_handoff() -> None:
    roadmap = build_review_roadmap(
        snapshot=_snapshot(),
        control_decision={"system_response": "allow", "decision_id": "ECD-ALLOW"},
    )
    assert roadmap["generation_status"] == "generated"
    assert roadmap["hardening_targets"]
    assert roadmap["build_candidates"]
    categories = [step["category"] for step in roadmap["ordered_steps"]]
    assert categories.index("hardening") < categories.index("build")
    assert categories.index("consolidation") < categories.index("build")


def test_review_roadmap_warn_downgrades_expansion() -> None:
    roadmap = build_review_roadmap(
        snapshot=_snapshot(),
        control_decision={"system_response": "warn", "decision_id": "ECD-WARN"},
    )
    assert roadmap["readiness"] == "degraded"
    assert all(step["category"] != "build" for step in roadmap["ordered_steps"])


@pytest.mark.parametrize("response", ["freeze", "block"])
def test_review_roadmap_unsafe_response_blocks_generation(response: str) -> None:
    roadmap = build_review_roadmap(
        snapshot=_snapshot(),
        control_decision={"system_response": response, "decision_id": "ECD-BLOCK"},
    )
    assert roadmap["generation_status"] == "blocked"
    assert roadmap["ordered_steps"] == []


def test_review_roadmap_fails_closed_without_structured_handoff() -> None:
    snapshot = _snapshot()
    snapshot.pop("roadmap_handoff", None)
    with pytest.raises(ReviewRoadmapGeneratorError, match="roadmap_handoff"):
        build_review_roadmap(snapshot=snapshot, control_decision={"system_response": "allow", "decision_id": "ECD-1"})
