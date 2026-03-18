# Roadmap Inventory Review

**Review Date:** 2026-03-18
**Repository:** spectrum-systems
**Review Type:** REVIEW — Roadmap classification and single-source-of-truth identification
**Reviewer:** Copilot (Architecture Agent)
**Inputs Consulted:**
- All files matching "roadmap", "plan", "execution", "prompt", "tracker" in filename or content
- `AGENTS.md`, `CODEX.md`, `PLANS.md`
- `docs/roadmaps/codex-prompt-roadmap.md`
- `docs/architecture/module-pivot-roadmap.md`
- `docs/roadmaps/operational-ai-systems-roadmap.md`
- `docs/100-step-roadmap.md`
- `docs/roadmap.md`
- `docs/governance-enforcement-roadmap.md`
- `ecosystem/roadmap-tracker.json`
- `ecosystem/maturity-tracker.json`
- `docs/system-planning-framework.md`
- `docs/system-planning-steps.md`
- `docs/prompt-standard.md`
- `PLANS.md`
- `docs/reviews/2026-03-16-operational-ai-systems-roadmap-architecture-review.md`
- `docs/reviews/2026-03-16-operational-ai-systems-roadmap-review.md`
- `docs/review-actions/2026-03-16-roadmap-architecture-actions.md`
- `docs/review-actions/2026-03-16-roadmap-review-actions.md`
- `tests/test_roadmap_tracker.py`

---

## Scope

**In-bounds:** All files in the repository whose filename or content relates to roadmap, plan, execution, prompt, or tracker. Classification of each as ACTIVE, REFERENCE, or DEPRECATED. Identification of conflicting authorities. Recommendation of a single ACTIVE roadmap.

**Out-of-bounds:** Modifying any files; evaluating correctness of individual roadmap items; reviewing contracts or schemas not related to roadmaps.

---

## A. Executive Summary

The repository contains **seventeen roadmap-related artifacts** spanning execution drivers, strategic guidance, architecture pivots, governance enforcement plans, machine-readable trackers, planning frameworks, and review records. Of these, **two files simultaneously claim "Status: Active"** (`docs/roadmaps/codex-prompt-roadmap.md` and `docs/architecture/module-pivot-roadmap.md`), and one vestigial early draft (`docs/roadmap.md`) exists with no clear relationship to the current architecture. This creates an ambiguous execution authority and risks confusing Codex agents about which document drives current work.

**Assessment:** The conflict is resolvable without deleting anything. `docs/roadmaps/codex-prompt-roadmap.md` is the correct single ACTIVE execution driver — it is the most recent document (2026-03-18), explicitly marked Active, and already declares that it supersedes the Level-16 execution model in `module-pivot-roadmap.md`. `module-pivot-roadmap.md` should be reclassified as REFERENCE (architectural authority for module structure and Level-16 criteria, not for Codex prompt sequencing). `docs/roadmap.md` should be marked DEPRECATED (vestigial early draft, superseded by all subsequent roadmap artifacts).

---

## B. Roadmap Inventory

---

- **File:** `docs/roadmaps/codex-prompt-roadmap.md`
  - **Description:** Codex-optimal prompt slices H through AJ covering governance foundations, workflow modules, cross-source integration, reasoning outputs, packaging, hardening, and final proof. Every roadmap item expressed as three sub-slices (PLAN → BUILD/WIRE → VALIDATE/REVIEW) with explicit checkpoint gates.
  - **Purpose:** Execution — directly drives current Codex prompt sequencing.
  - **Usage:** Actively used; contains `Status: Active` and `Date: 2026-03-18`; referenced by `AGENTS.md` as the canonical roadmap and navigation target; declares it supersedes the Level-16 execution model in `module-pivot-roadmap.md`.
  - **Recommended Classification:** **ACTIVE**

---

- **File:** `docs/architecture/module-pivot-roadmap.md`
  - **Description:** Formalizes the architectural pivot from a multi-repository engine model to a module-first platform architecture. Defines the Level-16 roadmap, repository strategy (retained vs. collapsed repos), internal module tree, data strategy, evaluation framework, and Definition of Done criteria.
  - **Purpose:** Conceptual + partial execution — architectural authority for module structure, Level-16 criteria, and the Definition of Done. Its execution model (prompt sequencing) is explicitly superseded by `codex-prompt-roadmap.md`.
  - **Usage:** Marked `Status: Active` but its execution-model authority is transferred to `codex-prompt-roadmap.md` by explicit declaration in that document.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/100-step-roadmap.md`
  - **Description:** A 100-step execution map for the spectrum ecosystem, guiding architecture evolution toward Level 20 maturity. Each step specifies a title, target repo, primary purpose, primary risk, and guardrail. Reviewed by Claude on 2026-03-16.
  - **Purpose:** Historical execution — a comprehensive prior-generation execution plan organized around repo-centric steps across `spectrum-systems`, engine repos, and `spectrum-pipeline-engine`. Predates the module-first pivot.
  - **Usage:** Referenced by `tests/test_roadmap_tracker.py` (file-existence test); reviewed and archived; `ecosystem/roadmap-tracker.json` contains machine-readable entries keyed to its step numbers.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/roadmaps/operational-ai-systems-roadmap.md`
  - **Description:** Strategic description of operational AI systems across three layers (Layer 1: Operational Engines, Layer 2: Study-Scale Intelligence Systems, Layer 3: Ecosystem-Scale Intelligence Layer / Spectrum Intelligence Map). Each system described with purpose, inputs, outputs, and ecosystem placement.
  - **Purpose:** Conceptual — strategic guidance explicitly stated as non-binding ("does not create binding requirements unless a future standard, contract, or repository specification explicitly adopts part of it").
  - **Usage:** Reviewed by Claude on 2026-03-16; review actions tracked in `docs/review-actions/2026-03-16-roadmap-review-actions.md`; not referenced as a current execution driver.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/governance-enforcement-roadmap.md`
  - **Description:** Defines four phases of governance enforcement (declared identity, automated schema validation, CI-based conformance, ecosystem-level compatibility). Phase 1 is initiated as of 2026-03-16.
  - **Purpose:** Execution (governance track) — describes the active enforcement roadmap for governance declarations, but scoped to governance infrastructure rather than module development. Complements rather than competes with `codex-prompt-roadmap.md`.
  - **Usage:** Phase 1 is marked as initiated; references active governance artifacts (`contracts/governance-declaration.template.json`, `contracts/standards-manifest.json`). Not a Codex execution driver but an active governance status document.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/roadmap.md`
  - **Description:** A three-phase sketch (Phase 1: Foundations — schemas, comment resolution, transcript extraction; Phase 2: Analytical Systems; Phase 3: Institutional Systems). No dates, no step detail, no status field.
  - **Purpose:** Historical — an early conceptual draft that predates all subsequent planning work. Contains no information not covered with far more precision in later roadmap documents.
  - **Usage:** Not referenced by any other document, test, or governance artifact. Provides no unique information.
  - **Recommended Classification:** **DEPRECATED**

---

- **File:** `ecosystem/roadmap-tracker.json`
  - **Description:** Machine-readable JSON array of roadmap steps keyed to `docs/100-step-roadmap.md`. Each entry contains `step_number`, `title`, `repo`, `status`, `maturity_target`, `dependencies`, `primary_risk`, and `guardrail`.
  - **Purpose:** Supporting artifact — provides machine-readable state for the 100-step roadmap steps; validated by `tests/test_roadmap_tracker.py`.
  - **Usage:** Actively tested; validated against `ecosystem/roadmap-tracker.schema.json`; should be kept as a reference artifact aligned to the 100-step roadmap.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `ecosystem/roadmap-tracker.schema.json`
  - **Description:** JSON Schema for `ecosystem/roadmap-tracker.json`. Defines the required shape of roadmap tracker entries.
  - **Purpose:** Supporting artifact — schema governance for the roadmap tracker.
  - **Usage:** Used in `tests/test_roadmap_tracker.py` for validation.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `ecosystem/maturity-tracker.json`
  - **Description:** Machine-readable JSON array tracking current maturity level, next target, blocking gaps, and evidence per system in the ecosystem.
  - **Purpose:** Supporting artifact — operational maturity state tracker. Not a roadmap itself but reflects current progress against the maturity model.
  - **Usage:** Actively used; contains evidence and blocking gaps for each system.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `PLANS.md`
  - **Description:** Defines when a written execution plan is required and provides the plan template. References `docs/roadmaps/codex-prompt-roadmap.md` as the source for roadmap item labels. Tracks active plans.
  - **Purpose:** Governance process — plan lifecycle and template governance. Not a roadmap but a prerequisite governance artifact for executing the roadmap.
  - **Usage:** Actively referenced in `AGENTS.md` as a navigation target; required reading before any multi-file or non-trivial change.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/prompt-standard.md`
  - **Description:** Defines the required structure for all AI workflow prompts (role, context, task, constraints, verification, expected output schema) and guidance for structured outputs, deterministic parameters, and provenance fields.
  - **Purpose:** Governance process — prompt authoring standard. Orthogonal to roadmap content; defines how prompts are written, not what is on the roadmap.
  - **Usage:** Referenced by `CODEX.md` as an operational constraint.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/system-planning-framework.md`
  - **Description:** A 15-step framework summary for planning automation systems before implementation begins. Lists the 15 steps as a numbered checklist without elaboration.
  - **Purpose:** Conceptual — short-form planning checklist. Largely a duplicate of the detailed content in `docs/system-planning-steps.md`.
  - **Usage:** No active references to this specific file; content superseded by `docs/system-planning-steps.md`.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/system-planning-steps.md`
  - **Description:** Detailed elaboration of each system planning step (15 steps with definitions, examples, and guidance for spectrum automation systems).
  - **Purpose:** Conceptual — system design guidance for new automation systems. Predates the module-first architecture but remains valid as process guidance.
  - **Usage:** Not referenced by active execution documents but provides context for system design discipline.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/reviews/2026-03-16-operational-ai-systems-roadmap-architecture-review.md`
  - **Description:** Claude architecture review of `docs/100-step-roadmap.md` (mislabeled in the document as reviewing the operational-ai-systems roadmap; the document reviewed is the 100-step roadmap). Assesses architectural fit, layering integrity, data architecture risks, and build sequencing.
  - **Purpose:** Historical — review record; provides context for architectural decisions made in relation to the 100-step roadmap.
  - **Usage:** Review record; corresponding action tracker is `docs/review-actions/2026-03-16-roadmap-architecture-actions.md`.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/reviews/2026-03-16-operational-ai-systems-roadmap-review.md`
  - **Description:** Claude architecture review of `docs/roadmaps/operational-ai-systems-roadmap.md`. Assesses architectural fit, layering integrity, registry gaps, naming inconsistencies, and build sequencing flaws.
  - **Purpose:** Historical — review record for the operational AI systems roadmap.
  - **Usage:** Review record; corresponding action tracker is `docs/review-actions/2026-03-16-roadmap-review-actions.md`.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/review-actions/2026-03-16-roadmap-architecture-actions.md`
  - **Description:** Action tracker extracted from the 2026-03-16 architecture review. Contains critical, high-priority, medium-priority, and deferred items with owners, status, and blocking dependencies.
  - **Purpose:** Execution (open actions) — multiple open action items that are blocking or dependencies for current work.
  - **Usage:** Open action items (all marked Open); blocking items RM-002 and RM-004 are noted as blocking cross-engine artifact linking and knowledge schema work.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `docs/review-actions/2026-03-16-roadmap-review-actions.md`
  - **Description:** Action tracker extracted from the 2026-03-16 operational AI systems roadmap review. Contains critical, high-priority, medium-priority, and deferred items aligned to the operational AI systems roadmap.
  - **Purpose:** Execution (open actions) — open items stemming from the roadmap review.
  - **Usage:** Open action items; blocking items noted.
  - **Recommended Classification:** **REFERENCE**

---

- **File:** `tests/test_roadmap_tracker.py`
  - **Description:** Pytest suite that validates `ecosystem/roadmap-tracker.json` against its schema, checks step number uniqueness, and verifies that `README.md` references the roadmap.
  - **Purpose:** Supporting artifact — test coverage for tracker integrity. Not a roadmap.
  - **Usage:** Actively run in CI.
  - **Recommended Classification:** **REFERENCE**

---

## C. Conflicts

### Conflict 1: Dual "Active" status on two documents

Both `docs/roadmaps/codex-prompt-roadmap.md` and `docs/architecture/module-pivot-roadmap.md` carry `Status: Active`. A Codex agent reading `module-pivot-roadmap.md` in isolation could interpret the Level-16 roadmap table as the current execution guide, leading to incorrect prompt construction or duplicate work.

**Resolution:** `codex-prompt-roadmap.md` already declares that it supersedes the execution model in `module-pivot-roadmap.md`. `module-pivot-roadmap.md` should be updated to reflect REFERENCE status and should direct readers to `codex-prompt-roadmap.md` for prompt execution. Until that update is made, the dual-Active state is a latent confusion risk.

### Conflict 2: Three documents describing "what to build next"

`docs/100-step-roadmap.md`, `docs/roadmaps/codex-prompt-roadmap.md`, and `docs/architecture/module-pivot-roadmap.md` each describe a sequence of work items at different levels of granularity. An agent querying "what should be done next?" could receive conflicting answers from these three documents. The 100-step roadmap organizes around repo-centric steps; the codex-prompt-roadmap organizes around Codex-executable prompt slices; the module-pivot roadmap organizes around a Level-16 maturity target. Their sequencing is compatible but not identical, creating potential confusion about priority order.

**Resolution:** `codex-prompt-roadmap.md` is the authoritative source for next-action sequencing. The other two are context documents.

### Conflict 3: Vestigial `docs/roadmap.md` with no relationship to current architecture

`docs/roadmap.md` describes three phases (Foundations, Analytical Systems, Institutional Systems) that do not correspond to any naming convention, maturity level, or execution stage in the current architecture. A new contributor or agent reading this file first would form an incorrect mental model of the build sequence.

**Resolution:** Deprecate `docs/roadmap.md` and add a deprecation notice pointing to `docs/roadmaps/codex-prompt-roadmap.md`.

---

## D. Final Recommendation

### ACTIVE

`docs/roadmaps/codex-prompt-roadmap.md`

**Rationale:** Most recent document (2026-03-18). Explicitly marked Active. Contains Codex-executable prompt slices H through AJ with typed objectives (PLAN / BUILD / WIRE / VALIDATE / REVIEW), checkpoint gates, parallelization rules, and a checkpoint summary table. Explicitly supersedes the execution model of `module-pivot-roadmap.md`. Referenced in `AGENTS.md` as the canonical navigation target for the prompt roadmap. All Codex agents should treat this document as the sole current execution driver.

---

### REFERENCE

The following files are retained as supporting context, architectural authority, or historical record. They must not be treated as competing execution drivers.

| File | Retention Rationale |
| --- | --- |
| `docs/architecture/module-pivot-roadmap.md` | Authoritative source for module structure, Level-16 criteria, repository strategy, and Definition of Done. Strategic architecture, not a Codex execution driver. |
| `docs/100-step-roadmap.md` | Prior-generation 100-step execution plan; reviewed and archived; required by `tests/test_roadmap_tracker.py`. Valuable historical context. |
| `docs/roadmaps/operational-ai-systems-roadmap.md` | Strategic system description across three layers; explicitly non-binding; reviewed and archived. |
| `docs/governance-enforcement-roadmap.md` | Active governance enforcement phase tracker; orthogonal to prompt execution; Phase 1 is initiated. |
| `ecosystem/roadmap-tracker.json` | Machine-readable tracker for 100-step roadmap; validated by tests. |
| `ecosystem/roadmap-tracker.schema.json` | JSON Schema for roadmap tracker. |
| `ecosystem/maturity-tracker.json` | Operational maturity state per system. |
| `PLANS.md` | Plan governance template and lifecycle process; required reading before any BUILD/WIRE prompt. |
| `docs/prompt-standard.md` | Prompt authoring standard; orthogonal to roadmap content. |
| `docs/system-planning-framework.md` | Short-form planning checklist; useful context. |
| `docs/system-planning-steps.md` | Detailed system design guidance; predates module-first architecture but valid as process context. |
| `docs/reviews/2026-03-16-operational-ai-systems-roadmap-architecture-review.md` | Archived architecture review record. |
| `docs/reviews/2026-03-16-operational-ai-systems-roadmap-review.md` | Archived roadmap review record. |
| `docs/review-actions/2026-03-16-roadmap-architecture-actions.md` | Open action tracker with blocking items (RM-002, RM-004) that must be resolved before Layer 2 development. |
| `docs/review-actions/2026-03-16-roadmap-review-actions.md` | Open action tracker from roadmap review. |
| `tests/test_roadmap_tracker.py` | Test coverage for tracker schema and file existence. |

---

### DEPRECATED

| File | Deprecation Rationale |
| --- | --- |
| `docs/roadmap.md` | Vestigial early draft; three-phase sketch with no dates, no step detail, no alignment to current module-first architecture or H–AJ prompt sequence. Not referenced by any other document, test, or governance artifact. Superseded entirely by `docs/roadmaps/codex-prompt-roadmap.md`. |

---

## E. Required Actions

The following actions must be taken to resolve conflicts and formalize the single-ACTIVE state. See `docs/review-actions/2026-03-18-roadmap-inventory-actions.md` for the tracked action list.

| ID | Action | Priority |
| --- | --- | --- |
| RI-001 | Add deprecation notice to `docs/roadmap.md` pointing to `docs/roadmaps/codex-prompt-roadmap.md` | High |
| RI-002 | Update `Status:` field in `docs/architecture/module-pivot-roadmap.md` from `Active` to `Reference` and add a navigation note pointing to `docs/roadmaps/codex-prompt-roadmap.md` for Codex prompt sequencing | High |
| RI-003 | Add a "Single ACTIVE Roadmap" note to `AGENTS.md` or `CODEX.md` explicitly naming `docs/roadmaps/codex-prompt-roadmap.md` as the execution driver | Medium |
| RI-004 | Resolve open blocking actions RM-002 (Canonical ID Standard) and RM-004 (Canonical Knowledge Model) from `docs/review-actions/2026-03-16-roadmap-review-actions.md` before any Layer 2 module work begins | Medium |
