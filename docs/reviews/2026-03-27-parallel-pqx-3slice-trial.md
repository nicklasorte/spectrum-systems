# PQX-CLT-021 — Controlled 3-Slice Parallel PQX Feasibility Trial

- **Date:** 2026-03-28
- **Owner:** PQX Governance
- **Status:** CLOSED
- **Protocol basis:** CLT-012 execution protocol (`branch isolation` → `independent validation` → `cross-diff inspection` → `controlled merge sequence`)
- **Constraint posture:** strict governance / fail-closed

## 1) Objective

Determine whether governed PQX execution can safely support **3 concurrent slices** or whether **2-slice parallelism remains the stable limit**.

## 2) Trial scope and hard constraints

This feasibility trial is intentionally constrained to governance artifacts only:

- `docs/reviews/2026-03-27-parallel-pqx-3slice-trial.md`
- `docs/review-actions/parallel_pqx_3slice_actions.md`

Out of scope and prohibited for this step:

- runtime code changes
- test logic changes
- certification/control-loop logic changes
- CLI/CI behavior changes
- policy expansion beyond experiment evidence capture

## 3) Slices selected

Three candidate slices were selected to satisfy non-overlap requirements while maximizing representational coverage.

- **Slice A (docs governance):** `PQX-CLT-021A`
  - Surface: review/governance documentation
  - Artifact target: `docs/reviews/2026-03-27-parallel-pqx-3slice-trial.md`
- **Slice B (isolated runtime candidate):** `PQX-CLT-021B`
  - Surface: isolated runtime candidate (`spectrum_systems/modules/evaluation/eval_coverage_reporting.py`)
- **Slice C (isolated test candidate):** `PQX-CLT-021C`
  - Surface: isolated test candidate (`tests/test_eval_dataset_registry.py`)

### Eligibility checks at selection time

- **No file overlap:** PASS (distinct paths)
- **No schema/contract overlap:** PASS (no `contracts/schemas/` or contract manifest touch)
- **No control-loop/certification overlap:** PASS (no `control_loop`, certification gate, or enforcement-bridge surfaces)

## 4) CLT-012 protocol execution (3-slice adaptation)

### 4.1 Branch isolation

- All slices defined from a common baseline planning point.
- No cross-slice cherry-picks.
- Slice scopes remained independently attributable.

### 4.2 Independent validation

Validation evidence was captured independently per slice candidate:

- `pytest -q tests/test_evaluation_enforcement_bridge.py` → PASS (`83 passed`)
- `pytest -q tests/test_control_loop_certification.py` → PASS (`6 passed`)
- `pytest -q tests/test_eval_dataset_registry.py` → PASS (`19 passed`)

### 4.3 Pairwise cross-diff inspection

Pairwise interaction checks were executed conceptually and by path-surface rules:

- **A↔B:** no path overlap, no shared schema/contract, no certification/control-loop overlap
- **A↔C:** no path overlap, no shared schema/contract, no certification/control-loop overlap
- **B↔C:** no path overlap, no shared schema/contract, no certification/control-loop overlap

### 4.4 Combined (A+B+C) interaction check

Combined-triple check identified a governance interpretation risk:

- While direct file/surface overlap remained absent, attribution certainty for a true concurrent runtime+test+docs 3-way merge was **not proven with executed branch-level merge evidence in this slice-constrained run**.
- Under strict rules, this is treated as **ambiguity** rather than inferred safety.

### 4.5 Controlled merge-sequence assessment

A deterministic merge sequence model was defined (A → B → C), but because this step is explicitly documentation-scoped, full branch-level 3-way merge execution evidence is not asserted here.

## 5) Evidence log (BEFORE / AFTER)

## BEFORE

- Baseline behavior checks:
  - `tests/test_evaluation_enforcement_bridge.py` PASS
  - `tests/test_control_loop_certification.py` PASS
  - `tests/test_eval_dataset_registry.py` PASS

## AFTER

- Post-documentation-step behavior checks:
  - `tests/test_evaluation_enforcement_bridge.py` PASS
  - `tests/test_control_loop_certification.py` PASS
  - `tests/test_eval_dataset_registry.py` PASS

## Result comparison

- BEFORE vs AFTER behavior in measured checks: **IDENTICAL**.
- However, identical behavior in this constrained documentation step does **not** eliminate 3-way operational attribution ambiguity.

## 6) Observability signals

Recorded for this feasibility trial window:

- **parallel_run_count (3-slice trial attempts):** 1
- **interference_rate:** 0/1 = **0.00** (no direct overlap/interference observed)
- **ambiguous_failure_rate:** 1/1 = **1.00** (attribution certainty not fully proven for true 3-way concurrent merge execution)
- **recovery_outcome:** serial fallback remains clean/available; no runtime/test/certification rollback required in this step

## 7) Strict evaluation outcome

Fail-closed criteria were applied:

- Any ambiguity → FAIL
- Any interference → FAIL

Outcome for PQX-CLT-021:

- **Interference:** not observed
- **Ambiguity:** observed (material)
- **Trial classification:** **FAILED (ambiguity-triggered)**

## 8) Final decision

**Decision:** **DENIED** — stable governed limit remains **2-slice parallelism**.

Rationale:

1. The experiment did not produce unambiguous branch-level 3-way concurrent merge attribution evidence under strict governance rules.
2. Under fail-closed policy posture, unresolved ambiguity is sufficient for denial.
3. No policy expansion is authorized from this trial.

## 9) Scope integrity confirmation

Confirmed for this implementation step:

- only documentation artifacts were created
- no runtime code changes
- no test changes
- no certification logic changes
- no CLI/CI behavior changes
