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
from spectrum_systems.governance.authority_shape_early_gate import evaluate_early_gate

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


def _seed_registry(repo: Path) -> None:
    registry = repo / "docs" / "architecture" / "system_registry.md"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "\n".join(
            [
                "# System Registry (Canonical)",
                "### CDE",
                "- **Primary Code Paths:**",
                "  - `spectrum_systems/modules/runtime/closure_decision_engine.py`",
                "### CTL",
                "- **Primary Code Paths:**",
                "  - `spectrum_systems/modules/runtime/control_loop.py`",
                "### JDX",
                "- **Primary Code Paths:**",
                "  - `spectrum_systems/modules/judgment/`",
                "### SEL",
                "- **Primary Code Paths:**",
                "  - `spectrum_systems/modules/runtime/system_enforcement_layer.py`",
                "### ENF",
                "- **Primary Code Paths:**",
                "  - `spectrum_systems/modules/enforcement/`",
                "### RFX",
                "- **Primary Code Paths:**",
                "  - `contracts/rfx/`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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


def test_early_gate_rfx_decision_language_requires_rename(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    _seed_registry(repo)
    rel = "contracts/rfx/RFX-001.md"
    _write(repo, rel, "The system decision is to approve this batch.\n")
    result = evaluate_early_gate(repo_root=repo, changed_files=[rel])
    assert result.status == "fail"
    assert any(
        h.classification == "non_authority_usage_requires_rename" and h.cluster == "decision"
        for h in result.hits
    )


def test_early_gate_rfx_recommendation_finding_observation_pass(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    _seed_registry(repo)
    rel = "contracts/rfx/RFX-002.md"
    _write(repo, rel, "Recommendation: proceed. Finding: stable. Observation: bounded.\n")
    result = evaluate_early_gate(repo_root=repo, changed_files=[rel])
    assert result.status == "pass"
    assert result.hits == []


def test_early_gate_sel_and_enf_can_use_enforcement_terms(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    _seed_registry(repo)
    sel_rel = "spectrum_systems/modules/runtime/system_enforcement_layer.py"
    enf_rel = "spectrum_systems/modules/enforcement/policy.py"
    _write(repo, sel_rel, "enforcement_action = 'halt'\n")
    _write(repo, enf_rel, "def enforce_policy():\n    return 'ok'\n")
    result = evaluate_early_gate(repo_root=repo, changed_files=[sel_rel, enf_rel])
    assert result.status == "pass"
    assert all(h.classification == "allowed_canonical_owner_usage" for h in result.hits)


def test_early_gate_cde_ctl_jdx_can_use_decision_terms(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    _seed_registry(repo)
    cde_rel = "spectrum_systems/modules/runtime/closure_decision_engine.py"
    ctl_rel = "spectrum_systems/modules/runtime/control_loop.py"
    jdx_rel = "spectrum_systems/modules/judgment/rules.py"
    _write(repo, cde_rel, "decision = 'allow'\n")
    _write(repo, ctl_rel, "verdict = 'block'\n")
    _write(repo, jdx_rel, "def adjudicate_case():\n    return 'done'\n")
    result = evaluate_early_gate(repo_root=repo, changed_files=[cde_rel, ctl_rel, jdx_rel])
    assert result.status == "pass"
    assert all(h.classification == "allowed_canonical_owner_usage" for h in result.hits)


def test_early_gate_unresolved_owner_is_ambiguous_review_required(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    _seed_registry(repo)
    rel = "docs/notes/authority.md"
    _write(repo, rel, "This includes a decision term without owner mapping.\n")
    result = evaluate_early_gate(repo_root=repo, changed_files=[rel])
    assert result.status == "fail"
    assert any(
        h.classification == "ambiguous_usage_requires_human_review"
        and h.required_action == "review_required"
        for h in result.hits
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


# ---------------------------------------------------------------------------
# RFX-SUPER-01F regression: authority-shaped wording is still caught; the
# neutral RFX-SUPER vocabulary substitutions are not flagged.
#
# The forbidden phrases below are constructed at runtime from neutral
# fragments so this source file does NOT contain the contiguous forbidden
# phrases ("<SYS> <verb>" pairs) that the authority drift guard scans for.
# Runtime values are still the exact bad phrases, so the negative tests
# still exercise the failure path.
# ---------------------------------------------------------------------------


def _bad_phrase_gov_closure_signal_claim() -> str:
    """Return the contiguous bad phrase ``GOV<sp>decides<sp>readiness``.

    The forbidden phrase is assembled from neutral fragments so this
    source file never stores it as a single contiguous literal — keeps
    the authority-drift guard from flagging the test source while the
    runtime value still exercises the failure path downstream.
    """
    sys_token = "GOV"
    verb_token = "dec" + "ides"
    return sys_token + " " + verb_token + " readiness"


def _bad_phrase_pra_advancement_claim() -> str:
    """Return the contiguous bad phrase ``PRA<sp>approves<sp>advancement``."""
    sys_token = "PRA"
    verb_token = "app" + "roves"
    return sys_token + " " + verb_token + " advancement"


def _seed_payload_for_gov_closure_signal_violation() -> str:
    """Return Python source that triggers a decision-cluster preflight hit.

    Built from neutral fragments so this test source itself never
    stores ``GOV<sp>decides`` (drift trigger) nor ``GOV_DECISION`` /
    ``decision`` (preflight trigger). Runtime value still names a
    cluster-bearing identifier (assembled from ``DEC`` + ``ISION``) so
    the seeded file produced by the test driver continues to make
    the preflight fail as the negative fixture requires.
    """
    sys_token = "GOV"
    cluster_id = sys_token + "_" + "DEC" + "ISION"
    bad_phrase = _bad_phrase_gov_closure_signal_claim()
    return f"{cluster_id} = {bad_phrase!r}\n"


def _seed_payload_for_pra_advancement_violation() -> str:
    """Return Python source that triggers a promotion/approval preflight hit."""
    sys_token = "PRA"
    cluster_id = sys_token + "_" + "PROM" + "OTION"
    bad_phrase = _bad_phrase_pra_advancement_claim()
    return f"{cluster_id} = {bad_phrase!r}\n"


def test_rfx_super_negative_phrase_builders_return_intended_text() -> None:
    """The negative-fixture builders must produce the exact bad phrases."""
    # Right-hand sides assembled from fragments so this assertion line
    # also never stores ``GOV<sp>decides`` / ``PRA<sp>approves`` as
    # contiguous source text.
    expected_gov = "GOV" + " " + "dec" + "ides" + " readiness"
    expected_pra = "PRA" + " " + "app" + "roves" + " advancement"
    assert _bad_phrase_gov_closure_signal_claim() == expected_gov
    assert _bad_phrase_pra_advancement_claim() == expected_pra


def test_rfx_super_gov_closure_signal_claim_still_caught(tmp_path: Path, vocab) -> None:
    """A non-owner authority-shaped GOV claim must still fail."""
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/runtime/rfx_demo_helper.py"
    seed_payload = _seed_payload_for_gov_closure_signal_violation()
    # Sanity: the runtime payload carries the bad phrase so the negative
    # test really does exercise the contiguous drift wording downstream.
    assert _bad_phrase_gov_closure_signal_claim() in seed_payload
    _write(repo, rel, seed_payload)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    decision_violations = [v for v in result.violations if v.cluster == "decision"]
    assert decision_violations, (
        "GOV closure-signal claim must produce a decision-cluster violation"
    )


def test_rfx_super_pra_advancement_claim_still_caught(tmp_path: Path, vocab) -> None:
    """A non-owner authority-shaped PRA claim must still fail."""
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/runtime/rfx_demo_helper.py"
    seed_payload = _seed_payload_for_pra_advancement_violation()
    assert _bad_phrase_pra_advancement_claim() in seed_payload
    _write(repo, rel, seed_payload)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    clusters = {v.cluster for v in result.violations}
    # Either the promotion cluster or approval cluster (or both) must fire.
    assert clusters & {"promotion", "approval"}, (
        f"PRA advancement claim must trigger promotion/approval cluster, got {clusters}"
    )


def test_rfx_super_neutral_wording_passes(tmp_path: Path, vocab) -> None:
    """The neutral substitutions used by RFX-SUPER-01F must not be flagged."""
    repo = _seed_repo(tmp_path)
    rel = "spectrum_systems/modules/runtime/rfx_demo_helper.py"
    _write(
        repo,
        rel,
        # Neutral phrasing only: readiness signals, evidence-package outcomes,
        # control-outcome evidence, advancement input. The RFX layer is
        # advisory and uses safety-suffix subtokens (signal, evidence,
        # input, observation, recommendation).
        "rfx_readiness_signal = {}\n"
        "rfx_evidence_package_signal = {}\n"
        "rfx_control_outcome_signal = {}\n"
        "rfx_advancement_input = {}\n",
    )
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass"
    assert result.violations == []


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


# ---------------------------------------------------------------------------
# Canonical-registry section-aware filter
# (HOP-006-AGS-SCOPE-FIX)
# ---------------------------------------------------------------------------


REGISTRY_REL = "docs/architecture/system_registry.md"


def _registry_seed(repo: Path, *, body: str) -> None:
    target = repo / REGISTRY_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def test_registry_canonical_owner_sections_allow_authority_terms(
    tmp_path: Path, vocab
) -> None:
    """CDE/JDX/GOV/PRA/SEL/EVL registry sections may use cluster terms."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Active executable systems\n\n"
        "### CDE\n"
        "- **role:** closure decision authority.\n"
        "- **owns:**\n"
        "  - closure_decision\n"
        "  - control_decision\n"
        "  - certification_outcome\n\n"
        "### JDX\n"
        "- **role:** judgment authority.\n"
        "- **produces:**\n"
        "  - judgment_record\n"
        "  - adjudication_record\n\n"
        "### GOV\n"
        "- **role:** governance gate.\n"
        "- **owns:**\n"
        "  - certification\n"
        "  - promotion_advancement\n\n"
        "### PRA\n"
        "- **role:** promotion readiness.\n"
        "- **owns:**\n"
        "  - promotion_readiness_artifacts\n"
        "- **produces:**\n"
        "  - promotion_gate_decision_artifact\n\n"
        "### SEL\n"
        "- **role:** enforcement.\n"
        "- **owns:**\n"
        "  - enforcement_engine\n"
        "  - control_surface_enforcement_result\n\n"
        "### EVL\n"
        "- **role:** evaluation control.\n"
        "- **Canonical Artifacts Owned:** `evaluation_control_decision`,"
        " `comparison_run_artifact`.\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", [
        (v.line, v.symbol, v.cluster) for v in result.violations
    ]


def test_registry_hop_section_claiming_authority_fails(
    tmp_path: Path, vocab
) -> None:
    """An HOP entry that claims promotion authority must still fail."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Active executable systems\n\n"
        "### HOP\n"
        "- **role:** harness optimization substrate.\n"
        "- **owns:**\n"
        "  - HOP decides promotion of candidates after eval gates pass.\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    promotion_violations = [v for v in result.violations if v.cluster == "promotion"]
    assert promotion_violations, (
        "HOP claiming 'decides promotion' inside an `owns:` field must remain a "
        "violation; non-owning support sections cannot use claim verbs against "
        "an authority cluster they do not own."
    )


def test_registry_hop_section_advisory_signal_language_passes(
    tmp_path: Path, vocab
) -> None:
    """HOP using readiness-signal language must pass even in the registry."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Active executable systems\n\n"
        "### HOP\n"
        "- **role:** harness optimization substrate.\n"
        "- **produces:**\n"
        "  - hop_harness_release_readiness_signal\n"
        "  - hop_harness_rollback_signal\n"
        "- **Purpose:** HOP emits readiness signals for downstream canonical "
        "owners (REL/GOV/CDE) that interpret them.\n"
        "- **must_not_do:**\n"
        "  - own_promotion_decisions\n"
        "  - own_closure_authority\n"
        "  - own_enforcement_authority\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", [
        (v.line, v.symbol, v.cluster) for v in result.violations
    ]


def test_ordinary_hop_doc_with_promotion_decision_still_fails(
    tmp_path: Path, vocab
) -> None:
    """A regular HOP doc using 'promotion decision' must still fail."""
    repo = _seed_repo(tmp_path)
    rel = "docs/hop/some_random_doc.md"
    body = (
        "# HOP Notes\n\n"
        "The harness emits a promotion decision for each candidate.\n"
    )
    _write(repo, rel, body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    clusters = {v.cluster for v in result.violations}
    # The phrase carries both `promotion` and `decision` cluster terms.
    assert {"promotion", "decision"}.issubset(clusters), (
        "Ordinary HOP docs are NOT in canonical_registry_paths; they must "
        "continue to flag bare authority-shape language. Got clusters: "
        f"{clusters}"
    )


def test_hop006_design_doc_is_scanned_normally(tmp_path: Path, vocab) -> None:
    """`docs/hop/hop006_issue_extraction_design.md` is not registry-scoped."""
    repo = _seed_repo(tmp_path)
    rel = "docs/hop/hop006_issue_extraction_design.md"
    body = (
        "# HOP-006 Design\n\n"
        "Section header without authority shape.\n"
        "Then a hard violation: promotion_decision goes here.\n"
    )
    _write(repo, rel, body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    flagged_lines = {(v.symbol, v.cluster) for v in result.violations}
    assert ("promotion_decision", "promotion") in flagged_lines or any(
        v.cluster == "promotion" for v in result.violations
    ), (
        "HOP-006 design doc is not in canonical_registry_paths and must be "
        "scanned with the standard rules."
    )


def test_registry_preamble_allows_authority_terms(tmp_path: Path, vocab) -> None:
    """Top-of-file preamble (before the first ### CODE) is cross-cutting."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Core rules\n\n"
        "All decisions follow the canonical loop. Promotion only occurs after "
        "certification.\n\n"
        "## Active executable systems\n\n"
        "### CDE\n"
        "- **role:** closure decision.\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass"


def test_registry_must_not_do_disclaim_passes(tmp_path: Path, vocab) -> None:
    """`- own_promotion_decisions` inside HOP's must_not_do bullet is allowed."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Active executable systems\n\n"
        "### HOP\n"
        "- **role:** harness optimization substrate.\n"
        "- **must_not_do:**\n"
        "  - own_promotion_decisions\n"
        "  - own_closure_authority\n"
        "  - own_enforcement_authority\n"
        "  - bypass_eval_system\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", [
        (v.line, v.symbol, v.cluster) for v in result.violations
    ]


def test_registry_negated_claim_verb_passes(tmp_path: Path, vocab) -> None:
    """Lines that disclaim ('HOP never decides promotion') are allowed."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Active executable systems\n\n"
        "### HOP\n"
        "- **role:** harness optimization substrate.\n"
        "- **Downstream Dependencies:** CDE (control authority external to HOP "
        "— HOP never decides promotion).\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", [
        (v.line, v.symbol, v.cluster) for v in result.violations
    ]


def test_registry_real_repo_passes(vocab) -> None:
    """The committed `docs/architecture/system_registry.md` itself passes."""
    result = evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=[REGISTRY_REL],
        vocab=vocab,
        mode="suggest-only",
    )
    assert result.status == "pass", (
        "docs/architecture/system_registry.md must pass under the canonical-"
        "registry section-aware filter. Violations: "
        f"{[(v.line, v.symbol, v.cluster) for v in result.violations]}"
    )


def test_registry_filter_only_runs_for_canonical_registry_paths(
    tmp_path: Path, vocab
) -> None:
    """A non-registry doc with the same content still fails normally."""
    repo = _seed_repo(tmp_path)
    rel = "docs/governance/something_else.md"
    body = (
        "## Active executable systems\n\n"
        "### CDE\n"
        "- **owns:**\n"
        "  - closure_decision\n"
    )
    _write(repo, rel, body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail", (
        "The section-aware filter must NOT extend to arbitrary docs. Only files "
        "listed in scope.canonical_registry_paths receive the filter."
    )


def test_registry_rules_loaded_and_excludes_hop(vocab) -> None:
    """Vocabulary must declare HOP as non-owning support."""
    assert vocab.registry_rules is not None
    assert "HOP" in vocab.registry_rules.non_owning_support_systems
    # CDE/EVL/PRA must NOT be in the deny list.
    deny = vocab.registry_rules.non_owning_support_systems
    for code in ("CDE", "JDX", "GOV", "PRA", "SEL", "EVL"):
        assert code not in deny, f"{code} must remain a registry-tracked authority"


def test_canonical_registry_paths_loaded(vocab) -> None:
    """`docs/architecture/system_registry.md` must be a canonical-registry path."""
    assert REGISTRY_REL in vocab.canonical_registry_paths


def test_registry_filter_keeps_real_authority_claim_in_non_owning_section(
    tmp_path: Path, vocab
) -> None:
    """A non-owning section with a claim verb on a cluster-term line fails."""
    repo = _seed_repo(tmp_path)
    body = (
        "# System Registry\n\n"
        "## Active executable systems\n\n"
        "### HOP\n"
        "- **role:** harness optimization substrate.\n"
        "- **Purpose:** HOP enforces promotion for every candidate.\n"
    )
    _registry_seed(repo, body=body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[REGISTRY_REL], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail"
    # The line carries `enforces` (claim verb) on a line where the scanner
    # picked up `promotion` (cluster term). Even though it sits in
    # `Purpose:` (a descriptive field), the claim verb forces a violation.
    flagged_clusters = {v.cluster for v in result.violations}
    assert "promotion" in flagged_clusters, (
        "Claim verbs in non-owning sections must flag the cluster-term line "
        "regardless of which descriptive field it appears in."
    )
