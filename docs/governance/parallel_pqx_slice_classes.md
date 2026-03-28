# PQX-CLT-019 — Parallel PQX Slice Classification Policy

- **Date Activated:** 2026-03-28
- **Status:** **ACTIVE**
- **Scope:** Classification of PQX work items for parallel pairing decisions
- **Dependency:** `docs/governance/parallel_pqx_policy.md` remains authoritative for execution hard constraints

## 1) Purpose

This policy defines a repo-native, operator-usable classification model for PQX slices.
Classification is required before deciding whether two slices can run in parallel.

## 2) Required Classification Dimensions (Bounded Enums)

Each slice **must** be classified using all dimensions below.

### 2.1 Primary Surface (`primary_surface`)

Allowed values:

1. `docs_review_governance`
2. `isolated_runtime`
3. `isolated_test`
4. `shared_runtime`
5. `shared_test`
6. `schema_contract`
7. `control_loop_policy`
8. `certification_gate`
9. `registry_manifest`

### 2.2 Sharedness Risk (`sharedness_risk`)

Allowed values:

1. `none`
2. `low`
3. `high`

### 2.3 Control Sensitivity (`control_sensitivity`)

Allowed values:

1. `none`
2. `medium`
3. `critical`

### 2.4 Parallel Eligibility (`parallel_eligibility`)

Allowed values:

1. `parallel_safe`
2. `conditional`
3. `not_parallel_safe`

## 3) Class-to-Eligibility Rules (Fail-Closed)

Use this table to assign `parallel_eligibility` from `primary_surface`.

| Primary surface | Default eligibility | Operator rule |
| --- | --- | --- |
| `docs_review_governance` | `parallel_safe` | Allowed when file overlap is none and no hidden policy/certification edits are present. |
| `isolated_runtime` | `conditional` | Allowed only if changed files are non-overlapping and no shared contracts/manifests/control surfaces are touched. |
| `isolated_test` | `conditional` | Allowed only if test files are non-overlapping and tests do not mutate shared fixtures or certification assertions. |
| `shared_runtime` | `not_parallel_safe` | Shared runtime surfaces are serialized by default. |
| `shared_test` | `not_parallel_safe` | Shared test surfaces are serialized by default. |
| `schema_contract` | `not_parallel_safe` | Contract/schema changes are serialized by default. |
| `control_loop_policy` | `not_parallel_safe` | Control-loop policy changes are serialized by default. |
| `certification_gate` | `not_parallel_safe` | Certification-gate changes are serialized by default. |
| `registry_manifest` | `not_parallel_safe` | Registry/manifest changes are serialized by default. |

## 4) Pairing Rule

A pair of slices may run in parallel only when:

1. both slices are classified,
2. neither slice is `not_parallel_safe`,
3. all conditional constraints are satisfied,
4. no file overlap exists,
5. no shared schema/contract/control/certification/manifest surface is touched.

If any check fails, execute serially.

## 5) Fail-Closed Rule (Mandatory)

A slice defaults to `not_parallel_safe` when any of the following is true:

1. classification is missing,
2. classification is uncertain,
3. multiple plausible classes include any `not_parallel_safe` class,
4. operator evidence is incomplete,
5. expected touched files are unknown.

No “probably safe” or “assumed safe” decisions are allowed.

## 6) Recording Requirement

Operators must record classifications using:

- `docs/review-actions/parallel_pqx_slice_classification_template.md`

Classification records are required evidence for any parallel pairing decision.
