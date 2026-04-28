# PQX-CLT-016 — Parallel PQX Execution Policy (2-Slice Governed Mode)

- **Date Activated:** 2026-03-28
- **Authority Basis:** PQX-CLT-015 approved trial outcome (`docs/reviews/2026-03-27-parallel-pqx-trial-closure.md`)
- **Status:** **ACTIVE**
- **Scope:** **2-slice parallel PQX only**

## 1) Purpose

This policy operationalizes the approved parallel PQX trial into a governed, repository-native execution rule set.

It exists to:

1. enable safe execution of **exactly two** PQX slices in parallel,
2. preserve deterministic governance outcomes under concurrency,
3. keep promotion/certification control semantics unchanged from serial execution.

This policy does **not** authorize generalized concurrency beyond two slices.

## 2) Allowed and Disallowed Slice Classes

### Allowed for parallel execution

A two-slice parallel run is allowed only when both slices are in one of the classes below and satisfy all hard constraints in Section 3.

1. **Docs-only slices**
   - Reviews, action trackers, governance artifacts, reliability documentation, and similar documentation-only outputs.
2. **Isolated runtime/test slices**
   - Each slice must be isolated to distinct modules/files.
   - Slices must not share schemas/contracts.
   - Slices must not touch certification or control-loop governance surfaces.

### Disallowed for parallel execution

Parallel execution is disallowed when either slice modifies any of the following:

1. certification gate surfaces,
2. enforcement bridge surfaces,
3. control-loop policy surfaces,
4. shared schemas/contracts,
5. `contracts/standards-manifest.json`,
6. shared test files.

## 3) Hard Constraints (Must All Hold)

A 2-slice run is valid only if all constraints below are satisfied:

1. **No file overlap** between Slice A and Slice B.
2. **No schema/contract overlap** between slices.
3. **No shared test files** between slices.
4. **No control-loop or certification overlap** between slices.
5. **Explicit cross-diff inspection is required** before merge.

If any constraint fails, the run is invalid and must be aborted.

## 4) Execution Protocol (Compressed from PQX-CLT-011)

All 2-slice parallel runs must follow this protocol:

1. **Branch isolation**
   - Create Slice A and Slice B branches from the same baseline commit.
   - No cherry-picking between slice branches.
2. **Independent validation**
   - Validate each slice independently against its declared checks.
   - Record separate evidence for each slice.
3. **Cross-diff inspection**
   - Inspect both diffs together and confirm all Section 3 constraints.
4. **Merge order**
   - Merge lower-risk slice first (typically docs/governance), then merge second slice.
   - Reconfirm assumptions after first merge and before second merge.
5. **Post-merge validation**
   - Run targeted post-merge validation and confirm no behavior drift from expected serial outcomes.

## 5) Decision Rules

Parallel 2-slice execution is valid only if all are true:

1. **Behavior is identical to sequential execution** for the validated path(s).
2. **Attribution remains clear** (each change and outcome is traceable to one slice).
3. **No ambiguity is introduced** in promotion state, ownership, or interpretation of results.

## 6) Enforcement Rules

The following are mandatory and fail-closed:

1. Any constraint violation → **immediate abort**.
2. Any ambiguity in behavior, attribution, or state interpretation → **failure**.
3. Missing validation or review evidence → **failure**.

No partial-pass classification is allowed under this policy.

## 7) Escalation Path

If a 2-slice run fails under this policy:

1. immediately revert to **serial PQX** execution,
2. open and complete a **new governed trial** before attempting to re-enable parallel execution.

## 8) Governance Boundaries

This policy is intentionally narrow:

1. applies only to **exactly two** concurrent PQX slices,
2. does not claim readiness for broad or general concurrency,
3. introduces **no runtime enforcement, certification logic, CLI, or CI behavior changes**.

## 9) Activation Record

- **Plan lineage:** PQX-CLT-011 (`docs/reviews/2026-03-27-parallel-pqx-trial-plan.md`)
- **Approved trial lineage:** PQX-CLT-015 (recorded in `docs/reviews/2026-03-27-parallel-pqx-trial-closure.md`)
- **Policy activation:** PQX-CLT-016 (this document)

## 10) GOV hardening rule — authority-language boundaries (HRD-002)

For **non-CTL/SEL/ENF artifacts**, authority references are signal-only:

1. artifacts may reference control/enforcement systems strictly as input, signal, or observation seams;
2. artifacts must not imply execution, decision, promotion, enforcement, or certification ownership;
3. any authority-language implication in non-CTL/SEL/ENF artifacts is a **certification failure** and maps to a fail-closed **BLOCK** outcome.

This rule is consumed by preflight and eval hardening gates:

- AEX emits `authority_language_violation_record` and blocks preflight.
- EVAL executes `authority_language_compliance:v1`; fail result auto-blocks promotion gating.
