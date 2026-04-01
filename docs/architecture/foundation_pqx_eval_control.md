# Foundation Architecture — PQX Eval Control

## Canonical Intent

The foundation document defines the minimum viable system:

PQX → output_artifact → eval_result/eval_summary → control_decision → enforcement_action → replay/trace

Roadmap generation must:
- measure repo reality against this
- detect gaps
- prioritize missing foundation seams
- block expansion until those seams are hardened

## Canonical Authority Order (Mandatory)

This exact order is required and must be enforced consistently across strategy, roadmap generation prompts, roadmap authority notes, and roadmap outputs:

1. `docs/architecture/strategy-control.md`
2. `docs/architecture/foundation_pqx_eval_control.md`
3. current repository state
4. `docs/roadmaps/system_roadmap.md`
5. source design documents / architecture artifacts

## Foundation Layers (Required)

The following layers are required and must be evaluated as a connected, non-bypassable chain:

1. PQX execution
2. output_artifact production and persistence
3. eval system (`eval_result` / `eval_summary`)
4. control logic (`control_decision`)
5. enforcement (`enforcement_action`)
6. replay integrity
7. trace completeness
8. golden path buildability

## Foundation Gap Classification (Mandatory)

Roadmap generation must classify each required foundation layer as one of:

- `present_and_governed`
- `present_but_partial`
- `present_but_bypassable`
- `missing`
- `ambiguous`

This classification must be applied to:
- schemas
- PQX execution
- eval system
- control logic
- enforcement
- replay
- tracing
- golden path

Treat the following as hardening priorities:
- `present_but_bypassable`
- `missing`
- `ambiguous`

## No False Foundation Completion (Mandatory)

Foundation is NOT complete if only:
- documented
- stubbed
- schema-only
- partially wired
- not enforced by control
- bypassable

A layer is complete ONLY if:
- implemented
- wired into execution
- validated by eval
- consumed by control
- non-bypassable

## Hard Gate Rule

No roadmap may advance broader capability if required foundation layers are missing, partial, ambiguous, or bypassable.

Expansion of agent behavior, workflows, or artifact breadth is blocked until foundation hardening resolves these conditions.

## Foundation vs Roadmap Conflict Rule

If foundation and roadmap disagree:

DO NOT:
- rewrite architecture
- silently reconcile

INSTEAD:
- record mismatch as foundation gap
- prioritize closing that gap

## Drift Signal

A critical drift signal exists when repository state diverges from the required chain:

PQX → output_artifact → eval_result/eval_summary → control_decision → enforcement_action → replay/trace

Any such divergence must trigger hardening-first roadmap sequencing.
