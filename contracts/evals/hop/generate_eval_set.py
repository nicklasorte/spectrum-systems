#!/usr/bin/env python3
"""Deterministic generator for the HOP transcript -> FAQ eval set.

Run::

    python contracts/evals/hop/generate_eval_set.py

The script is idempotent: running it multiple times produces bit-identical
case files and manifest. Each case payload is finalized via the HOP artifacts
module so its ``content_hash`` and ``artifact_id`` are stable.
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

EVAL_SET_ID = "hop_transcript_to_faq_v1"
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
    eval_case_id = f"hop_case_{slug}"
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


def _golden_one_qa() -> dict[str, Any]:
    return _case(
        slug="golden_one_qa",
        category="golden",
        transcript_id="t_one_qa",
        turns=[
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["What is HOP?"],
                "expected_answer_substrings_per_question": [
                    {
                        "question_substring": "What is HOP?",
                        "answer_substring": "Harness Optimization Pipeline",
                    }
                ],
            },
        },
        failure_modes_targeted=["single_turn"],
    )


def _golden_two_qa() -> dict[str, Any]:
    return _case(
        slug="golden_two_qa",
        category="golden",
        transcript_id="t_two_qa",
        turns=[
            {"speaker": "user", "text": "What is the eval set?"},
            {"speaker": "assistant", "text": "It is a versioned set of cases."},
            {"speaker": "user", "text": "Why versioned?"},
            {"speaker": "assistant", "text": "To enable replay and detect drift."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 2,
                "max_qa_pairs": 2,
                "expected_questions_substrings": ["eval set", "Why versioned"],
            },
        },
        failure_modes_targeted=[],
    )


def _golden_three_qa_with_chatter() -> dict[str, Any]:
    return _case(
        slug="golden_three_qa_with_chatter",
        category="golden",
        transcript_id="t_chatter",
        turns=[
            {"speaker": "assistant", "text": "Hello, ready when you are."},
            {"speaker": "user", "text": "How do I store a candidate?"},
            {"speaker": "assistant", "text": "Use ExperienceStore.write_artifact."},
            {"speaker": "user", "text": "What does the validator do?"},
            {"speaker": "assistant", "text": "It rejects malformed candidates before eval."},
            {"speaker": "user", "text": "Where do failures go?"},
            {"speaker": "assistant", "text": "They are emitted as failure hypotheses."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 3,
                "max_qa_pairs": 3,
                "expected_questions_substrings": [
                    "store a candidate",
                    "validator",
                    "failures go",
                ],
            },
        },
        failure_modes_targeted=["interleaved_speakers"],
    )


def _golden_q_at_end() -> dict[str, Any]:
    return _case(
        slug="golden_q_at_end",
        category="golden",
        transcript_id="t_q_at_end",
        turns=[
            {"speaker": "assistant", "text": "Initial framing for the discussion."},
            {"speaker": "user", "text": "Anything else to know?"},
            {"speaker": "assistant", "text": "All artifacts are content-hashed."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["Anything else"],
                "expected_answer_substrings_per_question": [
                    {
                        "question_substring": "Anything else",
                        "answer_substring": "content-hashed",
                    }
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _golden_yes_no() -> dict[str, Any]:
    return _case(
        slug="golden_yes_no",
        category="golden",
        transcript_id="t_yes_no",
        turns=[
            {"speaker": "user", "text": "Is HOP append-only?"},
            {"speaker": "assistant", "text": "Yes, the experience store is append-only."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["append-only"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "append-only", "answer_substring": "Yes"}
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _golden_numerical() -> dict[str, Any]:
    return _case(
        slug="golden_numerical_answer",
        category="golden",
        transcript_id="t_num",
        turns=[
            {"speaker": "user", "text": "How many objectives does the frontier track?"},
            {"speaker": "assistant", "text": "The frontier tracks 5 objectives."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["objectives"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "objectives", "answer_substring": "5"}
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _golden_multi_sentence_answer() -> dict[str, Any]:
    return _case(
        slug="golden_multi_sentence_answer",
        category="golden",
        transcript_id="t_multi_sentence",
        turns=[
            {"speaker": "user", "text": "Why is the store append-only?"},
            {
                "speaker": "assistant",
                "text": (
                    "Append-only writes preserve full lineage. "
                    "They also make replay deterministic."
                ),
            },
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["append-only"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "append-only", "answer_substring": "lineage"}
                ],
            },
        },
        failure_modes_targeted=["long_answer_truncation"],
    )


def _golden_dedup_duplicate_questions() -> dict[str, Any]:
    return _case(
        slug="golden_dedup_duplicate_questions",
        category="golden",
        transcript_id="t_dedup",
        turns=[
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {"min_qa_pairs": 1, "max_qa_pairs": 1},
        },
        failure_modes_targeted=["duplicate_questions"],
    )


def _golden_four_qa_long() -> dict[str, Any]:
    # Owner names (PQX/CDE/SEL/TLC) refer to canonical owners — these are
    # references, not authority claims. Verbs were rephrased in HOP-005 to
    # use authority-neutral synonyms so the eval transcript content stays
    # advisory-only on the harness side.
    return _case(
        slug="golden_four_qa_long",
        category="golden",
        transcript_id="t_four_qa_long",
        turns=[
            {"speaker": "user", "text": "What does PQX run?"},
            {"speaker": "assistant", "text": "PQX runs bounded slices and bundles."},
            {"speaker": "user", "text": "What does CDE choose?"},
            {"speaker": "assistant", "text": "CDE chooses closure and release readiness."},
            {"speaker": "user", "text": "What does SEL guarantee?"},
            {"speaker": "assistant", "text": "SEL guarantees fail-closed actions."},
            {"speaker": "user", "text": "What does TLC orchestrate?"},
            {"speaker": "assistant", "text": "TLC orchestrates subsystem routing."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {"min_qa_pairs": 4, "max_qa_pairs": 4},
        },
        failure_modes_targeted=[],
    )


def _golden_capital_question_mark() -> dict[str, Any]:
    return _case(
        slug="golden_capital_question_mark",
        category="golden",
        transcript_id="t_capital_q",
        turns=[
            {"speaker": "user", "text": "Where does the frontier live?"},
            {"speaker": "assistant", "text": "The frontier is computed from harness scores."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["frontier"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "frontier", "answer_substring": "scores"}
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _golden_short_answer() -> dict[str, Any]:
    return _case(
        slug="golden_short_answer",
        category="golden",
        transcript_id="t_short",
        turns=[
            {"speaker": "user", "text": "Is the store fail-closed?"},
            {"speaker": "assistant", "text": "Yes."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {"min_qa_pairs": 1, "max_qa_pairs": 1},
        },
        failure_modes_targeted=[],
    )


def _golden_two_topics() -> dict[str, Any]:
    return _case(
        slug="golden_two_topics",
        category="golden",
        transcript_id="t_two_topics",
        turns=[
            {"speaker": "user", "text": "What is the schema_version field?"},
            {"speaker": "assistant", "text": "It is the contract version semver."},
            {"speaker": "user", "text": "What is the schema_ref field?"},
            {"speaker": "assistant", "text": "It is the relative schema path."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 2,
                "max_qa_pairs": 2,
                "expected_questions_substrings": [
                    "schema_version",
                    "schema_ref",
                ],
            },
        },
        failure_modes_targeted=[],
    )


def _golden_question_with_extra_punct() -> dict[str, Any]:
    return _case(
        slug="golden_question_with_extra_punct",
        category="golden",
        transcript_id="t_extra_punct",
        turns=[
            {"speaker": "user", "text": "What is replay-compatible?"},
            {"speaker": "assistant", "text": "It means runs can be replayed deterministically."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {"min_qa_pairs": 1, "max_qa_pairs": 1},
        },
        failure_modes_targeted=[],
    )


def _adv_empty_transcript() -> dict[str, Any]:
    return _case(
        slug="adversarial_empty_transcript",
        category="adversarial",
        transcript_id="t_empty",
        turns=[],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["empty_transcript"],
    )


def _adv_no_questions() -> dict[str, Any]:
    return _case(
        slug="adversarial_no_questions",
        category="adversarial",
        transcript_id="t_no_q",
        turns=[
            {"speaker": "user", "text": "I think HOP is interesting."},
            {"speaker": "assistant", "text": "Glad to hear that."},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["no_questions"],
    )


def _adv_question_no_following_assistant() -> dict[str, Any]:
    return _case(
        slug="adversarial_question_no_followup",
        category="adversarial",
        transcript_id="t_no_followup",
        turns=[
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "user", "text": "Hello?"},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["ambiguous_attribution", "no_questions"],
    )


def _adv_two_user_questions_one_answer() -> dict[str, Any]:
    return _case(
        slug="adversarial_two_q_one_a",
        category="adversarial",
        transcript_id="t_two_q_one_a",
        turns=[
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "user", "text": "Why does it exist?"},
            {"speaker": "assistant", "text": "HOP optimizes harnesses with full lineage."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {"min_qa_pairs": 2, "max_qa_pairs": 2},
        },
        failure_modes_targeted=["ambiguous_attribution"],
    )


def _adv_non_question_marked_question() -> dict[str, Any]:
    return _case(
        slug="adversarial_non_question_period",
        category="adversarial",
        transcript_id="t_period",
        turns=[
            {"speaker": "user", "text": "Tell me about HOP."},
            {"speaker": "assistant", "text": "HOP is a governed optimization pipeline."},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["non_question_marked_question"],
    )


def _adv_assistant_then_user_question() -> dict[str, Any]:
    return _case(
        slug="adversarial_assistant_then_user_question",
        category="adversarial",
        transcript_id="t_a_then_u",
        turns=[
            {"speaker": "assistant", "text": "Welcome."},
            {"speaker": "assistant", "text": "Anything to discuss?"},
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["What is HOP"],
            },
        },
        failure_modes_targeted=["interleaved_speakers"],
    )


def _adv_question_with_leading_whitespace() -> dict[str, Any]:
    return _case(
        slug="adversarial_question_leading_whitespace",
        category="adversarial",
        transcript_id="t_leading_ws",
        turns=[
            {"speaker": "user", "text": "    What is HOP?    "},
            {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {"min_qa_pairs": 1, "max_qa_pairs": 1},
        },
        failure_modes_targeted=["non_question_marked_question"],
    )


def _adv_long_answer() -> dict[str, Any]:
    long_answer = (
        "HOP stores candidate harness code, eval scores, and execution traces. "
        "It indexes by candidate_id, trace_id, score, and timestamp. "
        "It is append-only, replay-compatible, and rejects malformed artifacts."
    )
    return _case(
        slug="adversarial_long_answer",
        category="adversarial",
        transcript_id="t_adversarial_long_answer",
        turns=[
            {"speaker": "user", "text": "What does the experience store do?"},
            {"speaker": "assistant", "text": long_answer},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["experience store"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "experience store", "answer_substring": "append-only"}
                ],
            },
        },
        failure_modes_targeted=["long_answer_truncation"],
    )


def _adv_forbidden_substring() -> dict[str, Any]:
    return _case(
        slug="adversarial_forbidden_substring",
        category="adversarial",
        transcript_id="t_forbidden",
        turns=[
            {"speaker": "user", "text": "What is HOP?"},
            {"speaker": "assistant", "text": "HOP is the Harness Optimization Pipeline."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "forbidden_substrings_in_answers": ["lorem ipsum"],
            },
        },
        failure_modes_targeted=["hardcoded_answer_attempt"],
    )


def _adv_only_assistant_turns() -> dict[str, Any]:
    return _case(
        slug="adversarial_only_assistant",
        category="adversarial",
        transcript_id="t_only_assistant",
        turns=[
            {"speaker": "assistant", "text": "I will narrate HOP."},
            {"speaker": "assistant", "text": "It optimizes harnesses."},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["no_questions"],
    )


def _adv_user_only_question_then_user() -> dict[str, Any]:
    return _case(
        slug="adversarial_user_only_questions",
        category="adversarial",
        transcript_id="t_only_user",
        turns=[
            {"speaker": "user", "text": "Anybody home?"},
            {"speaker": "user", "text": "Hello?"},
        ],
        pass_criteria={
            "judge": "rejection_expected",
            "rules": {"expect_rejection": True},
        },
        failure_modes_targeted=["ambiguous_attribution"],
    )


def _failure_placeholder_leakage() -> dict[str, Any]:
    return _case(
        slug="failure_derived_leakage_placeholder",
        category="failure_derived_placeholder",
        transcript_id="t_leakage_placeholder",
        turns=[
            {"speaker": "user", "text": "Does HOP detect leakage?"},
            {"speaker": "assistant", "text": "Yes. The safety scan detects eval-id leakage."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "forbidden_substrings_in_answers": ["__hop_leak_marker__"],
            },
        },
        failure_modes_targeted=["leakage_attempt"],
    )


def _failure_placeholder_schema_weakening() -> dict[str, Any]:
    return _case(
        slug="failure_derived_schema_weakening_placeholder",
        category="failure_derived_placeholder",
        transcript_id="t_weakening_placeholder",
        turns=[
            {"speaker": "user", "text": "Can a candidate weaken HOP schemas?"},
            {"speaker": "assistant", "text": "No. The safety scan rejects schema weakening."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "forbidden_substrings_in_answers": ["additionalProperties"],
            },
        },
        failure_modes_targeted=["schema_weakening_attempt"],
    )


def _failure_placeholder_hardcoded() -> dict[str, Any]:
    return _case(
        slug="failure_derived_hardcoded_answer_placeholder",
        category="failure_derived_placeholder",
        transcript_id="t_hardcoded_placeholder",
        turns=[
            {"speaker": "user", "text": "Can a candidate hardcode answers?"},
            {"speaker": "assistant", "text": "No. The safety scan rejects hardcoded answers."},
        ],
        pass_criteria={
            "judge": "structural",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "forbidden_substrings_in_answers": ["__hop_hardcoded_marker__"],
            },
        },
        failure_modes_targeted=["hardcoded_answer_attempt"],
    )


CASE_BUILDERS = (
    _golden_one_qa,
    _golden_two_qa,
    _golden_three_qa_with_chatter,
    _golden_q_at_end,
    _golden_yes_no,
    _golden_numerical,
    _golden_multi_sentence_answer,
    _golden_dedup_duplicate_questions,
    _golden_four_qa_long,
    _golden_capital_question_mark,
    _golden_short_answer,
    _golden_two_topics,
    _golden_question_with_extra_punct,
    _adv_empty_transcript,
    _adv_no_questions,
    _adv_question_no_following_assistant,
    _adv_two_user_questions_one_answer,
    _adv_non_question_marked_question,
    _adv_assistant_then_user_question,
    _adv_question_with_leading_whitespace,
    _adv_long_answer,
    _adv_forbidden_substring,
    _adv_only_assistant_turns,
    _adv_user_only_question_then_user,
    _failure_placeholder_leakage,
    _failure_placeholder_schema_weakening,
    _failure_placeholder_hardcoded,
)


def main() -> int:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = [builder() for builder in CASE_BUILDERS]

    # Require uniqueness on eval_case_id.
    seen: dict[str, str] = {}
    for case in cases:
        eid = case["eval_case_id"]
        if eid in seen:
            raise SystemExit(f"duplicate_eval_case_id:{eid}")
        seen[eid] = case["artifact_id"]

    if len(cases) < 20 or len(cases) > 50:
        raise SystemExit(f"eval_set_size_out_of_bounds:{len(cases)}")

    for case in cases:
        category = case["category"]
        targeted = case.get("failure_modes_targeted", []) or []
        if category in {"adversarial", "failure_derived_placeholder"} and not targeted:
            raise SystemExit(
                f"eval_case_missing_targeted_mode:{case['eval_case_id']}:{category}"
            )

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
    print(f"wrote {len(cases)} cases to {CASES_DIR}")
    print(f"wrote manifest to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
