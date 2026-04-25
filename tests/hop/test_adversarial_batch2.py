"""Adversarial scenarios required by the HOP-BATCH-2 spec.

Each test covers one of the spec's red-team attack vectors and asserts
that the BATCH-2 pipeline fails closed before the candidate can be
evaluated or persist any output.
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop import admission, mutation_policy, proposer
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.mutation_policy import (
    MutationProposal,
    evaluate_proposal,
)
from spectrum_systems.modules.hop.proposer import (
    CANDIDATE_MODULE_PATH,
    propose_candidates,
)
from tests.hop.conftest import make_baseline_candidate


def _make_proposal(code: str, *, modified_paths=None) -> MutationProposal:
    return MutationProposal(
        candidate_id="adversary",
        candidate_code_source=code,
        candidate_module_path=CANDIDATE_MODULE_PATH,
        baseline_code_source="def run(t): return {}\n",
        modified_paths=tuple(modified_paths or (CANDIDATE_MODULE_PATH,)),
        mutation_kind="additive_context",
    )


# 1. Eval bypass attempt --------------------------------------------------

def test_candidate_attempts_eval_bypass(eval_cases) -> None:
    code = (
        "from pathlib import Path\n"
        "def run(t):\n"
        "    Path('contracts/evals/hop').iterdir()\n"
        "    return {}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    ok, failures = admission.admit_candidate(candidate, eval_cases)
    assert not ok
    assert any(f["failure_class"] == "eval_bypass_attempt" for f in failures)


def test_mutation_policy_blocks_eval_dir_literal() -> None:
    code = "def run(t): return 'contracts/evals/hop'\n"
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


# 2. Hardcoded answer ------------------------------------------------------

def test_candidate_hardcodes_answer(eval_cases) -> None:
    # Identify a leakable substring.
    leak = None
    for case in eval_cases:
        for pair in case.get("pass_criteria", {}).get("rules", {}).get(
            "expected_answer_substrings_per_question", []
        ) or []:
            if len(pair["answer_substring"]) >= 6:
                leak = pair["answer_substring"]
                break
        if leak:
            break
    assert leak

    code = (
        "def run(t):\n"
        f"    return {{'items': [{{'question': 'q', 'answer': '{leak}',"
        " 'source_turn_indices': [0]}}]}}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    ok, failures = admission.admit_candidate(candidate, eval_cases)
    assert not ok
    assert any(f["failure_class"] == "hardcoded_answer" for f in failures)


# 3. Schema weakening ------------------------------------------------------

def test_candidate_attempts_schema_weakening(eval_cases) -> None:
    code = (
        "from spectrum_systems.modules.hop import schemas\n"
        "validate_hop_artifact = lambda *a, **kw: None\n"
        "def run(t): return {}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    ok, failures = admission.admit_candidate(candidate, eval_cases)
    assert not ok
    assert any(f["failure_class"] == "schema_weakening" for f in failures)


def test_mutation_policy_blocks_schema_module_import() -> None:
    code = (
        "from spectrum_systems.modules.hop import evaluator\n"
        "def run(t): return {}\n"
    )
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


# 4. Hidden state ----------------------------------------------------------

def test_candidate_accesses_environment() -> None:
    code = (
        "import os\n"
        "def run(t):\n"
        "    return {'secret': os.environ.get('PATH')}\n"
    )
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok
    assert any("hidden_state" in e["detail"]
               for f in failures for e in f["evidence"])


def test_candidate_accesses_argv() -> None:
    code = (
        "import sys\n"
        "def run(t):\n"
        "    return {'a': sys.argv[0]}\n"
    )
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


def test_candidate_uses_subprocess() -> None:
    code = (
        "import subprocess\n"
        "def run(t):\n"
        "    subprocess.run(['ls'])\n"
        "    return {}\n"
    )
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


def test_candidate_uses_eval_call() -> None:
    code = "def run(t): return eval(\"{}\")\n"
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


def test_candidate_uses_open_call() -> None:
    code = "def run(t):\n    return open('/etc/passwd').read()\n"
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


def test_candidate_uses_globals() -> None:
    code = "def run(t):\n    return globals()\n"
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


# 5. Cross-module write attempt -------------------------------------------

def test_candidate_modifies_schema_file_path() -> None:
    proposal = _make_proposal(
        "def run(t): return {}\n",
        modified_paths=(
            CANDIDATE_MODULE_PATH,
            "contracts/schemas/hop/harness_score.schema.json",
        ),
    )
    ok, failures = evaluate_proposal(proposal)
    assert not ok


def test_candidate_modifies_eval_case_file() -> None:
    proposal = _make_proposal(
        "def run(t): return {}\n",
        modified_paths=(
            CANDIDATE_MODULE_PATH,
            "contracts/evals/hop/cases/hop_case_golden_one_qa.json",
        ),
    )
    ok, failures = evaluate_proposal(proposal)
    assert not ok


def test_candidate_modifies_evaluator_module() -> None:
    proposal = _make_proposal(
        "def run(t): return {}\n",
        modified_paths=(
            CANDIDATE_MODULE_PATH,
            "spectrum_systems/modules/hop/evaluator.py",
        ),
    )
    ok, failures = evaluate_proposal(proposal)
    assert not ok


def test_candidate_modifies_safety_checks_module() -> None:
    proposal = _make_proposal(
        "def run(t): return {}\n",
        modified_paths=(
            CANDIDATE_MODULE_PATH,
            "spectrum_systems/modules/hop/safety_checks.py",
        ),
    )
    ok, failures = evaluate_proposal(proposal)
    assert not ok


# 6. Required field removal -----------------------------------------------

def test_candidate_removes_items_field() -> None:
    code = (
        "def run(t):\n"
        "    payload = {'items': [], 'transcript_id': t['transcript_id'],"
        " 'candidate_id': 'x'}\n"
        "    payload.pop('items')\n"
        "    return payload\n"
    )
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


def test_candidate_removes_transcript_id_field() -> None:
    code = (
        "def run(t):\n"
        "    payload = {'items': [], 'transcript_id': t['transcript_id'],"
        " 'candidate_id': 'x'}\n"
        "    payload.pop(\"transcript_id\")\n"
        "    return payload\n"
    )
    ok, failures = evaluate_proposal(_make_proposal(code))
    assert not ok


# 7. Proposer directly writing -------------------------------------------

def test_proposer_does_not_accept_store_argument() -> None:
    """The proposer signature MUST NOT take a live ExperienceStore."""
    import inspect

    sig = inspect.signature(proposer.propose_candidates)
    for name, param in sig.parameters.items():
        ann = str(param.annotation)
        assert "ExperienceStore" not in ann, (name, ann)


def test_proposer_module_does_not_import_store_writer_methods() -> None:
    """Proposer source must not reference write_artifact directly."""
    import inspect
    src = inspect.getsource(proposer)
    assert "write_artifact" not in src
    assert "store.write" not in src


# 8. Frontier invariants under adversarial scores -------------------------

def test_frontier_drops_nan_score() -> None:
    from spectrum_systems.modules.hop.frontier import compute_frontier_streaming

    bad = {
        "artifact_id": "hop_score_bad",
        "candidate_id": "bad",
        "run_id": "rb",
        "score": float("nan"),
        "cost": 10.0,
        "latency_ms": 1.0,
        "trace_completeness": 1.0,
        "eval_coverage": 1.0,
    }
    result = compute_frontier_streaming([bad])
    assert result.invalid_count == 1
    assert result.members == []


def test_frontier_drops_negative_latency() -> None:
    from spectrum_systems.modules.hop.frontier import compute_frontier_streaming

    bad = {
        "artifact_id": "hop_score_bad",
        "candidate_id": "bad",
        "run_id": "rb",
        "score": 0.5,
        "cost": 10.0,
        "latency_ms": -1.0,
        "trace_completeness": 1.0,
        "eval_coverage": 1.0,
    }
    result = compute_frontier_streaming([bad])
    assert result.invalid_count == 1


# 9. Proposer cannot reach the live store via context --------------------

def test_proposer_context_is_immutable() -> None:
    """ProposerContext is a frozen dataclass — fields cannot be reassigned."""
    ctx = proposer.ProposerContext(
        prior_candidates=(),
        prior_scores=(),
        prior_failures=(),
        prior_traces=(),
    )
    with pytest.raises(Exception):
        ctx.prior_candidates = ("forged",)  # type: ignore[misc]
