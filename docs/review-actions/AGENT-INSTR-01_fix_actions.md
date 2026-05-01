# AGENT-INSTR-01 Fix Actions

Each `must_fix` finding from `docs/reviews/AGENT-INSTR-01_redteam.md`
is resolved in the same PR. Fix actions are listed below in finding
order. Authority note: APR, M3L, CLP, and APU are observation-only
systems; canonical ownership remains with the systems declared in
`docs/architecture/system_registry.md`.

## MF-01 — Agent claims PR-ready without an APR artifact
- **Finding ID:** MF-01
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_requires_apr_runner_invocation`
  and `::test_claude_md_requires_apr_runner_invocation`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — AGENT-INSTR-01 §1 requires the APR runner
  invocation and §5 lists missing-APR as a fail-closed stop condition.

## MF-02 — Agent claims PR-ready without an M3L path measurement
- **Finding ID:** MF-02
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_requires_m3l_artifact_path`,
  `::test_claude_md_requires_m3l_artifact_path`,
  `::test_agents_md_evidence_section_lists_all_legs`,
  `::test_claude_md_evidence_section_lists_all_legs`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — §2 names the canonical M3L artifact path
  and §5 lists missing-M3L as a fail-closed stop condition.

## MF-03 — Agent claims PR-update-ready without an APU artifact
- **Finding ID:** MF-03
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_requires_apu_artifact_path`,
  `::test_claude_md_requires_apu_artifact_path`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — §3 names the canonical APU artifact path
  and §5 lists missing-APU and `not_ready` APU readiness as stop
  conditions.

## MF-04 — A `present` leg is reported without artifact refs
- **Finding ID:** MF-04
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_evidence_section_lists_all_legs`,
  `::test_claude_md_evidence_section_lists_all_legs`. Upstream APR
  schema test
  `test_pass_without_output_artifact_refs_is_schema_invalid` covers the
  contract layer.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — §1 ties every present check to one or
  more `output_artifact_refs` and §5 lists "any `present` claim lacks
  an artifact ref" as a stop condition.

## MF-05 — A `missing` / `partial` / `unknown` leg is reported without reason codes
- **Finding ID:** MF-05
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:** upstream APR schema test
  `test_non_pass_without_reason_codes_is_schema_invalid` (covers the
  contract layer). The instruction-text rule in §1 + §5 binds the
  agent claim to that schema constraint.
- **Command run:** `python -m pytest tests/test_agent_pr_precheck.py -q`
- **Disposition:** resolved — §1 + §5 require reason codes for every
  non-pass check.

## MF-06 — `repo_mutating` unknown treated as ready
- **Finding ID:** MF-06
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_repo_mutating_unknown_stops_pr_ready`,
  `::test_claude_md_repo_mutating_unknown_stops_pr_ready`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — §5 lists "`repo_mutating` is unknown" as
  a fail-closed stop condition.

## MF-07 — PR body prose substituted for artifact refs
- **Finding ID:** MF-07
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_no_artifact_no_proof_clause_present`,
  `::test_claude_md_no_artifact_no_proof_clause_present`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — §4 fixes the structured evidence-section
  template and §5 states "Prose substitution is not evidence."

## MF-08 — M3L `fell_out_at` ignored
- **Finding ID:** MF-08
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_evidence_section_lists_all_legs`,
  `::test_claude_md_evidence_section_lists_all_legs`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — §4 requires `fell_out_at` in the
  evidence section and §5 lists non-null `fell_out_at` as a stop
  condition.

## MF-09 — Instructions use reserved authority verbs in non-owner context
- **Finding ID:** MF-09
- **Files changed:** `AGENTS.md`, `CLAUDE.md`
- **Test added/updated:**
  `tests/test_agent_instruction_apr_m3l_required.py::test_agents_md_avoids_reserved_authority_verbs_in_agent_instr_section`,
  `::test_claude_md_avoids_reserved_authority_verbs_in_agent_instr_section`.
- **Command run:** `python -m pytest tests/test_agent_instruction_apr_m3l_required.py -q`
- **Disposition:** resolved — the AGENT-INSTR-01 section uses
  observation-only vocabulary, includes a §6 authority-boundary
  paragraph, and the new test scans the section for reserved verbs.
