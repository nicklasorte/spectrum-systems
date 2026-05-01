# AGENTS.md

## Purpose

Durable operating instructions for agents working in `spectrum-systems`.

This repository is the governance and control-plane surface for a governed runtime.

## Canonical sources

All high-impact decisions must align to:

1. `README.md` (system identity and operating model)
1. `docs/architecture/system_registry.md` (canonical system roles and ownership)

If any instruction conflicts with these sources, treat it as a defect and correct the
conflicting surface.

## Agent roles

|Agent      |Authority                                                                                             |
|-----------|------------------------------------------------------------------------------------------------------|
|**Claude** |Architecture reasoning, risk assessment, review findings, and bounded implementation execution via PR.|
|**Codex**  |Repository execution and deterministic multi-file updates.                                            |
|**Copilot**|Downstream implementation repository coding.                                                          |

### Claude execution scope

Claude is authorized to perform implementation changes without requesting confirmation. All
changes must be delivered via Pull Request. The PR is the governed promotion mechanism.

**Pre-authorized actions — no confirmation needed:**

- Read any file in the repo
- Write files to a feature branch
- Run tests, linters, and build commands
- Commit and push to feature branches
- Open PRs with descriptions referencing the governed artifact or work item

**Halt and emit a finding instead of asking:**

- Any write directly to `main`
- Any action outside the declared scope of the current prompt
- Any action that would cross module boundaries (e.g. `control/*` writing `agent/*` artifacts)

Claude does not ask for permission within the pre-authorized surface. If scope is ambiguous,
halt and emit a finding — do not proceed on inference.

## Canonical runtime rules

1. **Artifact-first execution**
1. **Fail-closed behavior**
1. **Promotion requires certification**

These rules are non-negotiable across prompts, plans, and governance docs.

## Canonical system roles

Use role ownership exactly as defined in `docs/architecture/system_registry.md`.

Do not duplicate, subset, or redefine ownership sets in other governance documents.

## Prompt type system

Each prompt must declare exactly one primary type:

- `PLAN`
- `BUILD`
- `WIRE`
- `VALIDATE`
- `REVIEW`

## Operating rules

- **Plan first**: changes touching more than two files must start with a written plan in
  `PLANS.md` or `docs/review-actions/`.
- **No hidden behavior**: all execution rules must be explicit in governed markdown.
- **No deep reference chains**: keep required behavior understandable within one reference
  level.
- **No unrelated refactors**: keep changes in declared scope.
- **System introduction discipline**: before introducing or broadening any system owner,
  check `docs/architecture/system_registry.md`, avoid duplicate ownership claims, and
  include same-change canonical registration when a truly new system is required. System
  Registry Guard (SRG) enforcement in preflight/CI will fail closed on violations.
- **PR traceability**: every PR must reference the governed artifact, work item, or prompt
  type that authorized the change.

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

## Pre-PR Gate Evidence (CLP-02)

Before marking repo-mutating agent work PR-ready or updating an existing PR,
agents must run the core loop pre-PR gate or provide a valid
`core_loop_pre_pr_gate_result` artifact and a passing `agent_pr_ready_result`
guard artifact:

- `python scripts/run_core_loop_pre_pr_gate.py --work-item-id <ID> --agent-type claude|codex`
- `python scripts/check_agent_pr_ready.py --work-item-id <ID> --agent-type claude|codex`

CLP rules:

- repo-mutating slice with no CLP evidence → not PR-ready (fail closed).
- CLP `gate_status=block` → no PR update / no PR-ready handoff.
- CLP `gate_status=warn` → PR update permitted only when every warn reason
  code is listed in `docs/governance/core_loop_pre_pr_gate_policy.json` →
  `allowed_warn_reason_codes`.
- CLP `gate_status=pass` → PR update may proceed.

If CLP blocks, repair through the governed PRL/FRE/CDE/PQX flow or report
the CLP block. CLP itself never approves, certifies, promotes, admits, or
enforces — it only emits structured pre-PR evidence.

## Pre-PR Aggregate Evidence (APR-01)

CLP-01/CLP-02 are necessary but not sufficient. Before claiming PR-ready or
PR-update-ready on any repo-mutating slice, agents must also run the
aggregate agent PR precheck and produce a valid
`agent_pr_precheck_result` artifact:

- `python scripts/run_agent_pr_precheck.py --work-item-id <ID> --agent-type claude|codex`

APR composes the same per-gate scripts CI's `governed-contract-preflight`
job runs (authority-shape, authority-leak, system-registry, contract
compliance, contract preflight, generated-artifact freshness, selected
tests, CLP-01, CLP-02, APU) and emits a single readiness aggregate.

APR rules:

- repo-mutating slice with no `agent_pr_precheck_result` → not PR-ready
  (fail closed). PR body or commit prose is not a substitute.
- APR `overall_status=block` → no PR-ready / PR-update-ready handoff.
  Repair via the governed PRL/FRE/CDE/PQX flow or report the APR block.
- APR `overall_status=warn` → handoff permitted only when every warn
  reason code is policy-allowed under the upstream gate policies APR
  composes.
- APR `pr_ready_status=not_ready` or `pr_update_ready_status=not_ready` →
  fail closed; do not claim ready, regardless of overall status.
- APR `first_failed_check` and `first_missing_artifact` are the canonical
  pointers for what to repair. Cite them when reporting an APR block.

APR is observation-only. It surfaces pre-PR readiness inputs and
compliance observations only. Canonical authority remains with AEX
(admission), PQX (bounded execution closure), EVL (eval evidence), TPA
(policy/scope), CDE (continuation/closure), SEL (final gate signal),
LIN (lineage), REP (replay), and GOV per
`docs/architecture/system_registry.md`.

## PR-Update Readiness Guard (APU-3LS-01)

Before updating an existing PR with new repo-mutating commits, agents
must also produce a valid `agent_pr_update_ready_result` guard artifact:

- `python scripts/check_agent_pr_update_ready.py --work-item-id <ID> --agent-type claude|codex`

APU rules:

- repo-mutating PR update with no `agent_pr_update_ready_result` →
  not PR-update-ready (fail closed).
- APU `readiness_status=not_ready` → no PR update; repair the missing or
  failing CLP / AGL / CLP-02 inputs first.
- APU `readiness_status=human_review_required` → halt agent handoff and
  emit a finding instead of pushing.
- APU `readiness_status=ready` → PR update may proceed. The guard's
  `pr_evidence_section_markdown` is the canonical evidence summary to
  cite in the PR body.

APU is observation-only and is evaluated against
`docs/governance/agent_pr_update_policy.json`. Canonical authority for
the upstream signals it observes (CLP, AGL, CLP-02 / agent_pr_ready)
remains with the systems declared in `docs/architecture/system_registry.md`.

## Agent 3LS Path Measurement (M3L-02)

For every repo-mutating slice, agents must emit a measurement-only
`agent_3ls_path_measurement_record` so the loop is observable end to end:

- `python scripts/build_agent_3ls_path_measurement.py --work-item-id <ID> --agent-type claude|codex`

M3L answers, from existing APR / CLP / APU / AGL artifacts:

- did the agent traverse `AEX → PQX → EVL → TPA → CDE → SEL`?
- where did it fall out (`fell_out_at`)?
- what was the `first_missing_leg`?
- what was the `first_failed_check`?

M3L rules:

- repo-mutating slice with no `agent_3ls_path_measurement_record` →
  loop traversal is unobserved; do not claim PR-ready or PR-update-ready.
- M3L `loop_complete=false` → cite `fell_out_at`, `first_missing_leg`,
  and `first_failed_check` when reporting why the slice is not ready.
- M3L never recomputes upstream gates and never overrides APR / CLP /
  APU. If M3L disagrees with an upstream readiness status, the upstream
  artifact is canonical — repair the upstream input, do not re-emit M3L
  to mask it.

M3L is observation-only. Canonical authority remains with AEX, PQX, EVL,
TPA, CDE, SEL, LIN, REP, and GOV per
`docs/architecture/system_registry.md`. M3L emits no admission, execution,
eval, policy, control, or final-gate signal of its own.

## PR-Ready / PR-Update-Ready Claim Requirement

An agent may claim PR-ready or PR-update-ready only when, for the current
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

If any of the above is missing, blocked, or `not_ready`, the agent must
fail closed: do not claim PR-ready, do not push the PR-update, and
report the gap with the artifact reference and the specific
`first_missing_*` / `first_failed_*` field that drove the decision.

## Terminology normalization

Use these terms consistently:

- **execution**
- **artifact**
- **failure**
- **retrieve**

## Roadmap authority

Only `docs/roadmaps/system_roadmap.md` is authoritative for implementation sequencing.
