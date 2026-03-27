# PQX-CLT-011 — Controlled Parallel PQX Trial Plan (2-Slice)

- **Date:** 2026-03-27
- **Owner:** PQX Governance (TBD assignee)
- **Status:** EXECUTED (Controlled 2-slice trial)
- **Type:** Governance experiment protocol (not runtime implementation)

## Objective

Run one controlled experiment proving that **exactly two** PQX roadmap slices can execute in parallel without:

- cross-slice interference,
- ambiguous promotion state,
- hidden coupling,
- or action-tracker ambiguity.

## Why this is ready now

The promotion certification gate has completed verification and adversarial hardening in prior review artifacts, enabling a bounded parallelism trial under explicit governance controls.

## Scope boundary (hard)

This artifact defines a **first-trial protocol only**:

- ✅ Controlled 2-slice experiment.
- ❌ Not authorization for general parallel PQX execution.
- ❌ No runtime, certification logic, schema, or CI/CLI behavior changes.

## Eligibility rules for the first parallel pair

Both selected slices MUST be non-overlapping on all of the following:

- runtime files,
- shared test files,
- shared schemas/contracts,
- `contracts/standards-manifest.json` and other central registry files,
- the same review/action artifacts.

Allowed overlap policy:

- **Preferred:** none.
- **Permitted exception:** docs-only overlap where files are distinct (no shared file edits).

Rejected pair policy:

- Reject any pair where both slices touch control-loop policy files.
- Reject any pair where both slices touch certification-gate files.

## First trial-pair selection rubric

Select two slices using all criteria below:

- choose slices from different surfaces,
- one slice may be docs/review/reporting-oriented,
- one slice may be isolated runtime/test work in a separate module,
- both slices must be independently mergeable,
- both slices must be independently reversible.

If no established candidate pair exists at run time, keep selection generic and apply this rubric before branch creation.

## Execution protocol (operator checklist)

1. **Pair declaration**
   - Record Slice A and Slice B in the action tracker with owners and branches.
2. **Branch isolation**
   - Create independent branches from the same baseline commit.
   - Enforce no cherry-picking between the two branches.
3. **Independent implementation**
   - Implement Slice A and Slice B separately.
   - Keep each slice strictly within its declared file scope.
4. **Independent validation**
   - Run each slice's required checks independently.
   - Record evidence per slice in separate sections/artifacts.
5. **Cross-diff inspection before merge**
   - Compare both diffs and explicitly confirm:
     - no file overlap,
     - no semantic overlap,
     - no conflicting promotion-state assumptions,
     - no action-tracker ambiguity.
6. **Merge order rule**
   - Merge the lower-risk slice first (typically docs/governance-only), then merge the second slice.
   - Re-check merge-base assumptions after first merge and before second merge.
7. **Post-merge replay / targeted regression check**
   - Run targeted post-merge validation focused on promotion/certification control path and slice interfaces.
   - Record pass/fail and attribution clarity.

## Success criteria

The trial is successful only if all are true:

- both slices pass independently,
- no merge conflict or semantic conflict,
- post-merge validation passes,
- no regression in promotion/certification control path.

## Immediate abort criteria

Abort the trial immediately if any occur:

- overlapping runtime files are discovered,
- shared schema/manifest drift appears,
- one slice changes control semantics relied on by the other,
- post-merge validation yields ambiguous/blocking state not attributable to one slice.

## Required post-trial closure output

Publish a short closure artifact that states:

- what ran,
- whether isolation held,
- what failed or passed,
- final decision: **approved**, **conditionally approved**, or **denied** for broader 2-slice PQX usage.

## Executed trial pair (PQX-CLT-012)

- **Slice A:** PQX-CLT-012A — Trial-plan governance execution record update (`docs/reviews/2026-03-27-parallel-pqx-trial-plan.md`).
- **Slice B:** PQX-CLT-012B — Trial action-tracker execution and closure record (`docs/review-actions/2026-03-27-parallel-pqx-trial-actions.md`).
- **Baseline commit:** `1aa1ff8991234b7320102563029ea8794c00c528`
- **Branch A:** `pqx-clt-012-slice-a-plan-governance`
- **Branch B:** `pqx-clt-012-slice-b-action-tracker`

This pair satisfies the protocol's non-overlap constraints because each slice edits a distinct governance document and does not touch runtime modules, contracts/schemas, or certification/control-loop logic.

## Discipline constraints

- No claims that broad parallel execution is ready.
- No runtime behavior claims beyond prior established review evidence.
- Treat this as a constrained governance experiment protocol only.
