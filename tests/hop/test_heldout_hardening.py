"""HOP-005 hardening tests for the held-out validation eval set.

These tests live alongside ``test_heldout_eval.py``. They prove that:

1. Held-out cases are not reachable by candidate harnesses inside the
   sandbox (eval-data leakage is fail-closed).
2. The held-out set carries the coverage classes HOP-005 requires
   (ambiguous attribution, duplicate questions, no-answer cases, long
   answer, meta-question, non-question statement, leakage marker).
3. The held-out set's transcript_ids and eval_set_id remain disjoint
   from the search set after every regeneration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.sandbox import (
    SandboxConfig,
    execute_candidate,
)
from tests.hop.conftest import EVAL_DIR, HELDOUT_EVAL_DIR, make_baseline_candidate


REPO_ROOT = Path(__file__).resolve().parents[2]


def _heldout_case_files() -> list[Path]:
    return sorted((HELDOUT_EVAL_DIR / "cases").glob("hop_case_heldout_*.json"))


def test_heldout_cases_are_unreadable_from_sandbox(tmp_path: Path) -> None:
    """A candidate that tries to open a held-out case file must fail closed.

    The denied_read_path_prefixes tuple is set to the entire eval root so
    the sandbox refuses any read under contracts/evals/. A non-fail-closed
    sandbox would let an adversarial candidate memorise the held-out
    answers and bypass the validation cohort.
    """
    target = _heldout_case_files()[0]
    code = (
        "def run(t):\n"
        f"    with open({str(target)!r}, 'r') as fh:\n"
        "        fh.read()\n"
        "    return {}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    candidate["code_module"] = "attacker_payload"
    candidate["code_entrypoint"] = "run"
    eval_root = REPO_ROOT / "contracts" / "evals"
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t", "turns": []},
        config=SandboxConfig(denied_read_path_prefixes=(str(eval_root),)),
    )
    assert result.ok is False
    assert result.violation_type == "sandbox_violation"
    assert "read_denied_eval_data" in (result.detail or "")


def test_heldout_cases_unreadable_via_pathlib(tmp_path: Path) -> None:
    """Same denial via pathlib.Path.read_text — no second-class read API."""
    target = _heldout_case_files()[0]
    code = (
        "import pathlib\n"
        "def run(t):\n"
        f"    pathlib.Path({str(target)!r}).read_text()\n"
        "    return {}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    candidate["code_module"] = "attacker_payload"
    candidate["code_entrypoint"] = "run"
    eval_root = REPO_ROOT / "contracts" / "evals"
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t", "turns": []},
        config=SandboxConfig(denied_read_path_prefixes=(str(eval_root),)),
    )
    # pathlib.Path.read_text routes through builtins.open, which is guarded.
    assert result.ok is False
    assert result.violation_type == "sandbox_violation"


def test_heldout_cases_unreadable_via_os_open() -> None:
    """os.open with read flags is denied under denied_read_path_prefixes."""
    target = _heldout_case_files()[0]
    code = (
        "import os\n"
        "def run(t):\n"
        f"    fd = os.open({str(target)!r}, os.O_RDONLY)\n"
        "    os.close(fd)\n"
        "    return {}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    candidate["code_module"] = "attacker_payload"
    candidate["code_entrypoint"] = "run"
    eval_root = REPO_ROOT / "contracts" / "evals"
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t", "turns": []},
        config=SandboxConfig(denied_read_path_prefixes=(str(eval_root),)),
    )
    assert result.ok is False
    assert result.violation_type == "sandbox_violation"


REQUIRED_COVERAGE = {
    "ambiguous_attribution": [
        "hop_case_heldout_adversarial_two_questions_no_answer",
        "hop_case_heldout_adversarial_ambiguous_attribution_chain",
    ],
    "duplicate_questions": [
        "hop_case_heldout_golden_dedup_identical_qa",
        "hop_case_heldout_golden_dedup_triple_paraphrase",
    ],
    "no_answer": [
        "hop_case_heldout_adversarial_no_followup",
        "hop_case_heldout_adversarial_two_questions_no_answer",
        "hop_case_heldout_adversarial_only_statements",
        "hop_case_heldout_adversarial_question_no_qmark",
        "hop_case_heldout_adversarial_empty_transcript",
    ],
    "long_answer": [
        "hop_case_heldout_golden_long_answer",
    ],
    "meta_question": [
        "hop_case_heldout_golden_meta_question",
    ],
    "non_question_statement": [
        "hop_case_heldout_adversarial_only_statements",
    ],
    "leakage_marker": [
        "hop_case_heldout_adversarial_forbidden_marker",
        "hop_case_heldout_adversarial_authority_marker_carrier",
    ],
}


def test_heldout_required_coverage_classes_present() -> None:
    """The held-out set must include every HOP-005 coverage class.

    Each required class lists at least one case id. If the case files are
    renamed or removed, this test fails before any preflight check runs,
    so the validation cohort cannot silently regress its coverage.
    """
    manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    case_ids = {entry["eval_case_id"] for entry in manifest["cases"]}
    missing: dict[str, list[str]] = {}
    for klass, expected_ids in REQUIRED_COVERAGE.items():
        absent = [cid for cid in expected_ids if cid not in case_ids]
        if absent:
            missing[klass] = absent
    assert not missing, f"missing held-out coverage: {missing}"


def test_heldout_set_strictly_larger_than_minimum() -> None:
    """The held-out set must carry at least 12 cases.

    HOP-005 raised the floor from 5 to 12 to ensure each coverage class
    has at least one case. Below 12, removing a single case could drop
    a required class below threshold without a coverage test failing.
    """
    manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["case_count"] >= 12


def test_heldout_disjoint_eval_set_id() -> None:
    """eval_set_id must remain different from the search set's."""
    search = json.loads(
        (EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    heldout = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    assert search["eval_set_id"] != heldout["eval_set_id"]


def test_heldout_transcript_ids_globally_unique_in_set() -> None:
    """No duplicate transcript_id within the held-out set itself."""
    seen: dict[str, str] = {}
    for path in _heldout_case_files():
        case = json.loads(path.read_text(encoding="utf-8"))
        tid = case["input"]["transcript_id"]
        if tid in seen:
            pytest.fail(
                f"duplicate transcript_id '{tid}' in {path.name} "
                f"and {seen[tid]}"
            )
        seen[tid] = path.name


def test_heldout_transcript_ids_disjoint_from_search() -> None:
    """No transcript_id in the held-out set may appear in the search set.

    This is a structural complement to test_heldout_disjoint_from_search_set
    in test_heldout_eval.py; it scans the case files directly so a
    manifest-only mutation cannot mask a leak.
    """
    search_ids: set[str] = set()
    for path in (EVAL_DIR / "cases").glob("hop_case_*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        search_ids.add(case["input"]["transcript_id"])
    for path in _heldout_case_files():
        case = json.loads(path.read_text(encoding="utf-8"))
        tid = case["input"]["transcript_id"]
        assert tid not in search_ids, (
            f"held-out transcript_id '{tid}' in {path.name} collides with search set"
        )
