# 📘 REFERENCE

This document defines architectural direction and maturity targets (e.g., Level-16 system),
but is not used for day-to-day Codex execution.

Execution must follow the ACTIVE roadmap:
docs/roadmaps/codex-prompt-roadmap.md

---

# Module-Pivot Roadmap

**Status:** Reference
**Date:** 2026-03-17
**Author:** Architecture Working Group
**Scope:** Ecosystem-wide — governance, module structure, data strategy, Level-16 roadmap

---

## Purpose

This document formalizes the architectural pivot from a multi-repository engine model to a module-first platform architecture centered on `spectrum-systems`.

The prior approach — spinning up a dedicated repository per capability — produced useful design artifacts and reference implementations. It did not, however, produce a coherent system. Contracts diverged. Schemas were redefined locally. There was no shared state, no unified lifecycle, and no institutional memory. Each engine operated in isolation with its own conventions.

This roadmap supersedes that model.

The system is pivoting toward:

- **Ruthless golden paths.** One canonical way to do each thing. No parallel implementations of the same capability.
- **Stronger product boundaries.** Modules inside a platform, not repos that simulate products.
- **Centralized governance.** Contracts, schemas, and lifecycle gates live in `spectrum-systems` and are authoritative. Downstream consumers do not redefine them.
- **Module-first implementation.** New capability is built as a module inside `spectrum-systems`, not as a new repository.
- **Institutional memory.** The system captures decisions, outcomes, reuse patterns, and rationale — and makes them queryable.
- **Explainability and traceability.** Every output traces to its inputs, module, workflow, and human review checkpoint.

Placeholder engine repositories are treated as idea containers and design references. They are not long-term product boundaries by default. Any engine repo that is not justified by a runtime, product, or deployment boundary is a candidate for collapse into a module.

---

## Guiding Principles

**One product, many modules.**
`spectrum-systems` is the product. Modules are the units of capability. Repositories are a deployment and governance mechanism, not an architecture primitive.

**Golden paths over flexibility.**
Every workflow has a canonical path. Deviation from the golden path requires explicit justification. The system does not offer multiple ways to do the same thing unless there is a documented reason.

**Authoritative shared truth.**
Contracts, schemas, and lifecycle definitions live in `spectrum-systems`. No module, engine, or downstream system redefines them. Consumers import; they do not override.

**Control plane first.**
Governance, lifecycle, and contract enforcement are built before domain modules. You cannot build reliable domain logic on an uncontrolled foundation.

**Institutional memory as a first-class feature.**
The system records what happened, why, and with what outcome. This is not a logging concern. It is an architectural requirement. Memory informs decisions; decisions are traceable to their inputs.

**Explainability and traceability over convenience.**
An output that cannot be traced to its source, module, inputs, and review history is not a valid output. Convenience shortcuts that break traceability are not acceptable.

---

## Repository Strategy

### Retained Repositories

| Repository | Retention Rationale |
| --- | --- |
| `spectrum-systems` | Control plane, governance authority, module host — the core product |
| `system-factory` | Scaffolding and template management — retained as a distinct tool |
| `spectrum-pipeline-engine` | Retained only if runtime separation is justified by deployment or operational requirements |
| `spectrum-program-advisor` | Retained only if product or application separation is justified by distinct user-facing boundaries |

### Collapsed Repositories → Modules

The following repositories are collapsed into modules inside `spectrum-systems`. Each is preserved as a design artifact, reference implementation, and module specification source. No existing design work is discarded.

| Repository | Target Module | Preservation Role |
| --- | --- | --- |
| `meeting-minutes-engine` | `workflow_modules/meeting_intelligence` | Design artifact, reference implementation, module spec source |
| `comment-resolution-engine` | `workflow_modules/comment_resolution` | Design artifact, reference implementation, module spec source |
| `working-paper-review-engine` | `workflow_modules/working_paper_review` | Design artifact, reference implementation, module spec source |
| `docx-comment-injection-engine` | `workflow_modules/comment_injection` | Design artifact, reference implementation, module spec source |
| `agency-question-radar` | `workflow_modules/agency_question_radar` | Design artifact, reference implementation, module spec source |
| `knowledge-capture-engine` | `domain_modules/knowledge_capture` | Design artifact, reference implementation, module spec source |
| `allocation-intelligence-engine` | `domain_modules/allocation_intelligence` | Design artifact, reference implementation, module spec source |
| `interference-analysis-assistant` | `domain_modules/interference_assistant` | Design artifact, reference implementation, module spec source |
| `institutional-memory-engine` | `domain_modules/institutional_memory` | Design artifact, reference implementation, module spec source |
| `review-prediction-engine` | `domain_modules/review_prediction` | Design artifact, reference implementation, module spec source |

Engine repositories are not deleted. They remain as frozen references. New capability development does not go into engine repos.

---

## Internal Module Architecture

The following tree defines the recommended module structure inside `spectrum-systems`. This is the target state, not the current state. Modules are added incrementally following the Level-16 roadmap sequence.

```
spectrum_systems/
  control_plane/
    governance/
    contracts/
    schemas/
    policy/
    lifecycle/
    review_system/
    work_items/
    observability/
    evaluation/

  workflow_modules/
    meeting_intelligence/
    comment_resolution/
    working_paper_review/
    comment_injection/
    study_planning/
    agency_question_radar/

  domain_modules/
    allocation_intelligence/
    interference_assistant/
    knowledge_capture/
    institutional_memory/
    regulatory_reasoning/
    review_prediction/

  orchestration/
    pipeline/
    artifact_bus/
    state_machine/

  shared/
    artifact_models/
    ids/
    lineage/
    provenance/
    readiness/
    adapters/
```

The `control_plane` is built first. Workflow and domain modules are built on top of a functioning control plane. The `shared` layer is populated incrementally as canonical models are established.

---

## Enforcement Artifacts

The module-first architecture is enforced through canonical artifacts that accompany this roadmap.

| Artifact | Path | Purpose |
| --- | --- | --- |
| Module manifest schema | `schemas/module-manifest.schema.json` | JSON Schema for all module manifests |
| Module manifest example | `docs/examples/module-manifest.example.json` | Annotated example manifest |
| Module manifests | `docs/module-manifests/` | Per-module boundary contracts |
| Shared-layer authority | `docs/architecture/shared-authority.md` | Binding rules for the shared layer |
| Validation script | `scripts/validate_module_architecture.py` | Deterministic repo-local enforcement |
| CI gate | `.github/workflows/artifact-boundary.yml` | Runs validator on every PR and push |

---

## Explicit Control Mechanisms

The system enforces behavior through four categories of control.

### Guardrails

Structural rules that prevent invalid states.

- Schema validation on all artifact ingestion paths
- Contract enforcement on all cross-module and cross-repo artifact exchanges
- Required evaluation → work item linkage before lifecycle advancement
- Forbidden lifecycle transitions enforced by the state machine

### Golden Paths

Canonical workflows that all modules follow unless deviation is explicitly documented.

- Canonical evaluation flow: artifact ingested → evaluation run → result recorded → work item linked
- Canonical review flow: artifact submitted → Claude review checkpoint → findings recorded → action tracker updated
- Canonical study planning flow: spectrum study initiated → readiness assessed → plan generated → guidance emitted
- Canonical comment resolution flow: comment extracted → context resolved → disposition applied → matrix updated

### Reconciliation Loops

Ongoing processes that detect and resolve drift between actual and expected states.

- Evaluation → remediation loop: failed evaluation triggers remediation work item; loop does not close until work item is resolved
- Review → work item loop: review findings create work items; loop does not close until findings are addressed or explicitly deferred
- Lifecycle state reconciliation: actual artifact state is periodically reconciled against recorded lifecycle state
- Artifact completeness enforcement: incomplete artifacts trigger blocking signals on downstream consumers

### Human Checkpoints

Required human review gates in the workflow.

- Claude review checkpoints at defined stages (see Claude Review Protocol section)
- Upload audit checkpoints: artifacts uploaded to external systems require audit log entries
- Level-16 validation review: domain-critical outputs require structured human validation before release
- Policy-critical review gates: outputs that inform regulatory or policy decisions require explicit approval

---

## Data Collection Strategy

Documents alone are insufficient. The system must collect structured data as a first-class concern. Static documents capture intent; structured data captures what the system actually does, what it produces, and what happens as a result.

The system must collect data across six groups.

### A. Control-Plane Data

| Data Type | Description |
| --- | --- |
| System IDs | Canonical identifiers for all modules and systems |
| Lifecycle states | Current and historical state for every artifact under lifecycle management |
| Contract and schema versions | Active versions and change history |
| CI results | Test run outcomes, validation results, enforcement pass/fail records |
| Work-item status | Open, in-progress, and resolved work items with links to triggering events |

### B. Artifact Lineage Data

| Data Type | Description |
| --- | --- |
| Artifact IDs | Stable identifiers for all governed artifacts |
| Source relationships | What artifact or event produced each artifact |
| Producing module | Which module generated the artifact |
| Timestamps | Creation, modification, and review timestamps |
| Downstream usage | Which modules consumed each artifact and when |

### C. Evaluation Data

| Data Type | Description |
| --- | --- |
| Evaluation results | Pass, fail, partial, and conditional outcomes |
| Readiness states | Readiness classification per artifact and per evaluation run |
| Rationale | Why a given evaluation produced its result |
| Linked work items | Work items created or resolved by evaluation results |
| Test fixtures | Input/output pairs used for evaluation, stored for reproducibility |

### D. Workflow Data

| Data Type | Description |
| --- | --- |
| Meetings, transcripts, minutes | Raw and processed meeting content |
| Comments and resolutions | Extracted comments, assigned context, and resolution dispositions |
| Working papers | Versioned working paper artifacts and their review history |
| Review artifacts | Claude review outputs, structured findings, and action trackers |
| Revision history | Version-to-version delta records for governed artifacts |

### E. Domain Data

| Data Type | Description |
| --- | --- |
| Allocation tables | Frequency allocation data by band, service, and jurisdiction |
| Band metadata | Technical parameters, notes, and regulatory references per band |
| Services and constraints | Defined services, their technical constraints, and regulatory basis |
| Interference study data | Study inputs, methodology records, and computed results |
| Agency questions | Questions received, context, processing history, and responses |

### F. Outcome Data

| Data Type | Description |
| --- | --- |
| Accepted and rejected recommendations | Which system outputs were adopted and which were rejected, with rationale |
| Delays and causes | Process delays linked to root causes |
| Reuse patterns | Which artifacts, templates, or outputs were reused across studies or processes |
| Recurring issues | Issue patterns that appear repeatedly across workflows |
| Effectiveness of outputs | Assessment of whether system outputs produced the intended effect |

Outcome data is the hardest category to collect and the most valuable. Without it, the system cannot learn. Collecting it requires explicit instrumentation at human handoff points — upload checkpoints, review outcomes, and human decision records.

---

## Level-16 Roadmap

Prompt identifiers (K2, M–W) correspond to the sequential prompt numbering defined in `docs/100-step-roadmap.md`. Each prompt letter maps to a discrete implementation increment.

| Order | Prompt | Capability | Module Target | Level |
| --- | --- | --- | --- | --- |
| 1 | K2 | Control Loop Hardening | `control_plane` | L11 |
| 2 | M | Meeting Intelligence | `workflow_modules` | L12 |
| 3 | N | Comment Resolution | `workflow_modules` | L12 |
| 4 | O | Working Paper Review | `workflow_modules` | L12 |
| 5 | P | Comment Injection | `workflow_modules` | L13 |
| 6 | Q | Artifact Bus | `orchestration` | L14 |
| 7 | R | Lifecycle State Machine | `orchestration` | L14 |
| 8 | S | Study Planning | `workflow_modules` | L15 |
| 9 | T | Agency Question Radar | `workflow_modules` | L15 |
| 10 | U | Knowledge Capture | `domain_modules` | L15 |
| 11 | V | Allocation Intelligence | `domain_modules` | L16 |
| 12 | W | Interference Assistant | `domain_modules` | L16 |
| 13 | Audit | Level-16 Validation | system-wide | L16 |

Levels are cumulative. A module at L14 implies all L11–L13 prerequisites are satisfied. The control plane (K2) is a prerequisite for all subsequent work.

---

## Parallel Execution Rules

Some modules can be developed in parallel. Others must be serialized because they touch shared truth layers.

### Safe Parallel Groups

- **M + N + O** — Meeting Intelligence (M), Comment Resolution (N), and Working Paper Review (O) operate on distinct artifact types and have no shared implementation dependencies at L12.
- **S + T + U** — Study Planning (S), Agency Question Radar (T), and Knowledge Capture (U) operate across distinct domain areas at L15.
- **V + W** — Allocation Intelligence (V) and Interference Assistant (W) are both domain modules at L16 with no direct dependency on each other.

### Serialized Work

The following work must be serialized regardless of level:

- Schema changes — schemas are shared truth; parallel changes produce conflicts
- Contract changes — contract updates require coordinated version bumps across consumers
- Lifecycle changes — lifecycle state definitions must be consistent across the entire system at any point in time
- Review artifact structure — structural changes to review artifacts affect all modules that produce or consume them

**Rule:** Parallelize across layers, not within shared truth layers.

---

## Upload Checkpoints

| Stage | Upload Target |
| --- | --- |
| After K2 | `spectrum-systems` (pipeline upload optional) |
| After P | Workflow modules (internal validation) |
| After Q + R | `spectrum-systems` + `spectrum-pipeline-engine` + `spectrum-program-advisor` |
| After V + W | Full ecosystem |

Uploads at each checkpoint are audit events. Each upload must produce a corresponding audit log entry. Uploads are not silent pushes — they are state transitions in the artifact lifecycle.

---

## Claude Review Protocol

Claude review checkpoints are defined by stage and focus area. Each review produces structured findings using the canonical review format and emits an action tracker stub.

| Stage | Repository Focus | Review Focus |
| --- | --- | --- |
| After K2 | `spectrum-systems` | Control loop integrity — are guardrails, golden paths, and reconciliation loops structurally sound? |
| After P | `spectrum-systems` | Workflow correctness and roundtrip fidelity — do workflow modules produce and consume artifacts correctly end-to-end? |
| After Q + R | `spectrum-systems` + pipeline | Orchestration coherence — does the artifact bus and state machine correctly sequence module outputs? |
| After Level-16 Audit | system-wide | Domain intelligence validity — are domain module outputs structurally sound, traceable, and usable for their intended purpose? |

Reviews are not optional. Each checkpoint review blocks advancement to the next stage until findings are addressed or formally deferred with documented rationale.

---

## Migration Plan

1. **Freeze creation of new engine repositories.** No new capability work begins in a new repo. All new work goes into `spectrum-systems` modules.
2. **Extract designs from existing engine repositories.** Read each engine repo and produce a module specification document for its target module location.
3. **Map each repository to a module.** Use the collapsed repository table in the Repository Strategy section. Confirm the target module path for each repo before extraction begins.
4. **Implement modules inside `spectrum-systems`.** Build modules in roadmap order, starting with the control plane.
5. **Deprecate engine repositories while retaining them as references.** Add a deprecation notice to each engine repo README pointing to the corresponding module. Do not delete or archive the repos — they are design references.
6. **Align all contracts and schemas centrally.** Any contract or schema defined locally in an engine repo is migrated to `spectrum-systems` or formally deprecated. No engine repo defines its own authoritative schemas after migration.
7. **Enforce control mechanisms.** Once the control plane is operational, enforce guardrails and lifecycle gates. Gaps discovered during enforcement are tracked as work items, not bypassed.

---

## Definition of Done for Level 16

Level 16 is reached only when all of the following conditions are satisfied:

- The control loop is enforced end-to-end: guardrails, golden paths, reconciliation loops, and human checkpoints are all operational.
- Workflows operate cleanly across modules: meeting intelligence, comment resolution, working paper review, comment injection, study planning, and agency question radar all complete their canonical flows without manual intervention outside designated human checkpoints.
- The artifact lifecycle is unified: all governed artifacts carry system IDs, lifecycle state, provenance, and lineage records. No artifact exits the system without a complete provenance chain.
- Institutional memory is active and queryable: decisions, outcomes, reuse patterns, and rationale are captured in structured form and can be retrieved in response to queries.
- The system generates meaningful study guidance: study planning outputs are grounded in domain data, traceable to their inputs, and usable by engineers without manual reformatting.
- Domain reasoning is structured and usable: allocation intelligence and interference assistant outputs are structured artifacts, not free-text narratives. They carry provenance, link to source data, and support downstream consumption.

These conditions are binary. Either they are met or they are not. Partial credit does not constitute Level 16.

---

## Closing Principle

Do not build more surface area.

Build coherence, traceability, memory, and reasoning.

This is not a collection of tools. This is a system that understands its domain.
