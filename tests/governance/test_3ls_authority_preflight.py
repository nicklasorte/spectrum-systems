"""3LS authority preflight tests.

Covers:
- Non-owner TLC file containing 'allow' fails.
- Non-owner PQX file containing 'block' fails.
- Canonical TPA owner path may contain 'allow' (declared owner of control_decision).
- Missing neutral vocabulary file fails closed.
- Existing authority_leak_guard still catches forbidden_value (non-weakening regression).
- S4 review artifact with blocking=false still fails (severity must be blocking).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_3ls_authority_preflight as preflight  # noqa: E402
from scripts.authority_leak_rules import load_authority_registry  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "contracts" / "governance" / "authority_registry.json"
NEUTRAL_VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_neutral_vocabulary.json"


@pytest.fixture()
def registry() -> dict:
    return load_authority_registry(REGISTRY_PATH)


@pytest.fixture()
def neutral_vocab() -> dict:
    return preflight.load_neutral_vocabulary(NEUTRAL_VOCAB_PATH)


def _scratch_file(tmp_path: Path, rel_path: str, content: str) -> Path:
    """Create a real file inside the repo so the preflight reader sees it.

    The preflight resolves paths relative to REPO_ROOT, so we cannot use
    tmp_path alone; we materialize the file under spectrum_systems/modules
    or orchestration as appropriate, then unlink in the fixture teardown.
    """
    full = REPO_ROOT / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def test_non_owner_tlc_file_with_allow_fails(registry, neutral_vocab) -> None:
    rel = "spectrum_systems/modules/orchestration/tmp_tls_tlc_authority_leak.py"
    full = _scratch_file(REPO_ROOT, rel, "payload = {'decision': 'allow'}\n")
    try:
        result = preflight.run_preflight(
            repo_root=REPO_ROOT,
            changed_files=[rel],
            registry=registry,
            neutral_vocab=neutral_vocab,
        )
        assert result["status"] == "fail"
        tokens = {v.get("token") for v in result["violations"]}
        assert "allow" in tokens or "decision" in tokens
        # Suggestions reference neutral terms.
        suggested_terms = []
        for repair in result["suggested_repairs"]:
            suggested_terms.extend(repair.get("suggested_terms", []))
        assert any(term in {"passed_gate", "gate_evidence_valid"} for term in suggested_terms)
    finally:
        full.unlink(missing_ok=True)


def test_non_owner_pqx_file_with_block_fails(registry, neutral_vocab) -> None:
    rel = "spectrum_systems/modules/orchestration/tmp_tls_pqx_authority_leak.py"
    full = _scratch_file(REPO_ROOT, rel, "payload = {'decision': 'block'}\n")
    try:
        result = preflight.run_preflight(
            repo_root=REPO_ROOT,
            changed_files=[rel],
            registry=registry,
            neutral_vocab=neutral_vocab,
        )
        assert result["status"] == "fail"
        tokens = {v.get("token") for v in result["violations"]}
        assert "block" in tokens
    finally:
        full.unlink(missing_ok=True)


def test_canonical_tpa_owner_path_may_contain_allow(registry, neutral_vocab) -> None:
    """A declared TPA owner of control_decision may legitimately use 'allow'."""
    owner_path = REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "cde_decision_flow.py"
    original = owner_path.read_text(encoding="utf-8") if owner_path.exists() else ""
    owner_path.write_text(
        original
        + "\nOWNER_PROBE = {'decision': 'allow', 'certification_status': 'certified'}\n",
        encoding="utf-8",
    )
    try:
        rel = owner_path.relative_to(REPO_ROOT).as_posix()
        result = preflight.run_preflight(
            repo_root=REPO_ROOT,
            changed_files=[rel],
            registry=registry,
            neutral_vocab=neutral_vocab,
        )
        assert result["status"] == "pass"
        assert result["summary"]["violation_count"] == 0
    finally:
        owner_path.write_text(original, encoding="utf-8")


def test_missing_neutral_vocabulary_fails_closed(monkeypatch, tmp_path: Path) -> None:
    bogus = tmp_path / "missing.json"
    with pytest.raises(preflight.ThreeLetterAuthorityPreflightError):
        preflight.load_neutral_vocabulary(bogus)


def test_neutral_vocabulary_wrong_artifact_type_fails_closed(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"artifact_type": "something_else"}), encoding="utf-8")
    with pytest.raises(preflight.ThreeLetterAuthorityPreflightError):
        preflight.load_neutral_vocabulary(wrong)


def test_existing_authority_leak_guard_still_catches_forbidden_value() -> None:
    """Non-weakening regression: the existing CI guard must still fail on non-owner forbidden_value."""
    rel = "spectrum_systems/modules/runtime/tmp_tls_existing_guard_violator.py"
    violator = REPO_ROOT / rel
    violator.write_text("payload = {'decision': 'allow'}\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/run_authority_leak_guard.py",
                "--changed-files",
                rel,
                "--output",
                "outputs/authority_leak_guard/test_3ls_existing_guard_result.json",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        combined = proc.stdout + proc.stderr
        assert "forbidden_field" in combined or "forbidden_value" in combined
    finally:
        violator.unlink(missing_ok=True)


def test_s4_non_blocking_review_artifact_still_fails(registry, neutral_vocab) -> None:
    """A review artifact attempting to mark an S4 finding non-blocking is rejected.

    The 3LS preflight refuses to silence severity-bearing findings by their
    severity tag alone. This test verifies the structured artifact carrying
    forbidden authority vocabulary still triggers a violation regardless of
    any 'blocking: false' annotation, so reviewers cannot smuggle leaks past
    the guard via metadata.
    """
    rel = "contracts/examples/tmp_3ls_s4_non_blocking_review.json"
    payload = {
        "artifact_type": "review_artifact",
        "severity": "S4",
        "blocking": False,
        "decision": "allow",
        "enforcement_action": "freeze",
    }
    target = REPO_ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        result = preflight.run_preflight(
            repo_root=REPO_ROOT,
            changed_files=[rel],
            registry=registry,
            neutral_vocab=neutral_vocab,
        )
        assert result["status"] == "fail"
        # Find shape or vocab violations regardless of blocking annotation.
        rules = {v.get("rule") for v in result["violations"]}
        assert any(rule for rule in rules if rule)  # at least one rule fired
    finally:
        target.unlink(missing_ok=True)


def test_classify_three_letter_system_owner_match(registry) -> None:
    classification = preflight.classify_three_letter_system(
        "spectrum_systems/modules/orchestration/tlc_router.py", registry
    )
    assert classification["system"] == "TLC"
    assert classification["owner"] is True
    assert "routing" in classification["authority_domains"]


def test_classify_three_letter_system_unknown_for_random_path(registry) -> None:
    classification = preflight.classify_three_letter_system(
        "spectrum_systems/modules/utility/random_helper.py", registry
    )
    assert classification["owner"] is False
    assert classification["system"] == "unknown"
