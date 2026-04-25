"""Mutation policy tests — forbidden mutations + path-scope enforcement."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop import mutation_policy
from spectrum_systems.modules.hop.mutation_policy import (
    MutationProposal,
    evaluate_proposal,
)


_BASELINE = (
    "from typing import Any, Mapping\n"
    "def run(transcript: Mapping[str, Any]) -> dict:\n"
    "    return {'items': [], 'transcript_id': transcript['transcript_id'],"
    " 'candidate_id': 'baseline_v1'}\n"
)


def _proposal(
    *,
    code: str,
    candidate_id: str = "proposer_test",
    modified_paths=("spectrum_systems/modules/hop/baseline_harness.py",),
    mutation_kind: str = "additive_context",
) -> MutationProposal:
    return MutationProposal(
        candidate_id=candidate_id,
        candidate_code_source=code,
        candidate_module_path="spectrum_systems/modules/hop/baseline_harness.py",
        baseline_code_source=_BASELINE,
        modified_paths=tuple(modified_paths),
        mutation_kind=mutation_kind,
    )


def test_clean_proposal_passes() -> None:
    ok, failures = evaluate_proposal(_proposal(code=_BASELINE))
    assert ok is True
    assert failures == []


def test_modified_path_outside_candidate_is_rejected() -> None:
    proposal = _proposal(
        code=_BASELINE,
        modified_paths=(
            "spectrum_systems/modules/hop/baseline_harness.py",
            "spectrum_systems/modules/hop/evaluator.py",
        ),
    )
    ok, failures = evaluate_proposal(proposal)
    assert not ok
    assert any("illegal_modified_paths" in e["detail"]
               for f in failures for e in f["evidence"])


def test_forbidden_import_is_rejected() -> None:
    code = "import urllib.request\n" + _BASELINE
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("forbidden_imports" in e["detail"]
               for f in failures for e in f["evidence"])


def test_forbidden_call_is_rejected() -> None:
    code = "import os\n" + _BASELINE.replace(
        "return {'items'", "os.system('ls'); return {'items'"
    )
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("forbidden_calls" in e["detail"]
               for f in failures for e in f["evidence"])


def test_eval_dir_literal_is_rejected() -> None:
    code = (
        _BASELINE
        + "_LEAK = 'contracts/evals/hop'\n"
    )
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("literal_eval_directory_reference" in e["detail"]
               for f in failures for e in f["evidence"])


def test_env_access_is_rejected() -> None:
    code = (
        "import os\n"
        + _BASELINE.replace(
            "return {'items'",
            "_secret = os.environ.get('SECRET'); return {'items'",
        )
    )
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("hidden_state" in e["detail"]
               for f in failures for e in f["evidence"])


def test_field_removal_via_pop_is_rejected() -> None:
    code = (
        _BASELINE.replace(
            "return {'items'",
            "payload = {'items': [], 'transcript_id': 'x', 'candidate_id': 'x'};"
            " payload.pop('items'); return payload\n# ",
        )
    )
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("removed_required_fields" in e["detail"]
               for f in failures for e in f["evidence"])


def test_field_removal_via_del_attr_is_rejected() -> None:
    code = (
        _BASELINE.replace(
            "return {'items'",
            "class P: items = []\np = P(); del p.items; return {'items'",
        )
    )
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("removed_required_fields" in e["detail"]
               for f in failures for e in f["evidence"])


def test_obfuscated_import_is_caught() -> None:
    """Even when wrapped in importlib, the call is forbidden."""
    code = _BASELINE + "import subprocess\n"
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok


def test_syntax_error_fails_closed() -> None:
    code = "def run(\n  this is not python\n"
    ok, failures = evaluate_proposal(_proposal(code=code))
    assert not ok
    assert any("SyntaxError" in e["detail"]
               for f in failures for e in f["evidence"])


def test_invalid_proposal_object_raises() -> None:
    with pytest.raises(mutation_policy.MutationPolicyError):
        evaluate_proposal({"not": "a_proposal"})  # type: ignore[arg-type]


def test_allowed_mutation_kinds_is_stable() -> None:
    kinds = mutation_policy.list_allowed_mutation_kinds()
    assert set(kinds) == {
        "additive_context",
        "ordering",
        "retrieval_logic",
        "prompt_structure",
    }
