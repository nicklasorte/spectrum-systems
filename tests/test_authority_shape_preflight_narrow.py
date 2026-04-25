"""Regression tests for AUTH-SHAPE-01F narrowed authority-shape preflight.

The previous shape preflight matched any identifier whose subtoken contained
a generic governance noun (``decision``, ``promotion``, ``enforcement``,
``certification``, ``adjudication``). This produced 179 false positives in
suggest-only mode on PR #1209.

The narrowed model only flags ``<3-letter system> <action verb>`` constructs
and respects an explicit phrase allowlist for presence-of-evidence framings.
This module verifies:

  * the protected-authority phrases listed in the AUTH-SHAPE-01F task still
    fail closed; and
  * the neutral artifact/evidence phrases listed in the task still pass.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.governance.authority_shape_preflight import (
    evaluate_preflight,
    load_vocabulary,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"
NEUTRAL_PATH = REPO_ROOT / "contracts" / "governance" / "authority_neutral_vocabulary.json"


@pytest.fixture(scope="module")
def vocab():
    return load_vocabulary(VOCAB_PATH)


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "spectrum_systems" / "modules" / "hop").mkdir(parents=True)
    (repo / "contracts" / "governance").mkdir(parents=True)
    # Mirror the shared neutral allowlist into the sandbox so the loader picks
    # it up. The loader resolves the path either against vocab.parent.parent
    # (the repo root) or REPO_ROOT.
    (repo / "contracts" / "governance" / "authority_neutral_vocabulary.json").write_text(
        NEUTRAL_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return repo


def _write(repo: Path, rel: str, body: str) -> str:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return rel


# ---------------------------------------------------------------------------
# Protected drift — these phrases MUST still fail
# ---------------------------------------------------------------------------

PROTECTED_PHRASES = [
    pytest.param("# GOV decides readiness here.\n", "decision", id="GOV-decides-readiness"),
    pytest.param("# GOV approves promotion here.\n", "approval", id="GOV-approves-promotion"),
    pytest.param("# PRA approves readiness here.\n", "approval", id="PRA-approves-readiness"),
    pytest.param("# PRA approves promotion here.\n", "approval", id="PRA-approves-promotion"),
    pytest.param("# TLC enforces policy here.\n", "enforcement", id="TLC-enforces-policy"),
    pytest.param("# SEL decides closure here.\n", "decision", id="SEL-decides-closure"),
    pytest.param("# LIN owns replay here.\n", "authority", id="LIN-owns-replay"),
    pytest.param("# POL adjudicates policy here.\n", "decision", id="POL-adjudicates-policy"),
]


@pytest.mark.parametrize("body, expected_cluster", PROTECTED_PHRASES)
def test_protected_phrase_still_fails(
    tmp_path: Path, vocab, body: str, expected_cluster: str
) -> None:
    repo = _seed_repo(tmp_path)
    rel = _write(repo, "spectrum_systems/modules/hop/synthetic.py", body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "fail", (
        f"Expected protected-authority phrase to fail closed; got status="
        f"{result.status!r}, violations={[v.to_dict() for v in result.violations]}"
    )
    clusters = {v.cluster for v in result.violations}
    assert expected_cluster in clusters, (
        f"Expected violation in cluster {expected_cluster!r}; got clusters={clusters!r}"
    )


# ---------------------------------------------------------------------------
# Neutral artifact/evidence phrasings — these MUST pass
# ---------------------------------------------------------------------------

NEUTRAL_PHRASES = [
    pytest.param("# CDE decision artifact reference here.\n", id="CDE-decision-artifact"),
    pytest.param("# CDE decision input reference here.\n", id="CDE-decision-input"),
    pytest.param("# TPA adjudication evidence reference here.\n", id="TPA-adjudication-evidence"),
    pytest.param("# TPA adjudication record reference here.\n", id="TPA-adjudication-record"),
    pytest.param("# SEL enforcement record reference here.\n", id="SEL-enforcement-record"),
    pytest.param("# SEL enforcement evidence reference here.\n", id="SEL-enforcement-evidence"),
    pytest.param("# GOV certification package reference here.\n", id="GOV-certification-package"),
    pytest.param("# GOV certification evidence reference here.\n", id="GOV-certification-evidence"),
    pytest.param("# PRA promotion-readiness input reference here.\n", id="PRA-promotion-readiness-input"),
    pytest.param("# POL policy-posture input reference here.\n", id="POL-policy-posture-input"),
    pytest.param("# LIN lineage evidence reference here.\n", id="LIN-lineage-evidence"),
    pytest.param("# REP replay evidence reference here.\n", id="REP-replay-evidence"),
]


@pytest.mark.parametrize("body", NEUTRAL_PHRASES)
def test_neutral_phrase_does_not_fail(tmp_path: Path, vocab, body: str) -> None:
    repo = _seed_repo(tmp_path)
    rel = _write(repo, "spectrum_systems/modules/hop/synthetic.py", body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", (
        f"Neutral phrase {body!r} must not fail; violations="
        f"{[v.to_dict() for v in result.violations]}"
    )
    assert result.violations == []


# ---------------------------------------------------------------------------
# Generic governance noun MUST NOT trigger on its own
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "body",
    [
        "# decision artifact lives here.\n",
        "# adjudication evidence record lives here.\n",
        "# promotion readiness input lives here.\n",
        "# enforcement signal record lives here.\n",
        "# certification evidence package lives here.\n",
    ],
    ids=[
        "decision-artifact",
        "adjudication-evidence-record",
        "promotion-readiness-input",
        "enforcement-signal-record",
        "certification-evidence-package",
    ],
)
def test_generic_governance_noun_alone_does_not_fail(
    tmp_path: Path, vocab, body: str
) -> None:
    """Generic governance nouns without a 3-letter actor must not trigger."""
    repo = _seed_repo(tmp_path)
    rel = _write(repo, "spectrum_systems/modules/hop/synthetic.py", body)
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", (
        f"Generic noun {body!r} must not fail; violations="
        f"{[v.to_dict() for v in result.violations]}"
    )


# ---------------------------------------------------------------------------
# Common English uppercase tokens (NOT, AND, …) must not be treated as actors
# ---------------------------------------------------------------------------

def test_does_not_keyword_does_not_trigger_violation(tmp_path: Path, vocab) -> None:
    """``does NOT issue closure decisions`` must not flag NOT as a system actor."""
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "spectrum_systems/modules/hop/synthetic.py",
        "# This module does NOT issue closure decisions.\n",
    )
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", (
        "NOT must be treated as an English negation, not a 3-letter system; "
        f"violations={[v.to_dict() for v in result.violations]}"
    )


def test_canonical_owner_path_may_use_action_verb(tmp_path: Path, vocab) -> None:
    """A registered canonical-owner path may use the cluster's action verb without flagging."""
    repo = _seed_repo(tmp_path)
    rel = _write(
        repo,
        "spectrum_systems/modules/runtime/cde_decision_flow.py",
        "# CDE decides readiness within its canonical scope.\n",
    )
    result = evaluate_preflight(
        repo_root=repo, changed_files=[rel], vocab=vocab, mode="suggest-only"
    )
    assert result.status == "pass", (
        f"Canonical owner using its own verb must not be flagged; violations="
        f"{[v.to_dict() for v in result.violations]}"
    )


# ---------------------------------------------------------------------------
# Vocabulary contract: neutral allowlist must be loaded
# ---------------------------------------------------------------------------

def test_neutral_phrase_allowlist_loaded(vocab) -> None:
    assert vocab.neutral_phrases, "neutral phrase allowlist must be loaded into vocab"
    expected_subset = {
        "CDE decision artifact",
        "TPA adjudication evidence",
        "SEL enforcement record",
        "GOV certification package",
        "PRA promotion-readiness input",
        "POL policy-posture input",
        "LIN lineage evidence",
        "REP replay evidence",
    }
    loaded = set(vocab.neutral_phrases)
    missing = expected_subset - loaded
    assert not missing, f"neutral allowlist missing required phrases: {missing}"


def test_action_verbs_loaded_for_each_cluster(vocab) -> None:
    """Each cluster used by the protected list must declare action_verbs."""
    needed = {"decision", "approval", "enforcement", "authority"}
    by_name = {c.name: c for c in vocab.clusters}
    for name in needed:
        assert name in by_name, f"cluster {name!r} missing from vocabulary"
        assert by_name[name].action_verbs, (
            f"cluster {name!r} must declare action_verbs under the narrowed model"
        )
