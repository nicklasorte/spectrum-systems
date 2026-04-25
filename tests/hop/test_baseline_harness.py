"""Baseline harness behavioral tests."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop import baseline_harness
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def _input(turns):
    return {"transcript_id": "t_test", "turns": turns}


def test_baseline_pairs_user_question_with_next_assistant_answer() -> None:
    out = baseline_harness.run(
        _input(
            [
                {"speaker": "user", "text": "What is HOP?"},
                {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
            ]
        )
    )
    validate_hop_artifact(out, "hop_harness_faq_output")
    assert len(out["items"]) == 1
    assert out["items"][0]["question"] == "What is HOP?"
    assert "Harness Optimization Pipeline" in out["items"][0]["answer"]


def test_baseline_skips_non_question_turns() -> None:
    out = baseline_harness.run(
        _input(
            [
                {"speaker": "user", "text": "Tell me about HOP."},
                {"speaker": "assistant", "text": "It is a substrate."},
            ]
        )
    )
    assert out["items"] == []


def test_baseline_dedupes_exact_duplicate_qa_pairs() -> None:
    out = baseline_harness.run(
        _input(
            [
                {"speaker": "user", "text": "Why?"},
                {"speaker": "assistant", "text": "Because."},
                {"speaker": "user", "text": "Why?"},
                {"speaker": "assistant", "text": "Because."},
            ]
        )
    )
    assert len(out["items"]) == 1


def test_baseline_handles_empty_transcript() -> None:
    out = baseline_harness.run(_input([]))
    validate_hop_artifact(out, "hop_harness_faq_output")
    assert out["items"] == []


def test_baseline_skips_question_without_followup_assistant() -> None:
    out = baseline_harness.run(
        _input(
            [
                {"speaker": "user", "text": "What is HOP?"},
                {"speaker": "user", "text": "Hello?"},
            ]
        )
    )
    assert out["items"] == []


def test_baseline_pairs_two_user_questions_with_one_answer_each_only_when_present() -> None:
    out = baseline_harness.run(
        _input(
            [
                {"speaker": "user", "text": "Q1?"},
                {"speaker": "user", "text": "Q2?"},
                {"speaker": "assistant", "text": "Answer."},
            ]
        )
    )
    # Both questions point to the next assistant turn.
    assert len(out["items"]) == 2


def test_baseline_rejects_invalid_input_shape() -> None:
    with pytest.raises(ValueError):
        baseline_harness.run({"transcript_id": "x", "turns": "not_a_list"})
    with pytest.raises(ValueError):
        baseline_harness.run({"transcript_id": "", "turns": []})
    with pytest.raises(TypeError):
        baseline_harness.run("not_a_dict")  # type: ignore[arg-type]


def test_baseline_strips_leading_whitespace() -> None:
    out = baseline_harness.run(
        _input(
            [
                {"speaker": "user", "text": "   What is HOP?   "},
                {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
            ]
        )
    )
    assert out["items"][0]["question"] == "What is HOP?"
