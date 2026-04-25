"""Safety check tests — leakage, hardcoded answers, schema weakening, eval bypass."""

from __future__ import annotations

from spectrum_systems.modules.hop.artifacts import finalize_artifact
from spectrum_systems.modules.hop.safety_checks import scan_candidate
from tests.hop.conftest import make_baseline_candidate


def _candidate_with_source(code: str) -> dict:
    candidate = make_baseline_candidate(code_source=code)
    return candidate


def test_clean_baseline_passes(eval_cases) -> None:
    candidate = make_baseline_candidate()
    ok, failures = scan_candidate(candidate, eval_cases)
    assert ok is True
    assert failures == []


def test_eval_dataset_leakage_is_detected(eval_cases) -> None:
    leaky = "def run(t):\n    if 'hop_case_golden_one_qa' in t:\n        return {}\n"
    candidate = _candidate_with_source(leaky)
    ok, failures = scan_candidate(candidate, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "eval_dataset_leakage" for f in failures)


def test_hardcoded_answer_is_detected(eval_cases) -> None:
    hardcoded = (
        "def run(t):\n"
        "    return [{'q': 'X', 'a': 'Harness Optimization Pipeline'}]\n"
    )
    candidate = _candidate_with_source(hardcoded)
    ok, failures = scan_candidate(candidate, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "hardcoded_answer" for f in failures)


def test_schema_weakening_is_detected(eval_cases) -> None:
    weak = (
        "from spectrum_systems.modules.hop import schemas\n"
        "validate_hop_artifact = lambda *a, **kw: None\n"
    )
    candidate = _candidate_with_source(weak)
    ok, failures = scan_candidate(candidate, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "schema_weakening" for f in failures)


def test_eval_bypass_attempt_is_detected(eval_cases) -> None:
    bypass = (
        "from pathlib import Path\n"
        "def run(t):\n"
        "    Path(\"contracts/evals/hop\").iterdir()\n"
        "    return {}\n"
    )
    candidate = _candidate_with_source(bypass)
    ok, failures = scan_candidate(candidate, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "eval_bypass_attempt" for f in failures)


def test_forbidden_substring_in_code_is_flagged(eval_cases) -> None:
    bad = (
        "def run(t):\n"
        "    return [{'q': 'placeholder', 'a': '__hop_hardcoded_marker__'}]\n"
    )
    candidate = _candidate_with_source(bad)
    ok, failures = scan_candidate(candidate, eval_cases)
    assert ok is False
    assert any(f["failure_class"] == "hardcoded_answer" for f in failures)
