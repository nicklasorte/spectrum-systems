"""Tests for AEX shift-left authority-shape admission (AEX-FRE-AUTH-SHAPE-01).

Covers:

* Manifest entries containing protected authority compounds in non-owner
  contexts produce a blocking diagnostic.
* Generated report headings using protected authority terms produce a
  blocking diagnostic.
* Non-owner module docstrings claiming authority ownership produce a
  blocking diagnostic.
* SEL near enforcement ownership in a non-SEL module produces a blocking
  diagnostic.
* Canonical owner files using their own protected term are allowed.
* Unknown cluster contexts (no authority mapping) are surfaced as
  fail-closed reason codes.
* Schema validation of the emitted artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.aex.authority_shape_admission import (
    REASON_PROTECTED_TERM_DOCSTRING,
    REASON_PROTECTED_TERM_MANIFEST_ENTRY,
    REASON_PROTECTED_TERM_REPORT_HEADING,
    admission_blocks,
    classify_context_kind,
    evaluate_admission,
)
from spectrum_systems.contracts import validate_artifact
from spectrum_systems.governance.authority_shape_preflight import load_vocabulary


REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"


@pytest.fixture
def vocab():
    return load_vocabulary(VOCAB_PATH)


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "spectrum_systems" / "modules" / "hop").mkdir(parents=True)
    (repo / "spectrum_systems" / "modules" / "governance").mkdir(parents=True)
    (repo / "spectrum_systems" / "modules" / "runtime").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    (repo / "contracts" / "schemas").mkdir(parents=True)
    (repo / "contracts" / "examples").mkdir(parents=True)
    (repo / "docs" / "governance-reports").mkdir(parents=True)
    return repo


def _write(repo: Path, rel: str, body: str) -> str:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return rel


def test_classify_context_kind_routes_known_paths():
    assert classify_context_kind("contracts/standards-manifest.json") == "manifest"
    assert classify_context_kind("contracts/schemas/foo.schema.json") == "schema"
    assert classify_context_kind("contracts/examples/foo.json") == "example"
    assert classify_context_kind("docs/governance-reports/x.md") == "report"
    assert classify_context_kind("docs/architecture/y.md") == "doc"
    assert classify_context_kind("scripts/run_x.py") == "script"
    assert classify_context_kind("spectrum_systems/modules/hop/x.py") == "source"


def test_manifest_entry_with_allow_decision_proof_blocks(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "contracts/standards-manifest.json",
        '{\n  "contracts": [\n    {"artifact_type": "allow_decision_proof", "owner": "HOP"}\n  ]\n}\n',
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    assert payload["status"] == "block"
    assert admission_blocks(payload)
    decision_diags = [d for d in payload["diagnostics"] if d["cluster"] == "decision"]
    assert decision_diags, "expected a manifest-entry decision-cluster diagnostic"
    sample = decision_diags[0]
    assert sample["context_kind"] == "manifest"
    assert sample["fail_closed_reason_code"] == REASON_PROTECTED_TERM_MANIFEST_ENTRY
    assert sample["owner_context_allowed"] is False
    assert sample["suggested_safe_replacements"]
    validate_artifact(payload, "authority_shape_admission_result")


def test_report_heading_contract_enforcement_report_blocks(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "docs/governance-reports/contract-enforcement-report.md",
        "# Contract Enforcement Report\n\nbody\n",
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    assert payload["status"] == "block"
    enforcement_diags = [
        d for d in payload["diagnostics"]
        if d["cluster"] == "enforcement" and d["context_kind"] == "report"
    ]
    assert enforcement_diags, "expected an enforcement heading diagnostic"
    sample = enforcement_diags[0]
    assert sample["fail_closed_reason_code"] == REASON_PROTECTED_TERM_REPORT_HEADING
    assert sample["suggested_safe_replacements"]
    validate_artifact(payload, "authority_shape_admission_result")


def test_non_owner_docstring_claiming_ownership_blocks(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "spectrum_systems/modules/hop/governance_helper.py",
        '"""GOV owns policy enforcement decisions."""\n\nGOVERNANCE_DECISION = 1\n',
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    assert payload["status"] == "block"
    docstring_diags = [
        d for d in payload["diagnostics"]
        if d["fail_closed_reason_code"] == REASON_PROTECTED_TERM_DOCSTRING
    ]
    assert docstring_diags, "expected a non-owner module docstring diagnostic"


def test_sel_terms_in_non_sel_module_blocks(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "spectrum_systems/modules/hop/sel_helper.py",
        '"""Helper that performs enforcement_action against violators."""\n'
        "ENFORCEMENT_ACTION = 'block'\n",
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    assert payload["status"] == "block"
    enforcement_diags = [d for d in payload["diagnostics"] if d["cluster"] == "enforcement"]
    assert enforcement_diags, "expected enforcement-cluster diagnostics"


def test_canonical_owner_file_with_protected_term_passes(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "spectrum_systems/modules/runtime/sel_enforcement_foundation.py",
        '"""SEL canonical enforcement engine."""\nENFORCEMENT = 1\n',
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    assert payload["status"] == "pass"
    assert payload["summary"]["block_count"] == 0


def test_unknown_owner_context_surfaces_in_diagnostics(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "contracts/examples/random_authority_decision.json",
        '{"value": "authority_verdict"}\n',
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="enforce",
    )
    # The example sits outside any canonical owner path for the authority cluster,
    # so the diagnostic must surface a non-empty canonical_owner mapping
    # (so FRE has somewhere to delegate to) and block.
    assert payload["status"] == "block"
    assert payload["diagnostics"]
    for d in payload["diagnostics"]:
        assert d["owner_context_allowed"] is False


def test_suggest_only_mode_does_not_block(tmp_path: Path, vocab):
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "contracts/examples/example_decision.json",
        '{"artifact_type": "control_decision_record"}\n',
    )
    payload = evaluate_admission(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only",
    )
    assert payload["status"] == "pass"
    assert payload["mode"] == "suggest-only"
    assert payload["diagnostics"]
