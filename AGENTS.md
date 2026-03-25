# AGENTS.md

## Purpose
Durable operating instructions for all AI agents working in this repository.
`spectrum-systems` is the primary governance and implementation surface for the Spectrum Systems platform.
Read this file before making any changes.

---

## Ecosystem overview

| Repo | Role |
| --- | --- |
| `spectrum-systems` | Control plane — contracts, schemas, modules, governance, and prompt roadmap |
| `system-factory` | Scaffolding — templates pinned to czar-published standards |
| `spectrum-pipeline-engine` | Runtime orchestration — retained only if deployment boundary is justified |
| `spectrum-program-advisor` | Advisory outputs — retained only if product boundary is justified |
| Collapsed engine repos | Frozen design references — no new capability work |

**Module-first, repo-later.** New capability goes into a module inside `spectrum-systems`, not a new repository.

---

## Agent roles

| Agent | Responsibilities |
| --- | --- |
| Claude | Architecture reasoning, design critiques, review workflows, risk assessment |
| Codex | Repository modifications, documentation generation, schema creation, multi-file structured updates |
| Copilot | Code implementation inside downstream implementation repos |

---

## Prompt type system

Every Codex prompt must declare one primary type. Do not mix types in a single prompt.

| Type | When to use |
| --- | --- |
| `PLAN` | Produce a written execution plan before any multi-file or non-trivial change |
| `BUILD` | Implement a single well-scoped capability (one module, one schema, one workflow) |
| `WIRE` | Connect two existing artifacts (contract pin, pipeline link, interface binding) |
| `VALIDATE` | Run evaluation, schema checks, or contract conformance tests; emit an evidence bundle |
| `REVIEW` | Prepare review artifacts, action trackers, or Claude review packs |

**One prompt = one primary transformation.** If a task touches more than one type, split it.

---

## Operating rules

### Plan first
Any change touching more than two files or introducing a new module, contract, or schema **must** begin with a `PLAN` prompt.
The plan must be written to `PLANS.md` or a named file in `docs/review-actions/` before `BUILD` or `WIRE` begins.
See `PLANS.md` for the required plan template.

### Contract first
Define or update the JSON Schema in `contracts/schemas/` before implementing any module that produces or consumes that artifact type.
Do not implement a module against an undeclared or draft contract.

### Golden-path first validation
Before marking any `VALIDATE` step complete, run the golden-path fixture.
The golden path is the canonical happy-path input defined in `contracts/examples/` or `tests/fixtures/`.
A `VALIDATE` step that skips the golden path is not complete.

### Changed-scope verification
After every `BUILD` or `WIRE` step, verify that only the files declared in the plan were changed.
Run `.codex/skills/verify-changed-scope/run.sh` (or equivalent manual check) and record the result.
Undeclared file changes require explicit justification before commit.

### No unrelated refactors
Do not refactor, rename, or restructure code or documents outside the declared scope of the current prompt.
If a refactor is needed, open a separate `PLAN` → `BUILD` sequence.

### Checkpoint and Claude review expectations
Major checkpoints are defined in `docs/roadmaps/codex-prompt-roadmap.md`.
At each checkpoint, run `.codex/skills/checkpoint-packager/run.sh` and prepare a Claude review pack using `.codex/skills/claude-review-prep/run.sh`.
Claude review at a checkpoint blocks advancement to the next stage until findings are addressed or formally deferred.

---

## Safe behavior

- Always read `docs/vision.md` before modifying structure.
- Treat schemas in `contracts/schemas/` as authoritative. Downstream consumers import; they do not redefine.
- Do not generate automation code until the relevant workflow exists and lifecycle gates are satisfied.
- Prefer deterministic outputs. Every module must define inputs, outputs, and evaluation tests before shipping.
- Do not create new repositories for new capability. Use a module.

---

## Navigation

| File | Purpose |
| --- | --- |
| `CONTRACTS.md` | Contract authority and consumption rules |
| `SYSTEMS.md` | System catalog and module placement |
| `PLANS.md` | When and how to write execution plans |
| `docs/roadmaps/codex-prompt-roadmap.md` | H–AJ Codex-optimal prompt slice roadmap |
| `docs/architecture/module-pivot-roadmap.md` | Module-first architecture pivot and Level-16 plan |
| `docs/vision.md` | Core product vision — read before structural changes |
| `contracts/standards-manifest.json` | Canonical contract version pins |
| `.codex/skills/` | Reusable Codex skill workflows |

---

## Roadmap Execution Rule

- Only the ACTIVE roadmap may be used for implementation
- The ACTIVE roadmap is:
  docs/roadmaps/system_roadmap.md
- Non-authoritative roadmap files (including `docs/roadmaps/codex-prompt-roadmap.md`) provide context only and must not drive implementation execution.
- DEPRECATED roadmap execution paths must not be used for implementation.
