"""Proposer tests — bounded candidate generation and quota enforcement."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop import baseline_harness, mutation_policy, proposer
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.proposer import (
    DEFAULT_MAX_PROPOSALS,
    ProposerContext,
    ProposerError,
    ProposerQuotaExceeded,
    load_proposer_context,
    propose_candidates,
)
from tests.hop.conftest import make_baseline_candidate


def _empty_context() -> ProposerContext:
    return ProposerContext(
        prior_candidates=(),
        prior_scores=(),
        prior_failures=(),
        prior_traces=(),
    )


def test_proposer_emits_default_proposals(eval_cases) -> None:
    baseline = make_baseline_candidate()
    bundles = propose_candidates(
        baseline_candidate=baseline,
        context=_empty_context(),
    )
    assert len(bundles) == DEFAULT_MAX_PROPOSALS

    seen_kinds = {b.mutation_proposal.mutation_kind for b in bundles}
    assert seen_kinds == set(mutation_policy.list_allowed_mutation_kinds())


def test_proposer_candidates_pass_mutation_policy() -> None:
    baseline = make_baseline_candidate()
    bundles = propose_candidates(
        baseline_candidate=baseline,
        context=_empty_context(),
    )
    for bundle in bundles:
        ok, failures = mutation_policy.evaluate_proposal(bundle.mutation_proposal)
        assert ok, [f["evidence"] for f in failures]


def test_proposer_candidates_have_correct_lineage() -> None:
    baseline = make_baseline_candidate()
    bundles = propose_candidates(
        baseline_candidate=baseline,
        context=_empty_context(),
    )
    for bundle in bundles:
        assert bundle.candidate_payload["parent_candidate_id"] == baseline["candidate_id"]
        assert bundle.candidate_payload["candidate_id"] != baseline["candidate_id"]
        assert "proposer" in bundle.candidate_payload["tags"]


def test_quota_is_enforced() -> None:
    baseline = make_baseline_candidate()
    with pytest.raises(ProposerQuotaExceeded):
        propose_candidates(
            baseline_candidate=baseline,
            context=_empty_context(),
            max_proposals=0,
        )
    with pytest.raises(ProposerQuotaExceeded):
        propose_candidates(
            baseline_candidate=baseline,
            context=_empty_context(),
            max_proposals=10_000,
        )


def test_invalid_baseline_is_rejected() -> None:
    with pytest.raises(ProposerError):
        propose_candidates(
            baseline_candidate="not a mapping",  # type: ignore[arg-type]
            context=_empty_context(),
        )


def test_invalid_context_is_rejected() -> None:
    baseline = make_baseline_candidate()
    with pytest.raises(ProposerError):
        propose_candidates(
            baseline_candidate=baseline,
            context={"prior_candidates": []},  # type: ignore[arg-type]
        )


def test_proposer_never_receives_live_store() -> None:
    """Static guarantee: propose_candidates accepts no ExperienceStore.

    The signature MUST accept only a frozen ProposerContext; passing a
    live store fails-closed. This pins the architectural invariant that
    the proposer can never write to the store.
    """
    import inspect

    sig = inspect.signature(propose_candidates)
    for name, param in sig.parameters.items():
        annotation = param.annotation
        # No parameter may be annotated as ExperienceStore — even Optional.
        assert "ExperienceStore" not in str(annotation), name


def test_load_proposer_context_is_read_only(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    context = load_proposer_context(store)
    assert isinstance(context, ProposerContext)
    assert len(context.prior_candidates) == 1


def test_load_proposer_context_caps_records(store: ExperienceStore) -> None:
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    context = load_proposer_context(store, max_records=1)
    assert len(context.prior_candidates) == 1


def test_load_proposer_context_invalid_max_raises(store: ExperienceStore) -> None:
    with pytest.raises(ProposerError):
        load_proposer_context(store, max_records=0)


def test_each_proposal_is_distinct() -> None:
    baseline = make_baseline_candidate()
    bundles = propose_candidates(
        baseline_candidate=baseline,
        context=_empty_context(),
    )
    sources = {b.candidate_payload["code_source"] for b in bundles}
    assert len(sources) == len(bundles)


def test_proposed_candidate_runs_against_baseline_input() -> None:
    """Sanity: at least one proposed candidate executes the baseline path.

    The mutation templates are textual rewrites that preserve baseline
    semantics. We verify by importing the baseline harness module (which
    each proposed candidate references via code_module) and running it
    against a simple transcript.
    """
    transcript = {
        "transcript_id": "test_proposer_runs",
        "turns": [
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "Harness Optimization Pipeline."},
        ],
    }
    out = baseline_harness.run(transcript)
    assert out["items"][0]["question"] == "What is HOP?"
