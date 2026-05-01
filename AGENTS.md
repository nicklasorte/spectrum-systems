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

## AI Repo-Mutating Work — Required 3LS Evidence (AGENT-INSTR-01)

This rule applies to every Codex/Claude repo-mutating slice. It binds the
agent-facing instruction surface to the artifact-backed observation
systems that already exist in the repo. The agent must not claim
PR-ready or PR-update-ready without the artifacts named below.

APR, M3L, CLP, and APU are observation-only systems. APR emits pre-PR
readiness observations; M3L emits 3LS path measurement observations;
CLP emits pre-PR readiness observations; APU emits PR-update readiness
observations. Canonical authority remains with the owner systems
declared in `docs/architecture/system_registry.md`. The rule below
governs the agent's PR-ready handoff claim only — it neither redefines
ownership nor introduces a new gate.

### 1. Run APR before any PR-ready or PR-update claim

For any repo-mutating slice, run the APR runner and capture its
artifact before opening or updating a PR:

```
python scripts/run_agent_pr_precheck.py \
  --base-ref <base_ref> \
  --head-ref HEAD \
  --work-item-id <work_item_id> \
  --agent-type <codex|claude> \
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

Every final agent report or PR body for a repo-mutating slice must
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

The agent must stop and report `not_ready` /
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
substitution = not proven. The agent must not infer readiness from
silence.

### 6. Authority boundary

The rule above scopes the agent's PR-ready handoff claim only. APR,
M3L, CLP, and APU each surface observation-only PR-update or
measurement artifacts as listed above. They do not hold admission,
execution closure, eval evidence, policy/scope, continuation/closure,
or final-gate signal. Canonical ownership stays with the systems
declared in `docs/architecture/system_registry.md`.

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

## Terminology normalization

Use these terms consistently:

- **execution**
- **artifact**
- **failure**
- **retrieve**

## Roadmap authority

Only `docs/roadmaps/system_roadmap.md` is authoritative for implementation sequencing.
