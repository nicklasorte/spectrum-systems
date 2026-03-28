# PQX-CLT-020 — Parallel PQX Pairing Rules

- **Date Activated:** 2026-03-28
- **Status:** **ACTIVE**
- **Scope:** Deterministic 2-slice pairing decisions for parallel PQX execution
- **Depends On:** `docs/governance/parallel_pqx_slice_classes.md` (classification authority)

## 1) Purpose

This policy converts slice classification into deterministic pairing outcomes.
Operators must use this file to decide whether exactly two PQX slices may execute in parallel.

## 2) Required Inputs (Both Slices)

Before evaluating pairing rules, classify **Slice A** and **Slice B** using all required dimensions:

1. `primary_surface`
2. `sharedness_risk`
3. `control_sensitivity`
4. `parallel_eligibility`

If any required dimension is missing for either slice, pairing is denied.

## 3) Hard Blocks (Apply First, Order Is Mandatory)

Deny pairing immediately if **any** condition is true:

1. Slice A or Slice B has `primary_surface = schema_contract`.
2. Slice A or Slice B has `primary_surface = certification_gate`.
3. Slice A or Slice B has `primary_surface = control_loop_policy`.
4. Slice A or Slice B has `primary_surface = shared_runtime`.
5. Slice A or Slice B has `parallel_eligibility = not_parallel_safe`.

These checks are absolute and override all other rules.

## 4) Explicit Pairing Matrix (2-Slice)

Interpret the matrix by `primary_surface` pair.
Result values are only `ALLOW`, `DENY`, or `CONDITIONAL`.

| Slice A \\ Slice B | docs_review_governance | isolated_runtime | isolated_test | shared_runtime | shared_test | schema_contract | control_loop_policy | certification_gate | registry_manifest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **docs_review_governance** | **ALLOW** | **ALLOW** | **ALLOW** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **isolated_runtime** | **ALLOW** | **CONDITIONAL** | **CONDITIONAL** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **isolated_test** | **ALLOW** | **CONDITIONAL** | **CONDITIONAL** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **shared_runtime** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **shared_test** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **schema_contract** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **control_loop_policy** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **certification_gate** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |
| **registry_manifest** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** | **DENY** |

### Matrix-to-rule clarifications

- `docs_review_governance + docs_review_governance` → `ALLOW`.
- `docs_review_governance + isolated_runtime` → `ALLOW`.
- `isolated_runtime + isolated_runtime` → `CONDITIONAL`.
- `any + schema_contract` → `DENY`.
- `any + certification_gate` → `DENY`.
- `any + control_loop_policy` → `DENY`.
- `shared_runtime + anything` → `DENY`.

## 5) Conditional Gate (Required for Any `CONDITIONAL` Result)

A `CONDITIONAL` matrix result becomes final `ALLOW` only if **all** checks pass:

1. No file-path overlap between Slice A and Slice B.
2. No shared fixture overlap.
3. No shared contract/schema/manifest path overlap.
4. No control-policy or certification-gate path overlap.
5. `sharedness_risk` for both slices is not `high`.
6. `control_sensitivity` for both slices is not `critical`.

If any check fails or cannot be proven, final decision is `DENY`.

## 6) Pairing Decision Procedure (Operator)

Run this procedure in order. No step may be skipped.

1. Classify Slice A on all required dimensions.
2. Classify Slice B on all required dimensions.
3. Apply Hard Blocks (Section 3).
4. Read matrix outcome from Section 4.
5. If matrix outcome is `CONDITIONAL`, execute Section 5 checks.
6. Record final decision as exactly one of: `ALLOW` or `DENY`.
7. Record the applied rule and rationale using the pairing template.

## 7) Fail-Closed Rules (Mandatory)

Set final decision to `DENY` when any of the following is true:

1. Classification is missing for either slice.
2. Classification is ambiguous or disputed.
3. Pairing rule lookup is unclear.
4. Overlap status is uncertain.
5. Evidence is incomplete.

No “probably safe,” “assumed safe,” or “likely safe” decision path is permitted.

## 8) Required Evidence Artifact

Every 2-slice pairing decision must be recorded in:

- `docs/review-actions/parallel_pqx_pairing_template.md`
