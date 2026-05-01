# CLAUDE.md

## System Identity

Spectrum Systems is a governed execution runtime for artifact-first, policy-controlled AI work.

It is not a chat system, agent framework, or prompt wrapper. Every input, decision, execution
step, and output is a versioned, schema-bound artifact. There are no shadow paths.

## AEX Admission Rule

All repo-mutating agent work must begin with an AEX-style admission step before implementation.

Before editing any files, the agent must identify:

- request type and intended outcome
- exact changed surfaces (files, workflows, schemas, tests, docs)
- authority-shape risks across canonical-owner boundaries (per `docs/architecture/system_registry.md`)
- required tests and eval coverage
- required schema or artifact updates
- required governance mappings, where they exist (e.g. test-gating, selection, and ownership mappings declared in `docs/architecture/system_registry.md` or `docs/governance/`)
- required replay and observability updates
- whether the scope is too large and must be split

If the work touches any governed surface, including:

- `.github/workflows/`
- `scripts/`
- `contracts/`
- `spectrum_systems/`
- `tests/`
- `docs/governance/`
- system registry or architecture artifacts

then the agent must either:

1. Update all corresponding mappings, tests, schemas, and governance artifacts in the same change
1. OR stop and report the missing mapping before proceeding

### Authority Boundary

AEX is an admission boundary only.

It may produce:

- admission evidence
- policy observations
- normalized execution requests
- downstream input signals
- trace / provenance / lineage

It must NOT claim or implement:

- enforcement authority
- certification authority
- promotion authority
- final control decisions

All such authority remains with the canonical owner declared in `docs/architecture/system_registry.md`. AEX emits admission evidence and downstream support inputs only; it does not redefine any 3-letter system's ownership.

### Fail-Closed Principle

If required signals, mappings, or coverage are missing, the agent must fail closed:

- do not proceed with implementation
- do not create partial or unmapped changes
- do not assume downstream systems will "handle it"

Instead:

- report the gap
- propose the minimal required fix
- or split the work into smaller, admissible slices

### Intent

This rule ensures:

- no orphaned workflows, scripts, or schemas
- no missing test coverage for governed surfaces
- no authority-shape violations
- no hidden logic outside governed artifacts
- no CI drift caused by agent-generated changes

All changes must be admissible, traceable, testable, and governed before execution.

## Operational Loop

```
input → RIL (structure) → CDE (decide) → TLC (orchestrate)
     → PQX (execute) → eval gates → control decision
     → SEL (enforce) → certification → promotion
```

Non-determinism is logged. Promotion only follows a `control_decision` with `action = allow`.
Subsystem ownership is canonical in `docs/architecture/system_registry.md`.

## Module Boundaries

Modules are hard-separated. No module may cross-write another module’s artifact types.

|Module         |Authority                                    |
|---------------|---------------------------------------------|
|`agent/*`      |Produces output artifacts                    |
|`judgment/*`   |Interprets evidence, writes `judgment_record`|
|`evals/*`      |Assesses artifacts, writes eval artifacts    |
|`control/*`    |Emits `allow / warn / freeze / block`        |
|`enforcement/*`|Executes enforcement actions                 |

Decision, orchestration, execution, and enforcement assignments are canonical in `docs/architecture/system_registry.md`. Instruction docs must not redefine those assignments here.

## Hard Rules

- All work runs through the governed runtime. No exceptions.
- No repo mutation outside PQX-equivalent execution.
- No decision logic outside CDE.
- No orchestration outside TLC.
- No promotion without a passing `done_certification_record`.
- Fail-closed always. Missing artifact = halt. Missing eval gate = block.
- `branch_update_allowed = (terminal_state == "ready_for_merge")`. No exceptions.

## Promotion Rule

`branch_update_allowed = (terminal_state == "ready_for_merge")`

No exceptions. All changes ship via Pull Request. PRs are the promotion mechanism.

## Failure Handling

```
failure → evidence artifact → FRE diagnosis → CDE decision
       → bounded repair (TLC) → retest → eval gate
```

Every failure produces a `failure_classification` artifact. Silent failures are prohibited.

## Learning Loop

```
failure → classified → eval candidate → governed adoption → roadmap signal
```

Failures feed the versioned eval dataset. Policy and prompt template updates require governed
adoption — no ad hoc fixes.

## Execution Permissions

Claude operates in autonomous execution mode within this repo. The governance boundary is the
PR gate, not the interactive prompt.

**Pre-authorized actions — no confirmation needed:**

- Read any file in the repo
- Write files to a feature branch
- Run tests, linters, and build commands (`python -m pytest -q`, `npm test`, `npm run lint`)
- Commit and push to feature branches
- Open PRs with descriptions referencing the governed artifact or work item

**Not permitted — halt and emit a finding instead of asking:**

- Direct writes to `main`
- Any action outside this surface

If an action falls outside the pre-authorized surface, halt and emit a finding artifact.
Do not ask interactively. Do not proceed on ambiguous scope.

## Claude’s Role

Claude performs reasoning, review, and implementation tasks within the governed runtime.

**Claude is permitted to:**

- Produce explicit findings, risk calls, and boundary checks as artifacts.
- Recommend remediation paths with evidence.
- Execute bounded, deterministic implementation changes via PR (PQX-equivalent).
- Interpret governed artifacts and declared ownership.
- Escalate contradictions to canonical references.

**Claude is forbidden to:**

- Bypass CDE, TLC, PQX, or SEL.
- Make implicit decisions or infer missing approval signals.
- Execute direct repo mutations outside the PR flow.
- Redefine ownership or extend scope beyond the requested artifact.
- Reproduce decision logic, orchestration, or enforcement inline.

## Implementation Discipline

- All changes ship via Pull Request. No direct file edits to `main`.
- Scope is bounded to the requested artifact. Do not expand.
- Contradictions escalate — they are not resolved by inference.
- Rules are explicit. Descriptive drift is a defect.
- Every PR must be traceable to a governed artifact or declared work item.
- Keep scope bounded; remove contradictions and duplicate instruction surfaces.

## Review Behavior

State evidence, decision boundary, and blocking condition explicitly.

Do not interpret silence as approval. Do not proceed when required artifacts are missing.
Do not infer schema alignment — validate it.

## Interpretation Boundaries

- Interpret artifacts; do not redefine ownership.
- Recommend remediation; do not execute remediation outside the governed flow.
- Escalate contradictions to canonical references.

## Prohibited Behavior

- No direct file edits outside governed flow.
- No implicit decisions.
- No hidden execution paths.
- No bypass of SEL / CDE / TLC.
- No interactive permission prompts — halt and emit a finding instead.

## AI Repo-Mutating Work — Required 3LS Evidence (AGENT-INSTR-01)

This rule applies to every Claude repo-mutating slice. It binds the
agent-facing instruction surface to the artifact-backed observation
systems that already exist in the repo. Claude must not claim PR-ready
or PR-update-ready without the artifacts named below.

APR, M3L, CLP, and APU are observation-only systems. APR emits pre-PR
readiness observations; M3L emits 3LS path measurement observations;
CLP emits pre-PR readiness observations; APU emits PR-update readiness
observations. Canonical ownership remains with the systems declared in
`docs/architecture/system_registry.md`. The rule below governs the
agent's PR-ready handoff claim only — it neither redefines ownership
nor introduces a new gate.

### 1. Run APR before any PR-ready or PR-update claim

For any repo-mutating slice, run the APR runner and capture its
artifact before opening or updating a PR:

```
python scripts/run_agent_pr_precheck.py \
  --base-ref <base_ref> \
  --head-ref HEAD \
  --work-item-id <work_item_id> \
  --agent-type claude \
  --repo-mutating true \
  --output outputs/agent_pr_precheck/agent_pr_precheck_result.json
```

Required APR result conditions:

- `overall_status` must be `pass`, or a `warn` whose reason codes are
  all listed in the active warn-reason-codes policy file referenced by
  the APR / CLP runners.
- `pr_ready_status` must be `ready`.
- `pr_update_ready_status` must be `ready`.
- Every `pass` / present check entry must carry one or more
  `output_artifact_refs`.
- Every `missing` / `partial` / `unknown` / non-pass check entry must
  carry one or more `reason_codes`.

### 2. Inspect the M3L 3LS path measurement

The same invocation also writes an `agent_3ls_path_measurement_record`
artifact at:

```
outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json
```

Required M3L conditions:

- AEX, PQX, EVL, TPA, CDE, and SEL legs must each be recorded with a
  status.
- A `present` leg must list at least one `artifact_refs` entry.
- A `partial` / `missing` / `unknown` leg must list at least one
  `reason_codes` entry.
- `first_missing_leg`, `first_failed_check`, `fell_out_at`, and
  `loop_complete` must be recorded.

### 3. Inspect the APU PR-update readiness artifact

```
outputs/agent_pr_update/agent_pr_update_ready_result.json
```

Required APU conditions:

- The PR-update readiness must be `ready` before claiming
  PR-update-ready.
- A `not_ready`, `missing`, `unknown`, or `human_review_required`
  readiness observation stops the PR-ready claim.

### 4. Required PR-ready evidence section

Every final Claude report or PR body for a repo-mutating slice must
include this 3LS evidence section, populated from the artifacts above:

```
3LS Agent Path Evidence:
- APR result: <artifact_ref>
- M3L path measurement: <artifact_ref>
- APU readiness: <artifact_ref>
- AEX: present/partial/missing/unknown — artifact_ref or reason_code
- PQX: present/partial/missing/unknown — artifact_ref or reason_code
- EVL: present/partial/missing/unknown — artifact_ref or reason_code
- TPA: present/partial/missing/unknown — artifact_ref or reason_code
- CDE: present/partial/missing/unknown — artifact_ref or reason_code
- SEL: present/partial/missing/unknown — artifact_ref or reason_code
- first_missing_leg: <value>
- first_failed_check: <value>
- fell_out_at: <value>
- loop_complete: <value>
- pr_ready_status: <value>
- pr_update_ready_status: <value>
```

Prose substitution is not evidence. Every line must reference an
artifact ref or a reason code as recorded by APR / M3L / APU.

### 5. Stop conditions — fail closed

Claude must stop and report `not_ready` /
`human_review_required` if any of the following hold:

- the APR artifact is missing
- the M3L artifact is missing
- the APU artifact is missing
- `repo_mutating` is unknown
- any `present` claim lacks an artifact ref
- any `partial` / `missing` / `unknown` claim lacks a reason code
- APR `overall_status` is a non-pass blocking observation
- APU readiness is `not_ready`
- M3L records `fell_out_at` other than `null` for a required leg, unless
  the active warn-reason-codes policy explicitly permits that fallout
  reason

No artifact = not proven. Missing reason code = not proven. Prose
substitution = not proven. Claude must not infer readiness from silence.

### 6. Authority boundary

The rule above scopes Claude's PR-ready handoff claim only. APR, M3L,
CLP, and APU each surface observation-only PR-update or measurement
artifacts as listed above. They do not hold admission, execution
closure, eval evidence, policy/scope, continuation/closure, or
final-gate signal. Canonical ownership stays with the systems declared
in `docs/architecture/system_registry.md`.

## Pre-PR Gate Evidence (CLP-02)

Before marking repo-mutating work PR-ready or updating an existing PR, run
or provide:

- `python scripts/run_core_loop_pre_pr_gate.py --work-item-id <ID> --agent-type claude`
- `python scripts/check_agent_pr_ready.py --work-item-id <ID> --agent-type claude`

Rules:

- Repo-mutating slice with no `core_loop_pre_pr_gate_result` is not PR-ready.
- CLP `gate_status=block` blocks PR-ready handoff. Repair via PRL/FRE/CDE/PQX
  or report the CLP block.
- CLP `gate_status=warn` permits PR-ready only if every warn reason code is
  in `docs/governance/core_loop_pre_pr_gate_policy.json` →
  `allowed_warn_reason_codes`.
- CLP supplies observation-only pre-PR evidence; canonical ownership stays
  with the systems declared in `docs/architecture/system_registry.md`.

## References

- `README.md`
- `docs/architecture/system_registry.md`
- `docs/architecture/clp_02_pr_ready_admission.md`
