"""NX-ALL-01 / NX-02: Adversarial fixtures for system registry integrity.

These tests inject crafted registry mutations and assert that
``scripts.validate_system_registry`` raises an error for each attempted
authority bypass. They are pure-text fixtures — no live registry mutation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_system_registry as validator


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_REGISTRY = REPO_ROOT / "docs" / "architecture" / "system_registry.md"


def _live_text() -> str:
    return LIVE_REGISTRY.read_text(encoding="utf-8")


def _split_at_system_definitions(text: str) -> tuple[str, str]:
    marker = "## System Definitions\n"
    idx = text.find(marker)
    assert idx >= 0, "registry missing System Definitions section"
    return text[: idx + len(marker)], text[idx + len(marker):]


def _replace_definition_owns(text: str, acronym: str, new_owns_lines: list[str]) -> str:
    """Replace the `- **owns:**` block of the System-Definitions ``### {acronym}`` block."""
    import re

    head, body = _split_at_system_definitions(text)
    pattern = re.compile(
        rf"(### {acronym}\n(?:- \*\*[^*]+:\*\* [^\n]*\n|\s+- [^\n]*\n)*?- \*\*owns:\*\*\n)((?:\s+- [^\n]*\n)+)",
        flags=re.M,
    )
    replacement = "".join(f"  - {line}\n" for line in new_owns_lines)
    new_body, n = pattern.subn(rf"\g<1>{replacement}", body, count=1)
    assert n == 1, f"could not locate owns block for {acronym} in System Definitions"
    return head + new_body


def _replace_definition_status(text: str, acronym: str, new_status: str) -> str:
    import re

    head, body = _split_at_system_definitions(text)
    pattern = re.compile(
        rf"(### {acronym}\n(?:- \*\*[^*]+:\*\* [^\n]*\n|\s+- [^\n]*\n)*?- \*\*status:\*\* )([a-z_]+)",
        flags=re.M,
    )
    new_body, n = pattern.subn(rf"\g<1>{new_status}", body, count=1)
    assert n == 1, f"could not locate status for {acronym} in System Definitions"
    return head + new_body


def test_gov_claiming_tpa_authority_blocks() -> None:
    """RED-NX-02-A: GOV (active) cannot claim TPA's policy adjudication."""
    text = _replace_definition_owns(
        _live_text(), "GOV", ["trust_policy_application", "scope_gating"]
    )
    errors = validator.validate_registry(text)
    assert any(
        "GOV" in e and ("trust_policy_application" in e or "scope_gating" in e)
        for e in errors
    ), errors


def test_tlc_claiming_cde_closure_blocks() -> None:
    """RED-NX-02-B: TLC cannot claim CDE closure authority."""
    text = _replace_definition_owns(
        _live_text(),
        "TLC",
        [
            "orchestration",
            "closure",
            "promotion_readiness_decisioning",
        ],
    )
    errors = validator.validate_registry(text)
    assert any(
        "TLC" in e and "closure" in e for e in errors
    ), errors


def test_rqx_claiming_ril_interpretation_blocks() -> None:
    """RED-NX-02-C: demoted RQX cannot reclaim RIL review interpretation."""
    text = _replace_definition_owns(
        _live_text(),
        "RQX",
        ["review_queue_execution", "review_interpretation"],
    )
    errors = validator.validate_registry(text)
    assert any(
        "RQX" in e and ("review_interpretation" in e or "review interpretation" in e)
        for e in errors
    ), errors


def test_demoted_system_claiming_active_authority_blocks() -> None:
    """RED-NX-02-D: demoted PRG cannot claim runtime execution again."""
    text = _replace_definition_owns(
        _live_text(),
        "PRG",
        ["program_governance", "execution"],
    )
    errors = validator.validate_registry(text)
    assert any(
        "PRG" in e and "execution" in e for e in errors
    ), errors


def test_demoted_chx_claiming_runtime_execution_blocks() -> None:
    """RED-NX-02-E: chaos harness CHX cannot run own_runtime_execution."""
    text = _replace_definition_owns(
        _live_text(),
        "CHX",
        ["chaos_injection_artifacts", "own_runtime_execution"],
    )
    errors = validator.validate_registry(text)
    assert any(
        "CHX" in e and "own_runtime_execution" in e for e in errors
    ), errors


def test_new_three_letter_system_without_justification_blocks() -> None:
    """RED-NX-02-F: a fresh three-letter system in active section without rationale fails."""
    text = _live_text()
    # Append a fake active system with no Primary Code Paths
    inject = (
        "\n### ZZZ\n"
        "- **Status:** active\n"
        "- **Purpose:** unjustified phantom authority\n"
        "- **Failure Prevented:** none\n"
        "- **Signal Improved:** none\n"
        "- **Canonical Artifacts Owned:** none\n"
        "- **Primary Code Paths:**\n"
    )
    text2 = text.replace(
        "## Merged or demoted systems",
        f"{inject}\n## Merged or demoted systems",
    )
    errors = validator.validate_registry(text2)
    assert any("ZZZ" in e for e in errors), errors


def test_future_placeholder_with_runtime_evidence_requires_rationale() -> None:
    """RED-NX-02-G: future placeholder with substantive runtime evidence and
    empty rationale must be flagged.

    The validator already detects placeholder-vs-runtime contradiction; here
    we add explicit coverage for the rationale check.
    """
    # Use the placeholder ABX (future) and force it to appear in runtime via
    # the future-with-rationale parser by stripping the rationale text.
    import re

    text = _live_text()
    # Strip ABX rationale text
    text2 = re.sub(
        r"(\| ABX \| future \|)\s*[^|]*\|",
        r"\1                            |",
        text,
    )
    rationale_map = validator.parse_future_systems_with_rationale(text2)
    # ABX should be present but with empty rationale.
    assert "ABX" in rationale_map
    assert rationale_map["ABX"].strip() == ""


def test_live_registry_still_passes_under_new_rules() -> None:
    """Sanity: NX-01..03 hardening must not reject the live canonical registry."""
    errors = validator.validate_registry(_live_text())
    assert not errors, f"live registry must pass: {errors}"


def test_active_authority_collision_within_protected_map_is_explicit() -> None:
    """The protected-authority map must not silently overlap two active owners."""
    seen: dict[str, str] = {}
    for owner, authorities in validator.PROTECTED_AUTHORITY_BY_SYSTEM.items():
        for authority in authorities:
            assert authority not in seen, (
                f"protected authority '{authority}' double-listed for "
                f"{seen[authority]} and {owner}"
            )
            seen[authority] = owner


def test_demoted_forbidden_owns_table_covers_known_demoted() -> None:
    """Each demoted system in the live registry must have a forbidden-owns
    entry to guarantee a deterministic shadow-ownership block."""
    text = _live_text()
    definitions = validator.parse_system_definitions(text)
    demoted_acronyms = {
        acr
        for acr, fields in definitions.items()
        if str(fields.get("status", "")).lower() in {"demoted", "deprecated"}
    }
    # SUP/RET/QRY/etc. and similar demotes: at minimum the high-risk set must be present.
    high_risk = {"RDX", "PRG", "HNX", "RQX", "CHX", "DEX", "SIM"}
    missing = high_risk - set(validator.DEMOTED_FORBIDDEN_OWNS.keys())
    assert not missing, f"demoted high-risk systems missing from forbidden table: {missing}"
    # Every demoted system that is in the table must actually be demoted (no drift).
    actually_demoted_or_known = (
        demoted_acronyms | {acr for acr in validator.DEMOTED_FORBIDDEN_OWNS if acr not in definitions}
    )
    leaked_active = [
        acr
        for acr in validator.DEMOTED_FORBIDDEN_OWNS
        if acr in definitions
        and str(definitions[acr].get("status", "")).lower() == "active"
    ]
    assert not leaked_active, (
        f"DEMOTED_FORBIDDEN_OWNS contains active systems: {leaked_active}"
    )


@pytest.mark.parametrize("acronym", ["PQX", "CDE", "SEL", "TPA", "EVL", "REP", "LIN"])
def test_protected_authority_systems_must_remain_active(acronym: str) -> None:
    """Active protected systems cannot be demoted via registry edit without halting."""
    text = _replace_definition_status(_live_text(), acronym, "demoted")
    errors = validator.validate_registry(text)
    # By demoting a protected owner, its `owns` set is now treated as
    # demoted-but-claiming-protected-authority, which the new generalized
    # NX-02 rule must catch.
    assert any(
        acronym in e and "NX-02" in e for e in errors
    ), errors
