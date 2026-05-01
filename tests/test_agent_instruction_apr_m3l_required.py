"""AGENT-INSTR-01 — Agent instruction text must require APR / M3L / APU
evidence before any AI PR-ready or PR-update-ready claim.

These tests are deterministic. They read the static instruction surface
(``AGENTS.md``, ``CLAUDE.md``, ``tests/AGENTS.md``) and assert that the
AGENT-INSTR-01 rule is present and authority-safe. They do not run any
APR / M3L / APU runner.

Authority note: APR, M3L, CLP, and APU each emit observation-only
readiness or measurement artifacts. Canonical ownership remains with
the systems declared in ``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

AGENTS_MD = REPO_ROOT / "AGENTS.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
TESTS_AGENTS_MD = REPO_ROOT / "tests" / "AGENTS.md"

AGENT_INSTR_SECTION_HEADING = (
    "AI Repo-Mutating Work — Required 3LS Evidence (AGENT-INSTR-01)"
)

# Reserved authority verbs that the AGENT-INSTR-01 instruction surface
# must not use to describe APR / M3L / CLP / APU. These are owner-only
# verbs and must not appear in the AGENT-INSTR-01 section text in either
# affirmative or negated forms.
RESERVED_AUTHORITY_VERBS = (
    "approve",
    "approved",
    "approval",
    "certify",
    "certifies",
    "certified",
    "certification",
    "promote",
    "promoted",
    "promotion",
    "enforce",
    "enforces",
    "enforced",
    "enforcement",
    "decide",
    "decides",
    "decided",
    "decision",
    "adjudicate",
    "adjudication",
    "authorize",
    "authorized",
    "authorization",
)

# Required artifact-system tokens that must appear in the agent
# instruction surface for AGENT-INSTR-01 to be considered actionable.
REQUIRED_TOKENS_INSTRUCTION_SURFACE = (
    "APR",
    "M3L",
    "APU",
    "AEX",
    "PQX",
    "EVL",
    "TPA",
    "CDE",
    "SEL",
)

REQUIRED_ARTIFACT_PATHS = (
    "outputs/agent_pr_precheck/agent_pr_precheck_result.json",
    "outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json",
    "outputs/agent_pr_update/agent_pr_update_ready_result.json",
)

REQUIRED_RUNNER_REFERENCE = "scripts/run_agent_pr_precheck.py"


def _read(path: Path) -> str:
    assert path.is_file(), f"required agent instruction file missing: {path}"
    return path.read_text(encoding="utf-8")


def _extract_section(text: str, heading: str) -> str:
    """Return the AGENT-INSTR-01 section body, ending at the next ``## `` heading."""
    pattern = re.compile(
        r"##\s+" + re.escape(heading) + r"\s*\n(.*?)(?=\n##\s+|\Z)",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match, f"expected section heading not found: {heading!r}"
    return match.group(1)


# ---------------------------------------------------------------------------
# AGENTS.md
# ---------------------------------------------------------------------------


def test_agents_md_has_agent_instr_01_section() -> None:
    text = _read(AGENTS_MD)
    assert AGENT_INSTR_SECTION_HEADING in text, (
        "AGENTS.md must include the AGENT-INSTR-01 required-3LS-evidence section"
    )


def test_agents_md_requires_apr_runner_invocation() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    assert REQUIRED_RUNNER_REFERENCE in section, (
        "AGENTS.md AGENT-INSTR-01 section must reference scripts/run_agent_pr_precheck.py"
    )
    for flag in ("--work-item-id", "--agent-type", "--repo-mutating"):
        assert flag in section, (
            f"AGENTS.md AGENT-INSTR-01 section must show APR flag {flag!r}"
        )


def test_agents_md_requires_m3l_artifact_path() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    assert (
        "outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json"
        in section
    ), "AGENTS.md AGENT-INSTR-01 section must reference the M3L artifact path"


def test_agents_md_requires_apu_artifact_path() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    assert (
        "outputs/agent_pr_update/agent_pr_update_ready_result.json" in section
    ), "AGENTS.md AGENT-INSTR-01 section must reference the APU artifact path"


def test_agents_md_evidence_section_lists_all_legs() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    for token in REQUIRED_TOKENS_INSTRUCTION_SURFACE:
        assert re.search(rf"\b{re.escape(token)}\b", section), (
            f"AGENTS.md AGENT-INSTR-01 evidence section must reference {token}"
        )
    for token in (
        "first_missing_leg",
        "first_failed_check",
        "fell_out_at",
        "loop_complete",
        "pr_ready_status",
        "pr_update_ready_status",
    ):
        assert token in section, (
            f"AGENTS.md AGENT-INSTR-01 evidence section must include {token}"
        )


def test_agents_md_repo_mutating_unknown_stops_pr_ready() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    assert re.search(r"`?repo_mutating`?\s+is\s+unknown", section), (
        "AGENTS.md AGENT-INSTR-01 must call out `repo_mutating` unknown as a stop condition"
    )


def test_agents_md_no_artifact_no_proof_clause_present() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    assert "No artifact = not proven" in section, (
        "AGENTS.md AGENT-INSTR-01 must state explicitly that missing artifacts are not proof"
    )


def test_agents_md_avoids_reserved_authority_verbs_in_agent_instr_section() -> None:
    section = _extract_section(_read(AGENTS_MD), AGENT_INSTR_SECTION_HEADING)
    lowered = section.lower()
    found: list[str] = []
    for verb in RESERVED_AUTHORITY_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lowered):
            found.append(verb)
    assert not found, (
        "AGENTS.md AGENT-INSTR-01 section must not use reserved authority verbs "
        f"in non-owner context: found={found}"
    )


# ---------------------------------------------------------------------------
# CLAUDE.md
# ---------------------------------------------------------------------------


def test_claude_md_has_agent_instr_01_section() -> None:
    text = _read(CLAUDE_MD)
    assert AGENT_INSTR_SECTION_HEADING in text, (
        "CLAUDE.md must include the AGENT-INSTR-01 required-3LS-evidence section"
    )


def test_claude_md_requires_apr_runner_invocation() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    assert REQUIRED_RUNNER_REFERENCE in section
    for flag in ("--work-item-id", "--agent-type", "--repo-mutating"):
        assert flag in section


def test_claude_md_requires_m3l_artifact_path() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    assert (
        "outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json"
        in section
    )


def test_claude_md_requires_apu_artifact_path() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    assert "outputs/agent_pr_update/agent_pr_update_ready_result.json" in section


def test_claude_md_evidence_section_lists_all_legs() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    for token in REQUIRED_TOKENS_INSTRUCTION_SURFACE:
        assert re.search(rf"\b{re.escape(token)}\b", section)
    for token in (
        "first_missing_leg",
        "first_failed_check",
        "fell_out_at",
        "loop_complete",
        "pr_ready_status",
        "pr_update_ready_status",
    ):
        assert token in section


def test_claude_md_repo_mutating_unknown_stops_pr_ready() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    assert re.search(r"`?repo_mutating`?\s+is\s+unknown", section)


def test_claude_md_no_artifact_no_proof_clause_present() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    assert "No artifact = not proven" in section


def test_claude_md_avoids_reserved_authority_verbs_in_agent_instr_section() -> None:
    section = _extract_section(_read(CLAUDE_MD), AGENT_INSTR_SECTION_HEADING)
    lowered = section.lower()
    found: list[str] = []
    for verb in RESERVED_AUTHORITY_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lowered):
            found.append(verb)
    assert not found, (
        "CLAUDE.md AGENT-INSTR-01 section must not use reserved authority verbs "
        f"in non-owner context: found={found}"
    )


# ---------------------------------------------------------------------------
# tests/AGENTS.md
# ---------------------------------------------------------------------------


def test_tests_agents_md_references_agent_instr_01() -> None:
    text = _read(TESTS_AGENTS_MD)
    assert "AGENT-INSTR-01" in text, (
        "tests/AGENTS.md must reference AGENT-INSTR-01"
    )
    assert "test_agent_instruction_apr_m3l_required.py" in text, (
        "tests/AGENTS.md must list the AGENT-INSTR-01 test file"
    )


def test_tests_agents_md_lists_required_observation_systems() -> None:
    text = _read(TESTS_AGENTS_MD)
    for token in ("APR", "M3L", "APU"):
        assert token in text, (
            f"tests/AGENTS.md must reference {token} as an observation-only system"
        )
