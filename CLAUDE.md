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

## Pre-PR Aggregate Evidence (APR-01)

CLP-01/CLP-02 are necessary but not sufficient. Before claiming PR-ready
or PR-update-ready on any repo-mutating slice, also run or provide:

- `python scripts/run_agent_pr_precheck.py --work-item-id <ID> --agent-type claude`

APR composes the same per-gate scripts CI's `governed-contract-preflight`
job runs and emits a single `agent_pr_precheck_result` aggregate.

Rules:

- Repo-mutating slice with no `agent_pr_precheck_result` is not PR-ready.
  PR body or commit prose is not a substitute.
- APR `overall_status=block` blocks PR-ready / PR-update-ready handoff.
  Repair via PRL/FRE/CDE/PQX or report the APR block.
- APR `overall_status=warn` permits handoff only when every warn reason
  code is policy-allowed under the upstream gate policies APR composes.
- APR `pr_ready_status=not_ready` or `pr_update_ready_status=not_ready`
  blocks the corresponding handoff regardless of overall status.
- Cite APR `first_failed_check` and `first_missing_artifact` when
  reporting an APR block.

APR is observation-only. Canonical authority remains with AEX, PQX, EVL,
TPA, CDE, SEL, LIN, REP, and GOV per
`docs/architecture/system_registry.md`.

## PR-Update Readiness Guard (APU-3LS-01)

Before updating an existing PR with new repo-mutating commits, also run
or provide:

- `python scripts/check_agent_pr_update_ready.py --work-item-id <ID> --agent-type claude`

Rules:

- Repo-mutating PR update with no `agent_pr_update_ready_result` is not
  PR-update-ready.
- APU `readiness_status=not_ready` blocks the PR update; repair the
  missing or failing CLP / AGL / CLP-02 inputs first.
- APU `readiness_status=human_review_required` halts agent handoff —
  emit a finding instead of pushing.
- APU `readiness_status=ready` permits the PR update. Use the guard's
  `pr_evidence_section_markdown` as the canonical PR-body evidence
  summary.

APU is observation-only and evaluated against
`docs/governance/agent_pr_update_policy.json`. Canonical ownership of
upstream signals remains with the systems declared in
`docs/architecture/system_registry.md`.

## Agent 3LS Path Measurement (M3L-02)

For every repo-mutating slice, also emit a measurement-only
`agent_3ls_path_measurement_record`:

- `python scripts/build_agent_3ls_path_measurement.py --work-item-id <ID> --agent-type claude`

Rules:

- Repo-mutating slice with no `agent_3ls_path_measurement_record` leaves
  loop traversal unobserved; do not claim PR-ready or PR-update-ready.
- M3L `loop_complete=false` requires citing `fell_out_at`,
  `first_missing_leg`, and `first_failed_check` when reporting why the
  slice is not ready.
- M3L never recomputes upstream gates and never overrides APR / CLP /
  APU. If M3L disagrees with an upstream readiness status, the upstream
  artifact is canonical — repair the upstream input, do not re-emit M3L
  to mask it.

M3L is observation-only. Canonical authority remains with AEX, PQX, EVL,
TPA, CDE, SEL, LIN, REP, and GOV per
`docs/architecture/system_registry.md`.

## PR-Ready / PR-Update-Ready Claim Requirement

Claude may claim PR-ready or PR-update-ready only when, for the current
repo-mutating slice, all of the following are true:

1. A valid `core_loop_pre_pr_gate_result` exists (CLP-01) and a passing
   `agent_pr_ready_result` exists (CLP-02).
1. A valid `agent_pr_precheck_result` exists (APR-01) with
   `pr_ready_status=ready` (and `pr_update_ready_status=ready` for PR
   updates), and `overall_status` is `pass` or `warn` with all warn
   reason codes policy-allowed.
1. For PR updates, a valid `agent_pr_update_ready_result` exists
   (APU-3LS-01) with `readiness_status=ready`.
1. A valid `agent_3ls_path_measurement_record` exists (M3L-02) with
   `loop_complete=true`.

If any of the above is missing, blocked, or `not_ready`, fail closed:
do not claim PR-ready, do not push the PR-update, and report the gap
with the artifact reference and the specific `first_missing_*` /
`first_failed_*` field that drove the decision.

## References

- `README.md`
- `docs/architecture/system_registry.md`
- `docs/architecture/clp_02_pr_ready_admission.md`
