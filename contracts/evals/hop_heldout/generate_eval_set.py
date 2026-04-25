#!/usr/bin/env python3
"""Deterministic generator for the HOP held-out advisory eval set.

The held-out set is *separate* from the search eval set
(``contracts/evals/hop``). Candidate harnesses must score well on BOTH
sets — the held-out set surfaces overfitting on the search set as a
regression on disjoint inputs. The harness merely packages an advisory
readiness signal; release/promotion remains the canonical concern of
REL/CDE per ``contracts/governance/authority_registry.json``.

Cases here are intentionally distinct in transcript content, structure,
and phrasing from the search set. They share the same JSON schema and
judges. Transcript content stays free of authority-shaped vocabulary so
the held-out cases cannot be confused with control-plane artifacts and
do not mislead future prompts.

Run::

    python contracts/evals/hop_heldout/generate_eval_set.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace  # noqa: E402
from spectrum_systems.modules.hop.schemas import validate_hop_artifact  # noqa: E402

EVAL_SET_ID = "hop_transcript_to_faq_heldout_v1"
EVAL_SET_VERSION = "1.0.0"
CASE_VERSION = "1.0.0"
CASES_DIR = Path(__file__).resolve().parent / "cases"
MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"


def _case(
    *,
    slug: str,
    category: str,
    transcript_id: str,
    turns: list[dict[str, str]],
    pass_criteria: dict[str, Any],
    failure_modes_targeted: list[str],
) -> dict[str, Any]:
    eval_case_id = f"hop_case_heldout_{slug}"
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_eval_case",
        "schema_ref": "hop/harness_eval_case.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=f"hop_eval_set:{EVAL_SET_ID}:{slug}"),
        "eval_case_id": eval_case_id,
        "eval_case_version": CASE_VERSION,
        "category": category,
        "input": {"transcript_id": transcript_id, "turns": turns},
        "pass_criteria": pass_criteria,
        "failure_modes_targeted": failure_modes_targeted,
    }
    finalize_artifact(payload, id_prefix="hop_eval_case_")
    validate_hop_artifact(payload, "hop_harness_eval_case")
    return payload


# --- golden cases (held-out) --------------------------------------------------


def _heldout_golden_pricing() -> dict[str, Any]:
    return _case(
        slug="golden_pricing",
        category="golden",
        transcript_id="t_heldout_pricing",
        turns=[
            {"speaker": "user", "text": "How much does the eval bundle cost?"},
            {"speaker": "assistant", "text": "The eval bundle is included with the harness."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["eval bundle"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "eval bundle", "answer_substring": "included"},
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _heldout_golden_meta_question() -> dict[str, Any]:
    return _case(
        slug="golden_meta_question",
        category="golden",
        transcript_id="t_heldout_meta",
        turns=[
            {"speaker": "user", "text": "Who routes inputs through the harness?"},
            {"speaker": "assistant", "text": "An external router queues inputs."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["routes inputs"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "routes inputs", "answer_substring": "router"},
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _heldout_golden_paired_topics() -> dict[str, Any]:
    return _case(
        slug="golden_paired_topics",
        category="golden",
        transcript_id="t_heldout_paired",
        turns=[
            {"speaker": "user", "text": "What is the held-out set?"},
            {"speaker": "assistant", "text": "It is a disjoint eval cohort the harness scores against."},
            {"speaker": "user", "text": "How is it disjoint?"},
            {"speaker": "assistant", "text": "Cases share zero transcript_ids with the search set."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 2,
                "max_qa_pairs": 2,
                "expected_questions_substrings": ["held-out set", "disjoint"],
            },
        },
        failure_modes_targeted=[],
    )


def _heldout_golden_long_answer() -> dict[str, Any]:
    return _case(
        slug="golden_long_answer",
        category="golden",
        transcript_id="t_heldout_long",
        turns=[
            {"speaker": "user", "text": "Why hold cases out at all?"},
            {
                "speaker": "assistant",
                "text": (
                    "Held-out cases catch overfitting. A candidate that gamed the "
                    "search set will surface a regression on disjoint inputs."
                ),
            },
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["hold cases out"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "hold cases out", "answer_substring": "overfitting"},
                ],
            },
        },
        failure_modes_targeted=["long_answer_truncation"],
    )


def _heldout_golden_dedup_paraphrase() -> dict[str, Any]:
    return _case(
        slug="golden_dedup_identical_qa",
        category="golden",
        transcript_id="t_heldout_dedup",
        turns=[
            {"speaker": "user", "text": "Is the input cached?"},
            {"speaker": "assistant", "text": "The input is cached for a single run."},
            {"speaker": "user", "text": "Is the input cached?"},
            {"speaker": "assistant", "text": "The input is cached for a single run."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["input cached"],
            },
        },
        failure_modes_targeted=["duplicate_questions"],
    )


def _heldout_golden_three_topic() -> dict[str, Any]:
    return _case(
        slug="golden_three_topic",
        category="golden",
        transcript_id="t_heldout_three",
        turns=[
            {"speaker": "user", "text": "What does eval_factory ingest?"},
            {"speaker": "assistant", "text": "It ingests failures and near misses."},
            {"speaker": "user", "text": "What does it emit?"},
            {"speaker": "assistant", "text": "It emits new eval cases."},
            {"speaker": "user", "text": "How is the eval set versioned?"},
            {"speaker": "assistant", "text": "Each generation bumps the eval_set_version."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 3,
                "max_qa_pairs": 3,
                "expected_questions_substrings": ["ingest", "emit", "versioned"],
            },
        },
        failure_modes_targeted=[],
    )


# --- harder golden cases (held-out, HOP-005) ---------------------------------


def _heldout_golden_long_multi_sentence_answer() -> dict[str, Any]:
    """Long multi-sentence answer; baseline must preserve the full body."""
    return _case(
        slug="golden_long_multi_sentence_answer",
        category="golden",
        transcript_id="t_heldout_long_multi",
        turns=[
            {"speaker": "user", "text": "What invariants does the held-out set keep?"},
            {
                "speaker": "assistant",
                "text": (
                    "Three invariants. First, transcript_id disjointness from the "
                    "search set. Second, content_hash integrity per case. Third, "
                    "manifest tamper-evidence: any mismatch fails the loader closed."
                ),
            },
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["invariants"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "invariants", "answer_substring": "tamper-evidence"},
                ],
            },
        },
        failure_modes_targeted=["long_answer_truncation"],
    )


def _heldout_golden_topic_switch_three_qa() -> dict[str, Any]:
    """Three Q/A pairs on three distinct topics; pairing must not bleed."""
    return _case(
        slug="golden_topic_switch_three_qa",
        category="golden",
        transcript_id="t_heldout_topic_switch",
        turns=[
            {"speaker": "user", "text": "Where do failure hypotheses live?"},
            {"speaker": "assistant", "text": "They live in the experience store under their own kind."},
            {"speaker": "user", "text": "What seeds the proposer?"},
            {"speaker": "assistant", "text": "The proposer seeds from prior trace diffs and failures."},
            {"speaker": "user", "text": "Why is the loop deterministic?"},
            {"speaker": "assistant", "text": "Determinism keeps frontier recomputes reproducible."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 3,
                "max_qa_pairs": 3,
                "expected_questions_substrings": [
                    "failure hypotheses",
                    "seeds the proposer",
                    "deterministic",
                ],
            },
        },
        failure_modes_targeted=["interleaved_speakers"],
    )


def _heldout_golden_orphan_assistant_then_qa() -> dict[str, Any]:
    """Leading assistant turn must not become a phantom answer."""
    return _case(
        slug="golden_orphan_assistant_then_qa",
        category="golden",
        transcript_id="t_heldout_orphan_assistant",
        turns=[
            {"speaker": "assistant", "text": "Welcome to the harness."},
            {"speaker": "user", "text": "What does the harness emit?"},
            {"speaker": "assistant", "text": "The harness emits an FAQ output artifact."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["harness emit"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "harness emit", "answer_substring": "FAQ output"},
                ],
            },
        },
        failure_modes_targeted=["interleaved_speakers"],
    )


# --- adversarial cases (held-out) --------------------------------------------


def _heldout_adv_no_assistant_followup() -> dict[str, Any]:
    return _case(
        slug="adversarial_no_followup",
        category="adversarial",
        transcript_id="t_heldout_no_followup",
        turns=[
            {"speaker": "user", "text": "Where does the trace artifact go?"},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["single_turn"],
    )


def _heldout_adv_only_statements() -> dict[str, Any]:
    return _case(
        slug="adversarial_only_statements",
        category="adversarial",
        transcript_id="t_heldout_only_statements",
        turns=[
            {"speaker": "user", "text": "I am stating a fact, not asking."},
            {"speaker": "assistant", "text": "Acknowledged."},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["no_questions"],
    )


def _heldout_adv_two_questions_no_answer() -> dict[str, Any]:
    return _case(
        slug="adversarial_two_questions_no_answer",
        category="adversarial",
        transcript_id="t_heldout_two_q_no_a",
        turns=[
            {"speaker": "user", "text": "Why?"},
            {"speaker": "user", "text": "When?"},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["ambiguous_attribution"],
    )


def _heldout_adv_question_no_qmark() -> dict[str, Any]:
    return _case(
        slug="adversarial_question_no_qmark",
        category="adversarial",
        transcript_id="t_heldout_no_qmark",
        turns=[
            {"speaker": "user", "text": "Tell me about input batches."},
            {"speaker": "assistant", "text": "Batches are sized by the harness config."},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["non_question_marked_question"],
    )


def _heldout_adv_forbidden_marker() -> dict[str, Any]:
    return _case(
        slug="adversarial_forbidden_marker",
        category="adversarial",
        transcript_id="t_heldout_forbidden",
        turns=[
            {"speaker": "user", "text": "Does the held-out set check leakage?"},
            {"speaker": "assistant", "text": "Yes, the held-out set is disjoint by transcript_id."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "forbidden_substrings_in_answers": ["__hop_heldout_leak__"],
            },
        },
        failure_modes_targeted=["leakage_attempt"],
    )


def _heldout_adv_empty() -> dict[str, Any]:
    return _case(
        slug="adversarial_empty_transcript",
        category="adversarial",
        transcript_id="t_heldout_empty",
        turns=[],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["empty_transcript"],
    )


# --- harder adversarial cases (held-out, HOP-005) ----------------------------


def _heldout_adv_qmark_inside_assistant_text() -> dict[str, Any]:
    """Assistant text contains a '?' but is not a question; user makes a
    statement. The harness must not mistake the assistant's '?' for a user
    question.
    """
    return _case(
        slug="adversarial_qmark_inside_assistant_text",
        category="adversarial",
        transcript_id="t_heldout_qmark_in_assistant",
        turns=[
            {"speaker": "assistant", "text": "Were you asking?"},
            {"speaker": "user", "text": "I was not."},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["non_question_marked_question"],
    )


def _heldout_adv_leakage_in_question_text() -> dict[str, Any]:
    """User question contains the leakage marker. The harness must not
    propagate the marker into the answer body.
    """
    return _case(
        slug="adversarial_leakage_in_question_text",
        category="adversarial",
        transcript_id="t_heldout_leak_in_question",
        turns=[
            {
                "speaker": "user",
                "text": "Why is the marker __hop_heldout_leak__ banned?",
            },
            {
                "speaker": "assistant",
                "text": "It is reserved for leakage detection. The harness does not echo it.",
            },
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "forbidden_substrings_in_answers": ["__hop_heldout_leak__"],
            },
        },
        failure_modes_targeted=["leakage_attempt"],
    )


CASE_BUILDERS = (
    _heldout_golden_pricing,
    _heldout_golden_meta_question,
    _heldout_golden_paired_topics,
    _heldout_golden_long_answer,
    _heldout_golden_dedup_paraphrase,
    _heldout_golden_three_topic,
    _heldout_golden_long_multi_sentence_answer,
    _heldout_golden_topic_switch_three_qa,
    _heldout_golden_orphan_assistant_then_qa,
    _heldout_adv_no_assistant_followup,
    _heldout_adv_only_statements,
    _heldout_adv_two_questions_no_answer,
    _heldout_adv_question_no_qmark,
    _heldout_adv_forbidden_marker,
    _heldout_adv_empty,
    _heldout_adv_qmark_inside_assistant_text,
    _heldout_adv_leakage_in_question_text,
)


def main() -> int:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = [builder() for builder in CASE_BUILDERS]

    seen: dict[str, str] = {}
    for case in cases:
        eid = case["eval_case_id"]
        if eid in seen:
            raise SystemExit(f"duplicate_eval_case_id:{eid}")
        seen[eid] = case["artifact_id"]

    # Disjointness check vs search set: no shared transcript_ids.
    search_manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "hop" / "manifest.json").read_text(encoding="utf-8")
    )
    search_dir = Path(__file__).resolve().parents[1] / "hop"
    search_transcript_ids: set[str] = set()
    for entry in search_manifest["cases"]:
        case_payload = json.loads((search_dir / entry["path"]).read_text(encoding="utf-8"))
        search_transcript_ids.add(case_payload["input"]["transcript_id"])
    for case in cases:
        tid = case["input"]["transcript_id"]
        if tid in search_transcript_ids:
            raise SystemExit(
                f"heldout_overlaps_search_set:transcript_id={tid}"
            )

    if len(cases) < 5 or len(cases) > 50:
        raise SystemExit(f"heldout_set_size_out_of_bounds:{len(cases)}")

    # Drop any stale on-disk cases that the current builder set no longer
    # produces, so the manifest stays in sync byte-for-byte.
    expected_paths = {CASES_DIR / f"{case['eval_case_id']}.json" for case in cases}
    for stale in CASES_DIR.glob("hop_case_heldout_*.json"):
        if stale not in expected_paths:
            stale.unlink()

    for case in cases:
        path = CASES_DIR / f"{case['eval_case_id']}.json"
        path.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "eval_set_id": EVAL_SET_ID,
        "eval_set_version": EVAL_SET_VERSION,
        "case_count": len(cases),
        "cases": [
            {
                "eval_case_id": case["eval_case_id"],
                "category": case["category"],
                "artifact_id": case["artifact_id"],
                "content_hash": case["content_hash"],
                "path": f"cases/{case['eval_case_id']}.json",
            }
            for case in cases
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(cases)} held-out cases to {CASES_DIR}")
    print(f"wrote manifest to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
