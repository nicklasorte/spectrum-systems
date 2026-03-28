# PQX-CLT-023 — Parallel PQX Rollback and Containment Policy (2-Slice Governed Mode)

- **Date Activated:** 2026-03-28
- **Status:** **ACTIVE**
- **Scope:** **Exactly 2-slice parallel PQX runs**
- **Policy Type:** Governance-only; no runtime, test, certification, CLI, or CI behavior changes

## 1) Purpose

Define a bounded, operator-usable rollback and containment model for partial failures in 2-slice parallel PQX execution.

This policy exists to ensure concurrency does not create:

1. uncontrolled propagation of damage,
2. ambiguous ownership/attribution of failures,
3. unsafe continuation after unresolved uncertainty.

## 2) Failure and Containment Taxonomy

All detected run anomalies must be classified into one and only one primary failure type.

### 2.1 Slice-local failure
A failure is `slice_local_failure` when all of the following are true:

1. the failing behavior is isolated to one slice (A or B),
2. no evidence shows behavioral impact on the other slice,
3. attribution to the affected slice is clear.

Examples:
- Slice A validation fails before any merge; Slice B validations remain green.
- Slice B artifact quality gate fails with no observed drift in Slice A outputs.

### 2.2 Cross-slice interference
A failure is `cross_slice_interference` when either is true:

1. a change from one slice alters behavior, assumptions, or validation outcomes of the other slice, or
2. merge sequencing (A→B or B→A) introduces behavioral change not present in independent slice validation.

Examples:
- Slice A merges cleanly, then Slice B validation regresses only after A merge.
- Slice B merge changes an output consumed by Slice A documentation or review interpretation.

### 2.3 Ambiguous failure attribution
A failure is `ambiguous_failure` when attribution cannot be made with clear evidence.

A case is ambiguous when any of the following occur:

1. affected slice cannot be conclusively identified,
2. merge-order effects are plausible but unproven,
3. validation evidence is incomplete, contradictory, or missing,
4. operators cannot distinguish local failure from interference.

**Fail-closed requirement:** unclear attribution must be classified as `ambiguous_failure`.

## 3) Containment States (Bounded State Set)

Operators must use only the states below; no inferred or informal state labels are allowed.

1. `slice_local_failure`
2. `cross_slice_interference`
3. `ambiguous_failure`
4. `recovered`
5. `unrecovered`

### 3.1 State semantics

- `slice_local_failure`: localized failure confirmed; rollback may be slice-targeted.
- `cross_slice_interference`: inter-slice impact confirmed; trial path must be contained before continuation.
- `ambiguous_failure`: attribution unclear; parallel execution continuation is prohibited.
- `recovered`: required rollback + validation evidence proves stable restoration.
- `unrecovered`: restoration is not proven; this state persists until evidence is complete.

## 4) Rollback Decision Rules (Fail-Closed)

Rollback decisions must follow explicit rules below.

### Rule R1 — Localized pre-merge failure
If Slice A (or B) fails before merge and the other slice is unaffected:

1. classify as `slice_local_failure`,
2. rollback only the failing slice path,
3. continue only after unaffected slice evidence is reconfirmed.

### Rule R2 — Localized post-merge failure without spillover
If one slice fails post-merge and evidence confirms no impact to the other slice:

1. classify as `slice_local_failure`,
2. rollback the failing slice merge path,
3. revalidate unaffected slice against current baseline.

### Rule R3 — Confirmed inter-slice impact
If Slice A merge causes Slice B behavioral change (or vice versa):

1. classify as `cross_slice_interference`,
2. contain the trial immediately (no additional parallel merges/actions),
3. rollback merge path(s) required to remove interfering state,
4. re-run validations needed to establish a clean baseline.

### Rule R4 — Unclear attribution
If attribution is unclear at any decision point:

1. classify as `ambiguous_failure`,
2. stop parallel execution immediately,
3. deny continued parallel execution for the run,
4. require serial fallback workflow before further progression.

### Rule R5 — Recovery proof requirement
If rollback is performed but recovery evidence is incomplete:

1. containment status must remain `unrecovered`,
2. operators must not declare `recovered`,
3. no “probably recovered” or equivalent soft status is allowed.

## 5) Serial Fallback Requirement

Serial fallback is mandatory when either condition holds:

1. failure classification is `ambiguous_failure`, or
2. `cross_slice_interference` cannot be cleanly remediated with evidence-backed rollback.

Serial fallback means remaining work proceeds using governed serial PQX flow until a new governed parallel trial authorizes re-entry.

## 6) Evidence Requirements for Rollback and Recovery

Every containment/rollback decision must include all required evidence below:

1. **Affected slice(s):** A, B, or both.
2. **Baseline commit:** common commit used to launch both slices.
3. **Merge order:** `A→B` or `B→A`.
4. **Validation state:** before-failure and post-rollback validation outcomes.
5. **Attribution clarity:** `clear` or `unclear` with rationale.

### 6.1 Evidence completeness gate

Missing any required evidence item means:

1. recovery cannot be declared,
2. state remains `unrecovered`,
3. final disposition is fail-closed.

## 7) Operator Execution Standard

For every rollback/containment event in a 2-slice run, operators must produce a completed record using:

- `docs/review-actions/parallel_pqx_rollback_template.md`

An event is governance-incomplete unless all template fields are completed with explicit evidence.

## 8) Non-expansion Boundary

This policy:

1. applies only to 2-slice governed parallel PQX,
2. defines documentation and decision discipline only,
3. introduces no runtime automation, no test mutation, and no CLI/CI/certification logic changes.
