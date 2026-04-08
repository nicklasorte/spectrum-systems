from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.github_pr_feedback import (
    GithubPrFeedbackError,
    build_pr_feedback_comment,
    build_roadmap_draft_feedback_comment,
)


_FIXTURES = Path("contracts/examples")


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _valid_artifacts() -> dict:
    closure = _load_fixture("closure_decision_artifact.json")
    tlc = _load_fixture("top_level_conductor_run_artifact.json")
    continuation_result = {
        "continuation_id": "gcc-1234567890abcdef",
        "final_terminal_state": "ready_for_merge",
        "roadmap_two_step": {
            "roadmap_id": "R2S-2D11D09E9BA6FD4E",
            "steps": [
                "Extract bounded implementation constraints from docs/vision.md.",
                "Map extracted constraints into governed continuation inputs using docs/roadmaps/system_roadmap.md.",
            ],
        },
    }
    artifact_paths = {
        "closure_decision_artifact": "artifacts/github_closure_continuation/pr-1/gcc-123/closure_decision_artifact.json",
        "top_level_conductor_run_artifact": "artifacts/github_closure_continuation/pr-1/gcc-123/top_level_conductor_run_artifact.json",
        "next_step_prompt_artifact": "artifacts/github_closure_continuation/pr-1/gcc-123/next_step_prompt_artifact.json",
        "promotion_gate_decision_artifact": "artifacts/github_closure_continuation/pr-1/gcc-123/promotion_gate_decision_artifact.json",
    }
    promotion_gate = _load_fixture("promotion_gate_decision_artifact.json")
    promotion_gate["terminal_state"] = "ready_for_merge"
    return {
        "closure_decision_artifact": closure,
        "top_level_conductor_run_artifact": tlc,
        "promotion_gate_decision_artifact": promotion_gate,
        "continuation_result": continuation_result,
        "artifact_paths": artifact_paths,
    }


def test_valid_artifact_input_builds_expected_markdown() -> None:
    comment = build_pr_feedback_comment(_valid_artifacts())

    expected = "\n".join(
        [
            "## Spectrum Systems — Governed Run Result",
            "",
            "**Terminal State:** ready_for_merge",
            "",
            "**Decision Type:** hardening_required",
            "",
            "**Run ID:** tlc-1a2b3c4d5e6f",
            "",
            "**Promotion Allowed:** true",
            "",
            "**Certification Status:** certified",
            "",
            "**Reason:** promotion_allowed",
            "",
            "**Artifacts:**",
            "- Closure Decision: artifacts/github_closure_continuation/pr-1/gcc-123/closure_decision_artifact.json",
            "- TLC Run: artifacts/github_closure_continuation/pr-1/gcc-123/top_level_conductor_run_artifact.json",
            "- Promotion Gate Decision: artifacts/github_closure_continuation/pr-1/gcc-123/promotion_gate_decision_artifact.json",
            "- Next Step Prompt: artifacts/github_closure_continuation/pr-1/gcc-123/next_step_prompt_artifact.json",
            "",
            "**Roadmap Input:**",
            "- Roadmap ID: R2S-2D11D09E9BA6FD4E",
            "- Step 1: Extract bounded implementation constraints from docs/vision.md.",
            "- Step 2: Map extracted constraints into governed continuation inputs using docs/roadmaps/system_roadmap.md.",
            "",
            "**Trace:**",
            "- trace-cde-2026-04-06-001",
            "- trace-tlc-0001",
            "",
            "**Missing Requirements:**",
            "- none",
            "",
            "**Notes:**",
            "- This output is machine-generated and non-authoritative.",
            "- Merge-ready visibility is emitted only from certified promotion_gate_decision_artifact outputs.",
            "- No action is taken by this system.",
            "",
        ]
    )
    assert comment == expected


def test_deterministic_output_for_same_input() -> None:
    artifacts = _valid_artifacts()
    first = build_pr_feedback_comment(deepcopy(artifacts))
    second = build_pr_feedback_comment(deepcopy(artifacts))
    assert first == second


def test_trace_refs_are_deduplicated_for_idempotent_updates() -> None:
    artifacts = _valid_artifacts()
    artifacts["top_level_conductor_run_artifact"]["trace_refs"] = ["trace-cde-2026-04-06-001", "trace-tlc-0001"]

    comment = build_pr_feedback_comment(artifacts)
    assert comment.count("- trace-cde-2026-04-06-001") == 1


def test_missing_required_artifact_fails_closed() -> None:
    artifacts = _valid_artifacts()
    artifacts.pop("closure_decision_artifact")

    with pytest.raises(GithubPrFeedbackError, match="closure_decision_artifact"):
        build_pr_feedback_comment(artifacts)


def test_no_interpretation_logic_present_in_output() -> None:
    comment = build_pr_feedback_comment(_valid_artifacts()).lower()
    forbidden_tokens = ("recommend", "should ", "consider", "suggest")
    for token in forbidden_tokens:
        assert token not in comment


def test_non_promotable_state_is_status_only_with_missing_requirements() -> None:
    artifacts = _valid_artifacts()
    artifacts["continuation_result"]["final_terminal_state"] = "blocked"
    artifacts["top_level_conductor_run_artifact"]["current_state"] = "blocked"
    artifacts["promotion_gate_decision_artifact"]["terminal_state"] = "blocked"
    artifacts["promotion_gate_decision_artifact"]["promotion_allowed"] = False
    artifacts["promotion_gate_decision_artifact"]["certification_status"] = "missing_or_incomplete"
    artifacts["promotion_gate_decision_artifact"]["missing_requirements"] = ["terminal_state_not_ready_for_merge"]

    comment = build_pr_feedback_comment(artifacts)

    assert "**Promotion Allowed:** false" in comment
    assert "**Reason:** terminal_state:blocked" in comment
    assert "**Missing Requirements:**" in comment
    assert "- terminal_state_not_ready_for_merge" in comment


def test_correct_formatting_without_optional_next_step_prompt() -> None:
    artifacts = _valid_artifacts()
    artifacts["artifact_paths"]["next_step_prompt_artifact"] = None

    comment = build_pr_feedback_comment(artifacts)

    assert "## Spectrum Systems — Governed Run Result" in comment
    assert "**Artifacts:**" in comment
    assert "- Next Step Prompt:" not in comment
    assert comment.endswith("\n")


def test_explicit_roadmap_artifact_input_is_rendered() -> None:
    artifacts = _valid_artifacts()
    artifacts["roadmap_two_step_artifact"] = _load_fixture("roadmap_two_step_artifact.json")

    comment = build_pr_feedback_comment(artifacts)

    assert "- Roadmap ID: R2S-2D11D09E9BA6FD4E" in comment
    assert comment.count("- Step 1:") == 1
    assert comment.count("- Step 2:") == 1


def test_roadmap_draft_comment_format() -> None:
    roadmap = _load_fixture("roadmap_two_step_artifact.json")
    comment = build_roadmap_draft_feedback_comment(
        {"roadmap_two_step_artifact": roadmap, "draft_id": "RMD-0001"}
    )
    assert "## Spectrum Systems — Roadmap Draft" in comment
    assert "- bounded: true" in comment
    assert "This is a preview only. No execution has occurred." in comment
