"""Tests for HOP pattern modules.

Each pattern must produce a schema-valid ``hop_harness_faq_output``
artifact, never bypass the eval system, and behave deterministically.
The tests run the patterns through the evaluator to confirm they pass
schema validation under exactly the same gate the optimization loop
uses.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from spectrum_systems.modules.hop import patterns
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.patterns import (
    domain_router,
    draft_verify,
    label_primer,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from tests.hop.conftest import make_baseline_candidate


_TRANSCRIPT = {
    "transcript_id": "t_pattern",
    "turns": [
        {"speaker": "user", "text": "What is HOP?"},
        {"speaker": "assistant", "text": "Harness Optimization Pipeline."},
        {"speaker": "user", "text": "How do I run tests?"},
        {"speaker": "assistant", "text": "Use python -m pytest tests/hop -q to run them."},
        {"speaker": "user", "text": "Is this safe?"},
        {"speaker": "assistant", "text": "Yes, the runtime is sandboxed."},
        {"speaker": "user", "text": "Random statement, not a question."},
        {"speaker": "assistant", "text": "Filler reply."},
    ],
}


# ---------------------------------------------------------------------------
# registry / boundary
# ---------------------------------------------------------------------------


def test_pattern_registry_lists_three_patterns() -> None:
    assert sorted(patterns.list_pattern_kinds()) == [
        patterns.PATTERN_KIND_DOMAIN_ROUTER,
        patterns.PATTERN_KIND_DRAFT_VERIFY,
        patterns.PATTERN_KIND_LABEL_PRIMER,
    ]


# ---------------------------------------------------------------------------
# draft_verify
# ---------------------------------------------------------------------------


def test_draft_verify_produces_schema_valid_output() -> None:
    out = draft_verify.run(_TRANSCRIPT)
    validate_hop_artifact(out, "hop_harness_faq_output")
    assert out["candidate_id"] == draft_verify.PATTERN_ID


def test_draft_verify_drops_low_confidence_answers() -> None:
    transcript: Mapping[str, Any] = {
        "transcript_id": "t_low_conf",
        "turns": [
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "unknown"},
            {"speaker": "user", "text": "What does it do?"},
            {"speaker": "assistant", "text": "It optimizes harnesses."},
        ],
    }
    out = draft_verify.run(transcript)
    questions = [item["question"] for item in out["items"]]
    assert "What is HOP?" not in questions
    assert "What does it do?" in questions


def test_draft_verify_is_deterministic() -> None:
    a = draft_verify.run(_TRANSCRIPT)
    b = draft_verify.run(_TRANSCRIPT)
    a.pop("generated_at")
    b.pop("generated_at")
    a.pop("artifact_id")
    b.pop("artifact_id")
    a.pop("content_hash")
    b.pop("content_hash")
    assert a == b


def test_draft_verify_rejects_bad_input() -> None:
    with pytest.raises(TypeError):
        draft_verify.run("not a dict")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        draft_verify.run({"transcript_id": "", "turns": []})


# ---------------------------------------------------------------------------
# label_primer
# ---------------------------------------------------------------------------


def test_label_primer_produces_schema_valid_output() -> None:
    out = label_primer.run(_TRANSCRIPT)
    validate_hop_artifact(out, "hop_harness_faq_output")
    assert out["candidate_id"] == label_primer.PATTERN_ID


def test_label_primer_skips_user_statements() -> None:
    out = label_primer.run(_TRANSCRIPT)
    questions = [item["question"] for item in out["items"]]
    assert "Random statement, not a question." not in questions


def test_label_primer_skips_filler_assistant() -> None:
    transcript: Mapping[str, Any] = {
        "transcript_id": "t_filler",
        "turns": [
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "   "},  # filler
        ],
    }
    out = label_primer.run(transcript)
    assert out["items"] == []


def test_label_primer_rejects_bad_input() -> None:
    with pytest.raises(TypeError):
        label_primer.run("not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# domain_router
# ---------------------------------------------------------------------------


def test_domain_router_produces_schema_valid_output() -> None:
    out = domain_router.run(_TRANSCRIPT)
    validate_hop_artifact(out, "hop_harness_faq_output")
    assert out["candidate_id"] == domain_router.PATTERN_ID


def test_domain_router_classifies_questions() -> None:
    assert domain_router.route_question("What is HOP?") == domain_router.DOMAIN_DEFINITION
    assert domain_router.route_question("How do I run tests?") == domain_router.DOMAIN_HOWTO
    assert domain_router.route_question("Is this safe?") == domain_router.DOMAIN_YES_NO
    assert domain_router.route_question("Where now?") == domain_router.DOMAIN_GENERAL


def test_domain_router_drops_yes_no_answer_without_yes_or_no() -> None:
    transcript: Mapping[str, Any] = {
        "transcript_id": "t_yn",
        "turns": [
            {"speaker": "user", "text": "Is this safe?"},
            {"speaker": "assistant", "text": "Maybe sometime later."},
        ],
    }
    out = domain_router.run(transcript)
    assert out["items"] == []


def test_domain_router_keeps_yes_no_with_yes() -> None:
    transcript: Mapping[str, Any] = {
        "transcript_id": "t_yes",
        "turns": [
            {"speaker": "user", "text": "Is this safe?"},
            {"speaker": "assistant", "text": "Yes, it is sandboxed."},
        ],
    }
    out = domain_router.run(transcript)
    assert len(out["items"]) == 1


def test_domain_router_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        domain_router.run({"transcript_id": "x", "turns": "not a list"})


# ---------------------------------------------------------------------------
# patterns flow through the evaluator gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern_module",
    [draft_verify, label_primer, domain_router],
)
def test_pattern_runs_through_evaluator_gate(
    pattern_module, eval_set: EvalSet, eval_cases, store: ExperienceStore
) -> None:
    """A pattern's output must pass the evaluator's per-case schema check.

    We use a baseline-shaped candidate envelope (the candidate
    metadata is unrelated to which runner the evaluator invokes; the
    candidate body just needs to admit cleanly).
    """
    candidate = make_baseline_candidate()
    result = evaluate_candidate(
        candidate_payload=candidate,
        runner=pattern_module.run,
        eval_set=eval_set,
        store=store,
    )
    # Every emitted trace must validate; the run/score envelopes must
    # also validate. We don't assert score=1.0 because patterns are
    # deliberately not optimized for the eval set.
    for trace in result["traces"]:
        validate_hop_artifact(trace, "hop_harness_trace")
    validate_hop_artifact(result["run"], "hop_harness_run")
    validate_hop_artifact(result["score"], "hop_harness_score")
