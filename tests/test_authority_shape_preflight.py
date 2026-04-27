"""Tests for the authority-shape preflight (AGS-001).

These tests prove:

* non-owner systems using authority-shaped names fail fast
* non-owner systems using advisory replacements pass
* canonical owner files may use canonical terms
* guard scripts and canonical-owner files are protected from auto-remediation
* safe renames update text while keeping guards intact
* unsafe renames are refused
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from spectrum_systems.governance.authority_shape_preflight import (
    AuthorityShapePreflightError,
    apply_safe_renames,
    evaluate_preflight,
    is_guard_path,
    is_owner_path,
    load_vocabulary,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"


@pytest.fixture
def vocab():
    return load_vocabulary(VOCAB_PATH)


def _write(repo_root: Path, rel: str, body: str) -> Path:
    target = repo_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "spectrum_systems").mkdir()
    (repo / "spectrum_systems" / "modules").mkdir()
    (repo / "spectrum_systems" / "modules" / "hop").mkdir()
    (repo / "scripts").mkdir()
    (repo / "spectrum_systems" / "modules" / "governance").mkdir()
    return repo


def test_non_owner_using_promotion_decision_fails(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/hop/promotion_emitter.py"
    _write(repo, rel, "PROMOTION_DECISION = {'value': 'allow'}\n")
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    promotion_violations = [v for v in result.violations if v.cluster == "promotion"]
    assert promotion_violations, "expected a promotion-cluster violation"
    sample = promotion_violations[0]
    assert sample.file == rel
    assert sample.line >= 1
    assert "promotion_signal" in sample.suggested_replacements


def test_non_owner_using_promotion_signal_passes(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/hop/promotion_emitter.py"
    _write(repo, rel, "PROMOTION_SIGNAL = {'value': 'observation_only'}\n")
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass"
    assert result.violations == []


def test_non_owner_using_rollback_record_fails(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/hop/rollback_observer.py"
    _write(repo, rel, "rollback_record = {'steps': []}\n")
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    rollback_violations = [v for v in result.violations if v.cluster == "rollback"]
    assert rollback_violations, "expected a rollback-cluster violation"
    assert "rollback_signal" in rollback_violations[0].suggested_replacements


def test_non_owner_using_rollback_signal_passes(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/hop/rollback_observer.py"
    _write(repo, rel, "rollback_signal = {'steps': []}\n")
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass"


def test_non_owner_plan_doc_using_enforce_term_fails(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "docs/review-actions/PLAN-EXAMPLE.md"
    _write(
        repo,
        rel,
        "# PLAN\n\n1. Enforce fail-closed runtime behavior for all modules.\n",
    )
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    enforcement_violations = [v for v in result.violations if v.cluster == "enforcement"]
    assert enforcement_violations, "expected an enforcement-cluster violation"
    assert "enforcement_signal" in enforcement_violations[0].suggested_replacements


def test_canonical_owner_may_use_canonical_term(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/governance/done_certification.py"
    _write(
        repo,
        rel,
        "CERTIFICATION = {'certification_status': 'certified'}\n",
    )
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    cert_violations = [v for v in result.violations if v.cluster == "certification"]
    assert cert_violations == [], "canonical owner must be allowed to use canonical term"


def test_violation_payload_carries_required_fields(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/hop/cert_observer.py"
    _write(repo, rel, "x = 'certification_status'  # leak\n")
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    payload = result.to_dict()
    assert payload["status"] == "fail"
    leak = next(v for v in payload["violations"] if v["cluster"] == "certification")
    for field in (
        "file",
        "line",
        "symbol",
        "cluster",
        "canonical_owners",
        "suggested_replacements",
        "rationale",
    ):
        assert field in leak, f"missing {field} in violation payload"


def test_apply_safe_renames_updates_text_and_preserves_guards(
    tmp_path: Path, vocab
) -> None:
    repo = _seed_repo(tmp_path)
    target = "spectrum_systems/modules/hop/promotion_emitter.py"
    guard = "scripts/run_authority_leak_guard.py"
    _write(
        repo,
        target,
        "promotion_decision = 'pending'\nharness_rollback_record = []\n",
    )
    _write(
        repo,
        guard,
        "# guard script — must not be mutated\npromotion_decision = 'guard-internal'\n",
    )

    result = evaluate_preflight(
        repo_root=repo,
        changed_files=[target, guard],
        vocab=vocab,
        mode="apply-safe-renames",
    )

    rewritten = (repo / target).read_text(encoding="utf-8")
    assert "promotion_signal" in rewritten
    assert "harness_rollback_signal" in rewritten
    assert "promotion_decision" not in rewritten
    assert "harness_rollback_record" not in rewritten

    guard_text = (repo / guard).read_text(encoding="utf-8")
    assert guard_text.startswith("# guard script — must not be mutated\n")
    assert "promotion_decision" in guard_text, "guard scripts must remain untouched"

    rename_files = {r.file for r in result.applied_renames}
    assert target in rename_files
    assert guard not in rename_files

    refused = {entry["file"]: entry["reason"] for entry in result.refused_renames}
    assert refused.get(guard) == "guard_path"


def test_canonical_owner_path_refuses_rename(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/governance/done_certification.py"
    _write(repo, rel, "certification_record = 'owner-internal'\n")
    rename, reason = apply_safe_renames(repo_root=repo, rel_path=rel, vocab=vocab)
    assert rename is None
    assert reason == "canonical_owner_path"
    assert (
        (repo / rel).read_text(encoding="utf-8")
        == "certification_record = 'owner-internal'\n"
    )


def test_safe_rename_updates_imports_and_docs(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    py_rel = "spectrum_systems/modules/hop/promotion_emitter.py"
    _write(
        repo,
        py_rel,
        "from spectrum_systems.modules.hop.promotion_decision import emit\n"
        "schema_ref = 'harness_promotion_decision'\n"
        "artifact_type = 'promotion_decision'\n",
    )
    json_rel = "contracts/examples/harness_promotion_input.json"
    (repo / "contracts" / "examples").mkdir(parents=True, exist_ok=True)
    (repo / json_rel).write_text(
        json.dumps({"artifact_type": "harness_promotion_decision", "value": 1}) + "\n",
        encoding="utf-8",
    )
    md_rel = "docs/governance/promotion_notes.md"
    (repo / "docs" / "governance").mkdir(parents=True, exist_ok=True)
    (repo / md_rel).write_text("# notes\nUses harness_promotion_decision in HOP.\n", encoding="utf-8")

    result = evaluate_preflight(
        repo_root=repo,
        changed_files=[py_rel, json_rel, md_rel],
        vocab=vocab,
        mode="apply-safe-renames",
    )

    assert "harness_promotion_signal" in (repo / py_rel).read_text(encoding="utf-8")
    assert "harness_promotion_signal" in (repo / json_rel).read_text(encoding="utf-8")
    assert "harness_promotion_signal" in (repo / md_rel).read_text(encoding="utf-8")
    rename_files = {r.file for r in result.applied_renames}
    assert {py_rel, json_rel, md_rel}.issubset(rename_files)


def test_guard_paths_are_skipped_for_violations(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/governance/system_registry_guard.py"
    _write(
        repo,
        rel,
        "# guard logic\nallowed_patterns = ['promotion', 'rollback', 'enforcement']\n",
    )
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert all(v.file != rel for v in result.violations), (
        "guard scripts must be exempt from preflight violation reporting "
        "since they intentionally enumerate authority terms"
    )


def test_unsafe_rename_refused_for_canonical_owner_artifact(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/governance/done_certification.py"
    _write(repo, rel, "certification_record = {'status': 'pass'}\n")
    rename, reason = apply_safe_renames(repo_root=repo, rel_path=rel, vocab=vocab)
    assert rename is None
    assert reason == "canonical_owner_path"


def test_invalid_mode_raises(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    with pytest.raises(AuthorityShapePreflightError):
        evaluate_preflight(repo_root=repo, changed_files=[], vocab=vocab, mode="advisory")


def test_load_vocabulary_validates_structure(tmp_path: Path) -> None:
    bad = tmp_path / "vocab.json"
    bad.write_text(json.dumps({"clusters": {}}), encoding="utf-8")
    with pytest.raises(AuthorityShapePreflightError):
        load_vocabulary(bad)


def test_real_repo_vocabulary_loads_and_lists_required_clusters() -> None:
    vocab = load_vocabulary(VOCAB_PATH)
    cluster_names = {c.name for c in vocab.clusters}
    required = {
        "decision",
        "promotion",
        "rollback",
        "certification",
        "control",
        "enforcement",
        "approval",
        "release",
        "authority",
        "quarantine",
        "final",
    }
    assert required.issubset(cluster_names)


def test_is_owner_path_and_is_guard_path(vocab) -> None:
    cert_cluster = next(c for c in vocab.clusters if c.name == "certification")
    assert is_owner_path(
        "spectrum_systems/modules/governance/done_certification.py", cert_cluster
    )
    assert not is_owner_path("spectrum_systems/modules/hop/foo.py", cert_cluster)
    assert is_guard_path("scripts/run_authority_leak_guard.py", vocab)
    assert is_guard_path(
        "spectrum_systems/modules/governance/system_registry_guard.py", vocab
    )
    assert not is_guard_path("spectrum_systems/modules/hop/foo.py", vocab)


def test_excluded_paths_are_skipped(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "tests/test_promotion_decision_examples.py"
    _write(repo, rel, "promotion_decision = {'allow': True}\n")
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass"
    assert rel in result.skipped_files


def test_apply_safe_renames_no_pair_match_returns_reason(tmp_path: Path, vocab) -> None:
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/hop/clean.py"
    _write(repo, rel, "value = 1\n")
    rename, reason = apply_safe_renames(repo_root=repo, rel_path=rel, vocab=vocab)
    assert rename is None
    assert reason == "no_safe_pair_match"
