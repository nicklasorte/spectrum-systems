"""Admission tests — chained validator + safety_checks gate (F-01)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.admission import admit_candidate
from spectrum_systems.modules.hop.artifacts import finalize_artifact
from tests.hop.conftest import make_baseline_candidate


def test_admission_admits_baseline(eval_cases) -> None:
    candidate = make_baseline_candidate()
    ok, failures = admit_candidate(candidate, eval_cases)
    assert ok is True
    assert failures == []


def test_admission_rejects_schema_violation(eval_cases) -> None:
    bad = {"artifact_type": "hop_harness_candidate"}
    ok, failures = admit_candidate(bad, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "schema_violation" for f in failures)


def test_admission_blocks_unsafe_candidate(eval_cases) -> None:
    leaky = make_baseline_candidate(
        code_source=(
            "def run(t):\n"
            "    if 'hop_case_golden_one_qa' in t.get('transcript_id', ''):\n"
            "        return {}\n"
            "    return {}\n"
        )
    )
    ok, failures = admit_candidate(leaky, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "eval_dataset_leakage" for f in failures)


def test_admission_chains_validator_failure_short_circuits_safety(eval_cases) -> None:
    candidate = make_baseline_candidate()
    candidate["code_module"] = "spectrum_systems.modules.hop.does_not_exist"
    candidate.pop("content_hash", None)
    candidate.pop("artifact_id", None)
    finalize_artifact(candidate, id_prefix="hop_candidate_")

    ok, failures = admit_candidate(candidate, eval_cases)
    assert ok is False
    # Only the validator failure surfaces; safety scan is short-circuited.
    assert all(f["stage"] == "validation" for f in failures)
