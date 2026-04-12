# Spectrum Systems

Spectrum Systems is a governed execution runtime and control-plane repository.

It defines how governed execution is planned, routed, enforced, evaluated, repaired, and promoted. It does **not** serve as a generic chat wrapper and does **not** host production business pipelines. The durable value here is control: contracts, artifacts, rules, and evidence that make execution predictable and auditable.

## Overview

This repository is the governance surface for a bounded runtime:

- It defines canonical artifacts, schemas, prompts, and enforcement rules.
- It defines which subsystem owns each responsibility.
- It ensures promotion decisions are evidence-based and fail closed when evidence is missing.

Downstream implementations can change over time. The control model and governed artifacts are the stable layer.

## Core Principle

Spectrum Systems operates as a governed sequence:

**input → structure → decision → orchestration → execution → repair → enforcement → certification → promotion**

In practice, this means:

1. Inputs are captured as explicit artifacts.
2. Artifacts are structured into deterministic system-readable forms.
3. Decisions are made from governed evidence, not implicit agent behavior.
4. Orchestration routes work to the correct owner system.
5. Execution runs in bounded scopes.
6. Failures trigger diagnosis and bounded repair planning.
7. Enforcement applies hard gates and fail-closed blocking.
8. Certification validates required evidence.
9. Promotion occurs only when certification conditions are met.

## System Components

Canonical ownership is defined in `docs/architecture/system_registry.md`.

| System | Role in the runtime | Owns | Must not do |
| --- | --- | --- | --- |
| **RIL** (Review Integration Layer) | Interprets review outputs into deterministic integration artifacts | review interpretation and projection | enforce policy, execute work, make closure decisions |
| **CDE** (Closure Decision Engine) | Issues authoritative closure-state decisions | closure decisions and bounded next-step classification | execute work, enforce side effects, generate repairs |
| **TLC** (Top Level Conductor) | Orchestrates invocation order and routing across systems | orchestration and subsystem routing | execute work internals, replace CDE or FRE authority |
| **PQX** (Prompt Queue Execution) | Executes bounded authorized work slices | execution and execution state transitions | adjudicate policy, generate repairs, issue closure decisions |
| **FRE** (Failure Recovery Engine) | Diagnoses failures and emits repair plans | failure diagnosis and repair planning | execute repairs directly, enforce policy, issue closure decisions |
| **SEL** (System Enforcement Layer) | Applies hard gates and fail-closed controls | enforcement and promotion guarding | reinterpret review semantics, generate repairs, orchestrate routing |
| **PRG** (Program Governance) | Governs objectives, roadmap alignment, and program drift | program governance and roadmap alignment | execute runtime work, enforce runtime blocks, reinterpret review packets |

## Execution Model

The runtime is designed to be:

- **Artifact-first**: important state transitions are represented as governed artifacts.
- **Deterministic**: the same valid inputs should produce the same governed outcomes.
- **Fail-closed**: when required evidence is missing or invalid, the system blocks rather than guessing.
- **Traceable**: decisions and outcomes map back to explicit records.

No hidden execution paths are permitted.

## Promotion Rules

Promotion is gated by governed evidence.

- `ready_for_merge` is a gate outcome, not a default.
- Promotion requires certification evidence to be present and valid.
- Repair completion alone does not grant promotion authority.
- Closure and promotion decisions are separate from execution and repair generation.

## Failure Handling

Failures are handled as a bounded loop:

1. Capture failure evidence.
2. Diagnose the failure class.
3. Generate a bounded repair candidate.
4. Re-run governed checks/tests.
5. Re-evaluate closure and promotion gates.

If evidence remains insufficient, the system stays blocked.

## Learning Loop

Failure handling also feeds system learning:

1. Failure patterns are captured as structured artifacts.
2. Candidate evaluation improvements are proposed.
3. Improvements are adopted through governed review and evidence.
4. Accepted outcomes become roadmap and governance signals.

This loop improves the runtime without bypassing enforcement.

## Roadmap and Input Origins

Roadmap and execution inputs come from governed sources, including:

- design and architecture reviews
- source documents and contracts
- operator commands and run artifacts
- structured evaluation outputs
- program governance signals

Roadmap sequencing authority lives in `docs/roadmaps/system_roadmap.md`.

## Design Constraints

The runtime enforces hard constraints:

1. **No hidden execution**: behavior must be explicit in governed artifacts/docs.
2. **No promotion without certification**: evidence is mandatory.
3. **No duplicate responsibilities**: each responsibility has one canonical owner.
4. **Bounded execution only**: work is scoped, routed, and controlled.

## Prompt Contract Constraint

Governed prompts must declare exactly one primary prompt type:

- `PLAN`
- `BUILD`
- `WIRE`
- `VALIDATE`
- `REVIEW`

Prompts that omit this declaration or declare multiple primary types are non-compliant and must be corrected before promotion.

## What This Enables

Spectrum Systems enables:

- consistent execution behavior across model/provider changes
- auditable decision paths for reviews and promotions
- safe failure recovery without authority leakage
- clear subsystem boundaries that reduce architectural drift

## Current State

Current architecture centers on a governed runtime with explicit role ownership for **RIL, CDE, TLC, PQX, FRE, SEL, and PRG**, with control enforced through artifacts, schemas, and validation surfaces in this repository.

## How to Use

1. Start from canonical architecture ownership in `docs/architecture/system_registry.md`.
2. Use governed contracts and schemas from `contracts/` and `schemas/`.
3. Keep prompts and workflow rules explicit under `prompts/` and `docs/`.
4. Run validation checks before proposing promotion-relevant changes.
5. Treat this repo as control-plane governance; keep operational runtime code in implementation repositories.

## Related and Historical Documents

- Current and historical system maturity references: `docs/system-maturity-model.md`.
- Historical maturity guidance references: `docs/level-0-to-20-playbook.md` and `docs/review-maturity-rubric.md`.
- Study-loop context and prior operating flow framing: `docs/spectrum-study-operating-model.md`.
- Historical long-range planning reference: `docs/100-step-roadmap.md` (100-step roadmap).

These links are retained for compatibility and historical context. Active runtime guidance remains this README plus the canonical ownership registry in `docs/architecture/system_registry.md`.

## Philosophy

The system, not the model, controls execution.

Models can be replaced. Governance cannot be implicit.

Durable reliability comes from explicit artifacts, bounded execution, fail-closed enforcement, and evidence-based promotion.
