# System Architecture Philosophy

This document states the architectural principles that govern how Spectrum Systems is designed, extended, and evaluated. It is intended as a reference for design decisions, not as a high-level aspirational statement. Principles without teeth are noise.

---

## What This System Actually Is

Spectrum Systems is a governed operational AI ecosystem. It transforms expert engineering workflows — meetings, reviews, analysis, coordination — from manual, undocumented, irreproducible processes into governed, traceable, AI-assisted operations.

The system is **not** a general-purpose AI platform. It is not attempting to solve every problem. It is building narrow, reliable, governed loops one at a time, starting with the workflows where the toil is highest, the structure is clearest, and the failure modes are best understood.

The current MVP is the meeting-minutes workflow: Observe (ingest transcript and context) → Interpret (extract structured facts, actions, decisions, risks) → Recommend (generate governed follow-ups, ownership suggestions, operational signals). Everything else is subsequent.

---

## Architectural Principles

### 1. Product Boundaries Are Enforced, Not Suggested

Every system in the ecosystem has a defined boundary: what it accepts as inputs, what it produces as outputs, and what it does not touch. Boundaries are encoded in contracts (`contracts/schemas/`), enforced by CI, and documented in system interface specs (`systems/<system>/interface.md`).

Crossing a boundary without a contract change is a governance violation. Boundaries that are unclear are clarified before implementation proceeds — ambiguity in boundaries produces ungoverned coupling.

### 2. Golden Paths Are the Default

A golden path is the canonical, governed implementation pattern for a given workflow category. It defines the standard sequence of steps, the expected artifact types, and the validation checkpoints. New work follows the golden path by default.

For each workflow category (ingestion, extraction, transformation, recommendation, review), there is a canonical path. New work follows the golden path unless there is a documented reason to diverge. Divergence requires an ADR.

Golden paths exist to prevent the accumulation of inconsistent, one-off implementations that each require separate maintenance. Consistency reduces cognitive overhead and makes the ecosystem legible to new contributors and AI agents.

### 3. Explicit Contracts Over Implicit Conventions

Every interface between systems is governed by an explicit artifact contract. A contract specifies:
- The schema of the input and output artifacts
- The required and optional fields
- The versioning rules that apply when the schema changes
- The validation that must pass before the artifact is accepted

Implicit conventions — "everyone knows the output looks like this" — are not acceptable. If it is not in a contract, it is not governed.

### 4. Governance-First Execution

Governance is not applied retrospectively to working systems. It is the prerequisite for implementation.

Before a system is built:
- The problem is defined
- The input and output contracts exist
- The evaluation plan exists
- The failure modes are documented

Systems that exist without these are in technical governance debt. That debt is paid before new capabilities are added — not after.

### 5. Institutional Memory Is a Design Goal, Not a Byproduct

The system is designed to preserve decisions, rationale, and context as first-class artifacts. This is not documentation for its own sake — it is the foundation for:
- Reliable AI-assisted operation (models need structured context to produce useful outputs)
- Reproducible analysis (future runs need to reconstruct what earlier runs assumed)
- Governance accountability (decisions must remain auditable over time)

Institutional memory that exists only in human memory or informal documents is a reliability risk. The architecture treats it as a gap to close.

### 6. Explainability Is Mandatory

An AI-generated artifact must be explainable in terms of what it contains and why. This applies to extractions (traceable to source material), recommendations (basis in stated evidence), and governance flags (specific rule violated, specific location).

Opaque outputs are not acceptable. If a reviewer cannot interrogate an artifact to understand how it was produced, it cannot be trusted. Explainability is a design constraint for prompts and system interfaces, not a feature to be added later.

### 7. Ruthless Reduction of Ambiguity

Ambiguity in schemas, contracts, prompts, and interfaces is eliminated at the point of design. Every field has a type, a purpose, and a validation rule. Every prompt has a clear task and a defined output structure. Every system boundary has a contract.

The cost of ambiguity is paid slowly and repeatedly, in misrouted artifacts, silent failures, and inconsistent outputs. The cost of clarity is paid once, at design time. The architecture consistently prefers the upfront cost.

---

## The Architecture Favors Narrow, Reliable Loops Before Broad Platform Sprawl

The ecosystem does not attempt to build a general platform and then populate it with use cases. It builds narrow, governed loops first — and platformizes only the patterns that have proven reliable and repeatable in real operation.

The pattern:

1. Identify a high-toil, high-value workflow
2. Define its inputs, outputs, and failure modes
3. Implement a governed, narrow loop
4. Prove reliability through evaluation evidence
5. Extract common patterns into shared infrastructure only when two or more workflows demonstrate the same need

Platform abstractions built ahead of proven use cases are speculative infrastructure. Speculative infrastructure accrues maintenance burden without earning its keep.

The meeting-minutes workflow is the first narrow loop. It is not a demonstration of the platform — it is the proving ground for the architecture. If the principles above cannot make a meeting-minutes loop reliable and governable, they cannot make anything else reliable either.

---

## The Meeting Minutes MVP as Proving Ground

The meeting-minutes workflow (SYS-006) is the first concrete test of every principle in this document:

| Principle | Test |
|---|---|
| Product boundaries | Engine operates only within the `meeting_minutes` contract; does not reach into other systems |
| Golden path | Follows the canonical ingestion → extraction → recommendation → review → record path |
| Explicit contracts | `meeting_minutes` contract governs all inputs and outputs |
| Governance-first | Schema, contract, and evaluation plan existed before engine implementation |
| Institutional memory | Minutes artifacts preserve decisions, actions, and rationale in structured, queryable form |
| Explainability | Extracted fields are traceable to source transcript passages; reviewers can interrogate the artifact |
| Narrow loop first | Meeting minutes is one loop, done reliably, before expanding to adjacent workflows |

If the MVP meets these standards in practice, the architecture is working. If it does not, the architecture has a gap — and that gap takes priority over expansion.

---

## What This Means for New Work

Before adding a new system or capability to the ecosystem:

1. Is the bottleneck it addresses documented in `docs/bottleneck-map.md` or `SYSTEMS.md`?
2. Is the input contract defined in `contracts/schemas/`?
3. Is the output contract defined and versioned?
4. Is the evaluation plan in `eval/`?
5. Is the failure mode documented in the system interface or `docs/system-failure-modes.md`?
6. Does the new work follow an existing golden path, or does it require an ADR to diverge?

If the answer to any of these is "not yet," the prerequisite work comes first. Building systems without these foundations produces systems that cannot be governed, evaluated, or trusted — regardless of how useful the AI output appears in informal testing.
