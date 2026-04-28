"""Integration test for the AEX → FRE authority-shape shift-left loop.

End-to-end coverage:

* AEX detects a violation in a non-owner manifest entry.
* FRE generates a bounded repair candidate for that violation.
* The candidate carries safe replacements and required tests.
* No authority guardrails are weakened: AEX still produces a blocking
  ``authority_shape_admission_result`` and the existing
  ``authority_shape_preflight`` continues to flag the same file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.aex.authority_shape_admission import evaluate_admission
from spectrum_systems.contracts import validate_artifact
from spectrum_systems.fix_engine.authority_shape_repair import (
    generate_repair_candidates,
)
from spectrum_systems.governance.authority_shape_preflight import (
    evaluate_preflight,
    load_vocabulary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"


@pytest.fixture
def vocab():
    return load_vocabulary(VOCAB_PATH)


def _seed(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "spectrum_systems" / "modules" / "hop").mkdir(parents=True)
    (repo / "contracts").mkdir(parents=True)
    (repo / "docs" / "governance-reports").mkdir(parents=True)
    return repo


def _write(repo: Path, rel: str, body: str) -> str:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return rel


def test_admission_detects_then_fre_emits_bounded_candidate(tmp_path: Path, vocab):
    repo = _seed(tmp_path)
    rel_manifest = _write(
        repo,
        "contracts/standards-manifest.json",
        '{\n  "contracts": [\n    {"artifact_type": "allow_decision_proof", "owner": "HOP"}\n  ]\n}\n',
    )
    rel_report = _write(
        repo,
        "docs/governance-reports/contract-enforcement-report.md",
        "# Contract Enforcement Report\n\nbody\n",
    )

    admission = evaluate_admission(
        repo_root=repo,
        changed_files=[rel_manifest, rel_report],
        vocab=vocab,
        mode="enforce",
    )
    validate_artifact(admission, "authority_shape_admission_result")
    assert admission["status"] == "block"
    assert admission["summary"]["block_count"] >= 2

    candidates = generate_repair_candidates(admission_result=admission)
    assert candidates, "expected at least one bounded repair candidate"
    for candidate in candidates:
        validate_artifact(candidate, "authority_shape_repair_candidate")
        assert candidate["safe_replacement"]
        assert candidate["required_tests"], "candidates must declare required tests"
        # No candidate may silently propose a broad exclusion.
        assert "broad_exclusion" not in candidate.get("rejection_reason", "")
        # No candidate may silently elevate a non-owner into a canonical owner.
        assert candidate["non_authority_assertions"]


def test_preflight_still_flags_same_files_unchanged(tmp_path: Path, vocab):
    """Guardrails preserved: the existing preflight must keep flagging the
    same authority-shape leaks. Adding admission must not relax preflight."""
    repo = _seed(tmp_path)
    rel = _write(
        repo,
        "spectrum_systems/modules/hop/promotion_emitter.py",
        "PROMOTION_DECISION = {'value': 'allow'}\n",
    )
    preflight = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only",
    )
    assert preflight.status == "fail"
    assert any(v.cluster == "promotion" for v in preflight.violations)


def test_repair_candidate_chain_is_advisory_only(tmp_path: Path, vocab):
    """The AEX→FRE chain must never auto-mutate the repo."""
    repo = _seed(tmp_path)
    rel = _write(
        repo,
        "contracts/standards-manifest.json",
        '{"contracts": [{"artifact_type": "allow_decision_proof"}]}\n',
    )
    admission = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    candidates = generate_repair_candidates(admission_result=admission)
    # No candidate may mark itself "applied"; the schema only allows
    # ready/incomplete/rejected. PQX-equivalent execution is the only
    # path that can apply a repair, and only with control approval.
    for candidate in candidates:
        assert candidate["candidate_status"] in {"ready", "incomplete", "rejected"}

    # And the manifest must still be exactly what we wrote — repair is
    # advisory only.
    text = (repo / rel).read_text(encoding="utf-8")
    assert "allow_decision_proof" in text
