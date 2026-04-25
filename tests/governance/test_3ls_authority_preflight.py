"""3-letter system authority boundary preflight tests.

These tests assert non-owning behavior of the firewall:

- The firewall reads canonical responsibility from the registry; it does not
  redefine it.
- Non-owning support surfaces (TLC/PQX/...) cannot use protected vocabulary.
- A canonical responsibility owner path may legitimately use protected
  vocabulary because the registry already attributes it.
- Missing neutral vocabulary fails closed.
- Existing authority_leak_guard still catches forbidden_value (non-weakening
  regression).
- S4 review artifact with blocking=false still fails.
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


def _scratch_file(rel_path: str, content: str) -> Path:
    full = REPO_ROOT / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def test_non_support_tlc_path_with_allow_fails(registry, neutral_vocab) -> None:
    rel = "spectrum_systems/modules/orchestration/tmp_tls_tlc_support_leak.py"
    full = _scratch_file(rel, "payload = {'decision': 'allow'}\n")
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
        suggested_terms = []
        for repair in result["suggested_repairs"]:
            suggested_terms.extend(repair.get("suggested_terms", []))
        assert any(term in {"passed_gate", "gate_evidence_valid"} for term in suggested_terms)
    finally:
        full.unlink(missing_ok=True)


def test_non_support_pqx_path_with_block_fails(registry, neutral_vocab) -> None:
    rel = "spectrum_systems/modules/orchestration/tmp_tls_pqx_support_leak.py"
    full = _scratch_file(rel, "payload = {'decision': 'block'}\n")
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


def test_canonical_owner_path_may_contain_allow(registry, neutral_vocab) -> None:
    """A canonical responsibility owner path may legitimately contain 'allow'."""
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


def test_missing_neutral_vocabulary_fails_closed(tmp_path: Path) -> None:
    bogus = tmp_path / "missing.json"
    with pytest.raises(preflight.ThreeLetterAuthorityPreflightError):
        preflight.load_neutral_vocabulary(bogus)


def test_neutral_vocabulary_wrong_artifact_type_fails_closed(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"artifact_type": "something_else"}), encoding="utf-8")
    with pytest.raises(preflight.ThreeLetterAuthorityPreflightError):
        preflight.load_neutral_vocabulary(wrong)


def test_existing_authority_leak_guard_still_catches_forbidden_value() -> None:
    """Non-weakening regression: the CI gate still fails on non-support forbidden_value."""
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

    The preflight refuses to silence severity-bearing findings by their
    severity tag alone. This test verifies the structured artifact carrying
    forbidden vocabulary still triggers a violation regardless of any
    'blocking: false' annotation, so reviewers cannot smuggle leaks past
    the firewall via metadata.
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
        rules = {v.get("rule") for v in result["violations"]}
        assert any(rule for rule in rules if rule)
    finally:
        target.unlink(missing_ok=True)


def test_classify_returns_support_match_with_canonical_source(registry) -> None:
    """The classifier returns boundary_role and a canonical_authority_source pointer.

    It does not return ownership; canonical responsibility is referenced via
    canonical_authority_source pointing back to system_registry.md.
    """
    classification = preflight.classify_three_letter_system(
        "spectrum_systems/modules/orchestration/tlc_router.py", registry
    )
    assert classification["system"] == "TLC"
    assert classification["support_match"] is True
    assert classification["boundary_role"] == "routing_support"
    assert classification["canonical_authority_source"] == "docs/architecture/system_registry.md"


def test_classify_returns_unknown_for_random_path(registry) -> None:
    classification = preflight.classify_three_letter_system(
        "spectrum_systems/modules/utility/random_helper.py", registry
    )
    assert classification["support_match"] is False
    assert classification["system"] == "unknown"
    assert classification["canonical_authority_source"] == "docs/architecture/system_registry.md"


def test_firewall_does_not_create_new_ownership(registry) -> None:
    """The boundary guidance entries declare canonical_authority_source pointing
    back to system_registry.md and never declare ownership of their own.
    """
    guidance = registry.get("three_letter_system_boundary_guidance", {})
    assert guidance, "boundary guidance must be declared in the registry"
    for system, body in guidance.items():
        if not isinstance(body, dict):
            continue
        # No entry may carry an authority_domains field — that would be
        # an ownership claim. Only boundary_role + non_authority_assertions
        # + canonical_authority_source are allowed.
        assert "authority_domains" not in body, (
            f"{system} boundary entry must not declare authority_domains; "
            "ownership lives in system_registry.md"
        )
        assert "owner_path_prefixes" not in body, (
            f"{system} boundary entry must not declare owner_path_prefixes; "
            "use support_path_prefixes for non-owning classification"
        )
        if system == "guidance_note" or system == "canonical_authority_source":
            continue
        # Every system entry must point at the canonical registry.
        assert (
            body.get("canonical_authority_source") == "docs/architecture/system_registry.md"
        ), f"{system} must reference canonical_authority_source"
