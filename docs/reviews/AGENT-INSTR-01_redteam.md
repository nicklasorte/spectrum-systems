# AGENT-INSTR-01 Red-Team Review — Require APR / M3L / APU Evidence

Categories: `must_fix` (blocks the PR), `should_fix` (open follow-up
before the next dependent slice), `observation` (informational).

AGENT-INSTR-01 is an instruction-text hardening slice. It updates
`AGENTS.md`, `CLAUDE.md`, and `tests/AGENTS.md` so that any Codex/Claude
repo-mutating slice must surface APR / M3L / APU artifact-backed
evidence before the agent claims PR-ready or PR-update-ready. APR, M3L,
CLP, and APU are observation-only systems; canonical ownership of
admission, execution closure, eval evidence, policy/scope,
continuation/closure, and final-gate signal remains with the systems
declared in `docs/architecture/system_registry.md`.

## Findings

### MF-01 — Agent claims PR-ready without an APR artifact
- **Risk:** the agent skips APR entirely and substitutes prose for
  artifact-backed readiness evidence.
- **Mitigation:** AGENT-INSTR-01 §1 requires `scripts/run_agent_pr_precheck.py`
  to run for every repo-mutating slice and §5 lists "the APR artifact
  is missing" as an explicit fail-closed stop condition. The required
  evidence section in §4 has a dedicated `APR result: <artifact_ref>`
  line that cannot be filled without the on-disk artifact.
- **Test:** `test_agents_md_requires_apr_runner_invocation`,
  `test_claude_md_requires_apr_runner_invocation`.
- **Disposition:** resolved.

### MF-02 — Agent claims PR-ready without an M3L path measurement
- **Risk:** the agent reports a green APR result but never inspects
  whether it traversed AEX → PQX → EVL → TPA → CDE → SEL.
- **Mitigation:** §2 requires the M3L artifact path
  `outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json`
  and §5 lists "the M3L artifact is missing" as a stop condition. The
  evidence section in §4 lists every leg with a `present/partial/missing/unknown`
  status and an `artifact_ref or reason_code`.
- **Test:** `test_agents_md_requires_m3l_artifact_path`,
  `test_claude_md_requires_m3l_artifact_path`,
  `test_agents_md_evidence_section_lists_all_legs`.
- **Disposition:** resolved.

### MF-03 — Agent claims PR-update-ready without an APU artifact
- **Risk:** APU is the PR-update readiness observation surface; if the
  agent skips it, the PR-update claim is unsubstantiated.
- **Mitigation:** §3 requires the APU artifact path
  `outputs/agent_pr_update/agent_pr_update_ready_result.json` and §5
  lists "the APU artifact is missing" plus "APU readiness is `not_ready`"
  as stop conditions.
- **Test:** `test_agents_md_requires_apu_artifact_path`,
  `test_claude_md_requires_apu_artifact_path`.
- **Disposition:** resolved.

### MF-04 — A `present` leg is reported without artifact refs
- **Risk:** the agent could fill in `present` for any leg without a
  backing artifact.
- **Mitigation:** §1 requires every `pass` / present check entry to
  carry one or more `output_artifact_refs`. §4's evidence section
  template has `artifact_ref or reason_code` for each leg, and §5 lists
  "any `present` claim lacks an artifact ref" as a fail-closed stop
  condition.
- **Test:** `test_agents_md_evidence_section_lists_all_legs` and the
  upstream APR schema test
  `test_pass_without_output_artifact_refs_is_schema_invalid`.
- **Disposition:** resolved.

### MF-05 — A `missing` / `partial` / `unknown` leg is reported without reason codes
- **Risk:** the agent emits status without any explanatory reason code,
  hiding the underlying gap.
- **Mitigation:** §1 requires every non-pass check entry to carry one
  or more `reason_codes`. §5 lists "any `partial` / `missing` /
  `unknown` claim lacks a reason code" as a stop condition.
- **Test:** upstream APR schema test
  `test_non_pass_without_reason_codes_is_schema_invalid`.
- **Disposition:** resolved.

### MF-06 — `repo_mutating` is unknown but the agent treats it as ready
- **Risk:** APR returns `repo_mutating=null`; the agent could ignore
  the null and ship anyway.
- **Mitigation:** §5 lists "`repo_mutating` is unknown" as a stop
  condition. The instruction text matches the APR runner's own
  aggregator, which forces `overall_status=block` when
  `repo_mutating=None`.
- **Test:** `test_agents_md_repo_mutating_unknown_stops_pr_ready`,
  `test_claude_md_repo_mutating_unknown_stops_pr_ready`.
- **Disposition:** resolved.

### MF-07 — PR body prose substituted for artifact refs
- **Risk:** the agent writes "APR was run, all green" in the PR body
  instead of populating the structured evidence section.
- **Mitigation:** §4 fixes the exact evidence-section template the PR
  body must include and §5 says explicitly that "Prose substitution is
  not evidence." §1 ties every line to an APR/M3L/APU artifact ref or
  reason code.
- **Test:** `test_agents_md_no_artifact_no_proof_clause_present`,
  `test_claude_md_no_artifact_no_proof_clause_present`.
- **Disposition:** resolved.

### MF-08 — M3L `fell_out_at` is non-null but ignored
- **Risk:** M3L records that the agent fell out at, e.g., EVL, but the
  agent reports a green PR-ready anyway.
- **Mitigation:** §5 lists "M3L records `fell_out_at` other than `null`
  for a required leg" as a stop condition. §4 requires `fell_out_at`
  to appear in the evidence section.
- **Test:** `test_agents_md_evidence_section_lists_all_legs`,
  `test_claude_md_evidence_section_lists_all_legs`.
- **Disposition:** resolved.

### MF-09 — Instructions use reserved authority verbs in non-owner context
- **Risk:** the AGENT-INSTR-01 section in `AGENTS.md` or `CLAUDE.md`
  could drift into authority-claim language (e.g., "APR approves" or
  "M3L certifies") and quietly redefine ownership.
- **Mitigation:** the AGENT-INSTR-01 section uses observation-only
  vocabulary ("readiness observation", "compliance observation",
  "control input", "final gate signal", "finding", "artifact-backed
  evidence") and a §6 authority-boundary paragraph that re-pins
  canonical ownership to `docs/architecture/system_registry.md`. A
  test scans the AGENT-INSTR-01 section for reserved verbs.
- **Test:** `test_agents_md_avoids_reserved_authority_verbs_in_agent_instr_section`,
  `test_claude_md_avoids_reserved_authority_verbs_in_agent_instr_section`.
- **Disposition:** resolved.

### SF-01 — `should_fix`: extend AGENT-INSTR-01 to additional agent surfaces
- **Risk:** the repo may grow new agent-facing instruction files (e.g.,
  per-domain `AGENTS.md` files in subtrees) that bypass AGENT-INSTR-01.
- **Suggested next slice:** add a directory walker test that asserts
  every `AGENTS.md` and `CLAUDE.md` in the repo either inherits from
  the root rule or includes its own AGENT-INSTR-01 reference.

### OBS-01 — AGENT-INSTR-01 surface is instruction-only
- **Observation:** AGENT-INSTR-01 is a docs/instruction hardening
  slice. Runtime fail-closed behavior already lives in APR / M3L / APU
  / CLP. The instruction text does not introduce new runtime gates;
  it binds the agent's PR-ready handoff claim to those existing
  artifact-backed observations.

### OBS-02 — Reminder for downstream readers
- **Observation:** APR, M3L, and APU artifact-backed evidence is
  required for every AI repo-mutating slice before any PR-ready or
  PR-update-ready claim, per AGENT-INSTR-01 in the repo-root `AGENTS.md`
  and `CLAUDE.md`.
