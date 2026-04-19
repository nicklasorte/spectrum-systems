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

## Terminology normalization

Use these terms consistently:

- **execution**
- **artifact**
- **failure**
- **retrieve**

## Roadmap authority

Only `docs/roadmaps/system_roadmap.md` is authoritative for implementation sequencing.
