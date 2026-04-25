#!/usr/bin/env python3
"""Deterministic generator for the HOP held-out certification eval set.

The held-out set is *separate* from the search eval set
(``contracts/evals/hop``). Promotion candidates must pass BOTH sets — the
held-out set is the certification gate that catches search-eval overfitting.

Cases here are intentionally distinct in transcript content, structure, and
phrasing from the search set. They share the same JSON schema and judges.

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
            {"speaker": "user", "text": "How much does the certification gate cost?"},
            {"speaker": "assistant", "text": "Certification is bundled with the eval."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["certification gate"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "certification gate", "answer_substring": "bundled"},
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
            {"speaker": "user", "text": "Who decides allow versus block?"},
            {"speaker": "assistant", "text": "Control plane decides allow versus block."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["allow versus block"],
                "expected_answer_substrings_per_question": [
                    {"question_substring": "allow versus block", "answer_substring": "Control plane"},
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
            {"speaker": "assistant", "text": "It is a disjoint eval cohort used at certification."},
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
        failure_modes_targeted=[],
    )


def _heldout_golden_dedup_paraphrase() -> dict[str, Any]:
    return _case(
        slug="golden_dedup_identical_qa",
        category="golden",
        transcript_id="t_heldout_dedup",
        turns=[
            {"speaker": "user", "text": "Is rollback reversible?"},
            {"speaker": "assistant", "text": "Rollback restores the prior promoted harness."},
            {"speaker": "user", "text": "Is rollback reversible?"},
            {"speaker": "assistant", "text": "Rollback restores the prior promoted harness."},
        ],
        pass_criteria={
            "judge": "expected_qa_pairs",
            "rules": {
                "min_qa_pairs": 1,
                "max_qa_pairs": 1,
                "expected_questions_substrings": ["rollback reversible"],
            },
        },
        failure_modes_targeted=[],
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


# --- adversarial cases (held-out) --------------------------------------------

def _heldout_adv_no_assistant_followup() -> dict[str, Any]:
    return _case(
        slug="adversarial_no_followup",
        category="adversarial",
        transcript_id="t_heldout_no_followup",
        turns=[
            {"speaker": "user", "text": "Where does the rollback artifact go?"},
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
            {"speaker": "user", "text": "Tell me about promotion gates."},
            {"speaker": "assistant", "text": "They require search and held-out passes."},
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


CASE_BUILDERS = (
    _heldout_golden_pricing,
    _heldout_golden_meta_question,
    _heldout_golden_paired_topics,
    _heldout_golden_long_answer,
    _heldout_golden_dedup_paraphrase,
    _heldout_golden_three_topic,
    _heldout_adv_no_assistant_followup,
    _heldout_adv_only_statements,
    _heldout_adv_two_questions_no_answer,
    _heldout_adv_question_no_qmark,
    _heldout_adv_forbidden_marker,
    _heldout_adv_empty,
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
