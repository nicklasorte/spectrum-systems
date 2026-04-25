"""Tests for the held-out advisory eval set.

The held-out set is HOP-internal evidence only. It is consumed by the
release-readiness signal (advisory) and never owns release, promotion,
or rollback authority — those remain with REL/CDE.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from spectrum_systems.modules.hop.artifacts import compute_content_hash, finalize_artifact, make_trace
from spectrum_systems.modules.hop.evaluator import (
    evaluate_candidate,
    load_eval_set_from_manifest,
)
from spectrum_systems.modules.hop.sandbox import SandboxConfig, execute_candidate
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from tests.hop.conftest import HELDOUT_EVAL_DIR, EVAL_DIR, make_baseline_candidate


def test_heldout_manifest_loads():
    eval_set = load_eval_set_from_manifest(str(HELDOUT_EVAL_DIR / "manifest.json"))
    assert eval_set.eval_set_id == "hop_transcript_to_faq_heldout_v1"
    assert eval_set.eval_set_version == "1.0.0"
    assert eval_set.case_count >= 5


def test_heldout_disjoint_from_search_set():
    """Held-out cases must not share transcript_ids with the search set."""
    search_manifest = json.loads((EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    heldout_manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    search_tids: set[str] = set()
    for entry in search_manifest["cases"]:
        payload = json.loads((EVAL_DIR / entry["path"]).read_text(encoding="utf-8"))
        search_tids.add(payload["input"]["transcript_id"])
    for entry in heldout_manifest["cases"]:
        payload = json.loads(
            (HELDOUT_EVAL_DIR / entry["path"]).read_text(encoding="utf-8")
        )
        assert payload["input"]["transcript_id"] not in search_tids


def test_heldout_cases_are_schema_valid_and_hashed():
    heldout_manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    for entry in heldout_manifest["cases"]:
        payload = json.loads(
            (HELDOUT_EVAL_DIR / entry["path"]).read_text(encoding="utf-8")
        )
        validate_hop_artifact(payload, "hop_harness_eval_case")
        assert payload["content_hash"] == compute_content_hash(payload)
        assert payload["content_hash"] == entry["content_hash"]


def test_heldout_disjoint_from_search_eval_set_ids():
    search = load_eval_set_from_manifest(str(EVAL_DIR / "manifest.json"))
    heldout = load_eval_set_from_manifest(str(HELDOUT_EVAL_DIR / "manifest.json"))
    assert search.eval_set_id != heldout.eval_set_id


def test_baseline_passes_held_out_set(heldout_eval_set):
    candidate = make_baseline_candidate()
    bundle = evaluate_candidate(candidate_payload=candidate, eval_set=heldout_eval_set)
    assert bundle["score"]["score"] == 1.0
    assert bundle["score"]["pass_count"] == heldout_eval_set.case_count


def _heldout_case_payloads() -> list[dict]:
    manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    return [
        json.loads((HELDOUT_EVAL_DIR / entry["path"]).read_text(encoding="utf-8"))
        for entry in manifest["cases"]
    ]


def test_heldout_covers_required_failure_categories():
    """HOP-005 requires the held-out set to cover every listed category."""
    payloads = _heldout_case_payloads()
    case_ids = [p["eval_case_id"] for p in payloads]

    def _has(*needles: str) -> bool:
        return any(any(n in cid for n in needles) for cid in case_ids)

    # Each required category is satisfied by at least one case.
    assert _has("two_questions_no_answer"), "ambiguous_attribution case missing"
    assert _has("dedup_identical_qa"), "duplicate_questions case missing"
    assert _has("two_questions_no_answer", "no_followup"), "no-answer case missing"
    assert _has("long_answer", "long_multi_sentence_answer"), "long answer case missing"
    assert _has("meta_question"), "meta-question case missing"
    assert _has("only_statements"), "non-question statement case missing"
    assert _has("forbidden_marker", "leakage_in_question"), "leakage marker case missing"


def test_heldout_size_within_bounds():
    """Held-out set must stay within the generator's hard bounds."""
    payloads = _heldout_case_payloads()
    assert 5 <= len(payloads) <= 50


_AUTHORITY_TOKEN_RE = re.compile(
    r"\b(promotion_decision|rollback_record|control_decision|certification_record|"
    r"certification_status|promotion_ready|enforcement_action|"
    r"promotion gate|certification gate|control decision|"
    r"approved|certified|promoted|quarantine|rollback|promote|"
    r"allow|warn|block|freeze)\b",
    re.IGNORECASE,
)


def test_heldout_transcript_text_is_authority_safe():
    """No held-out transcript text may carry authority-shaped vocabulary.

    The held-out cases are advisory-only inputs; embedding control-plane
    tokens here would (a) leak vocabulary into HOP artifacts and (b)
    mislead future prompts that grep the held-out set for examples.
    """
    payloads = _heldout_case_payloads()
    leaks: list[str] = []
    for payload in payloads:
        for turn in payload["input"]["turns"]:
            text = turn.get("text", "")
            for match in _AUTHORITY_TOKEN_RE.finditer(text):
                leaks.append(
                    f"{payload['eval_case_id']}: '{match.group(1)}' in turn text "
                    f"({turn.get('speaker')})"
                )
    assert not leaks, "authority-shaped tokens leaked into held-out transcripts:\n" + "\n".join(leaks)


def _make_eval_reading_candidate() -> dict:
    """Build a malicious harness that tries to read the held-out cases."""
    code_source = '''
from pathlib import Path

def run(transcript, *, trace_id="hop_eval_reader"):
    # Try to read a held-out case file. The sandbox must deny this.
    target = Path("contracts/evals/hop_heldout/manifest.json").resolve()
    target.read_text(encoding="utf-8")
    return {"items": [], "transcript_id": transcript["transcript_id"]}
'''
    payload = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="hop_test_eval_reader"),
        "candidate_id": "eval_reader_v1",
        "harness_type": "transcript_to_faq",
        "code_module": "tests.hop.test_heldout_eval._eval_reader",
        "code_entrypoint": "run",
        "code_source": code_source,
        "declared_methods": ["run"],
        "parent_candidate_id": None,
        "tags": ["adversarial"],
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_candidate_")
    return payload


def test_heldout_cases_unreadable_from_sandbox_via_evaluator(heldout_eval_set):
    """The evaluator must run held-out candidates inside a sandbox that
    denies reads of the eval data — otherwise a candidate could memorise
    the held-out cases and trivially pass the readiness signal.

    The evaluator wraps each run with
    ``denied_read_path_prefixes=(repo_root/contracts/evals,)`` so any
    attempt to read a held-out case file surfaces as a sandbox_violation
    failure hypothesis instead of a passing score.
    """
    candidate = _make_eval_reading_candidate()
    bundle = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set
    )
    # Every case must register a failure. None should pass — the
    # candidate is trying to read held-out data.
    assert bundle["score"]["pass_count"] == 0
    failure_classes = {
        f["failure_class"] for f in bundle.get("failures", [])
    }
    assert "sandbox_violation" in failure_classes, (
        f"expected sandbox_violation, got {failure_classes}"
    )


def test_heldout_cases_unreadable_from_sandbox_directly():
    """Tighten the loop: the sandbox itself, with the evaluator's denied
    prefixes, must reject reads of the held-out manifest.
    """
    repo_root = Path(__file__).resolve().parents[2]
    candidate = _make_eval_reading_candidate()
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t_probe", "turns": []},
        config=SandboxConfig(
            denied_read_path_prefixes=(
                str(repo_root / "contracts" / "evals"),
            ),
        ),
    )
    assert not result.ok
    assert result.violation_type == "sandbox_violation"
    assert "read_denied_eval_data" in (result.detail or "")


def test_heldout_tampered_manifest_rejected(tmp_path: Path):
    """If the manifest content_hash is mutated, loading must fail closed."""
    manifest = json.loads(
        (HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    # Tamper with the first manifest entry's hash.
    manifest["cases"][0]["content_hash"] = "sha256:" + "0" * 64
    target_dir = tmp_path / "tampered"
    target_dir.mkdir()
    (target_dir / "cases").mkdir()
    for entry in manifest["cases"]:
        src = HELDOUT_EVAL_DIR / entry["path"]
        dst = target_dir / entry["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hop_evaluator_tampered_manifest"):
        load_eval_set_from_manifest(str(target_dir / "manifest.json"))
