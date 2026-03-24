# SF-14 Release Boundary Review

Date: 2026-03-24  
Reviewer: Codex (focused architecture + reliability review)

## Scope Reviewed (strict)
- `evaluation_release_record` schema and example (requested)
- `scripts/run_release_canary.py` (or equivalent entrypoint)
- Canary comparison logic (baseline vs candidate)
- Release decision logic (promote/hold/rollback)
- `eval_release_policy.json` loading and usage

## Scope Exclusions (strict)
- Entire repository-wide review
- Unrelated eval, coverage, or SBGE modules
- UI, dashboards, and future features

## Overall Decision
**FAIL**

## Critical Issues (must fix before merge)
- [ ] **Required SF-14 release artifacts are missing under requested contract names.** No `evaluation_release_record` schema/example, no `run_release_canary.py`, and no `eval_release_policy.json` were found.
- [ ] **Determinism is violated in the baseline-vs-candidate simulation artifact path.** `simulation_id` uses `uuid4()` and `created_at` uses wall-clock time; identical inputs can produce different artifacts.
- [ ] **Decision thresholds are hardcoded in code rather than fully policy-driven.** Promotion and regression thresholds are embedded constants in `simulation_compare.py`, enabling policy drift or bypass.

## High-Risk Gaps
- No explicit `rollback` outcome in the reviewed candidate-release decision artifact path (`promote|hold|reject` only), which can misalign with SF-14 release semantics.
- Canary comparison is aggregate-centric (`structural_score`, `semantic_score`, `grounding_score`, `latency_ms`) and does not enforce slice-level parity checks in this path.
- “New failures introduced” are not explicitly modeled as a first-class baseline-vs-candidate set-diff condition.

## Medium Issues
- `run_fix_simulation.py` has optional strict mode; without `--strict`, hard regression failures can still return exit code 0.
- `run_eval_ci_gate.py` is fail-closed but uses `eval_ci_gate_policy.json`, not `eval_release_policy.json`; release policy centralization is therefore inconsistent with requested SF-14 boundary.
- Decision precedence is implemented via ordered early returns but not codified as a single explicit precedence lattice artifact (`rollback > hold/block > promote`).

## Confirmed Guarantees
- `run_eval_ci_gate.py` blocks on missing required artifacts and invalid policy JSON, returning blocked status and non-zero exit.
- `run_eval_ci_gate.py` treats indeterminate outcomes as blocking.
- `evaluation_ci_gate_result` schema requires blocking reasons and artifact-trace metadata, supporting post-hoc auditability.

## Recommended Fixes (ordered)
1. Publish the exact SF-14 governed interface: `evaluation_release_record` schema + example, `eval_release_policy.json`, and canonical release-canary entrypoint.
2. Centralize all gating thresholds in governed policy files; fail closed on missing/invalid policy.
3. Add explicit precedence reducer with enforced ordering: rollback overrides all; block/hold overrides promote.
4. Add slice-level parity checks and explicit “new failures introduced” detection to canary comparison.
5. Make decision artifacts deterministic: derive stable IDs from input hashes and separate nondeterministic metadata.
6. Remove optional fail-open release execution modes for production gating paths.

## Residual Risk After Fixes
- **Moderate** if slice definitions/failure taxonomy remain unstable.
- **Low** once policy centralization, precedence hardening, deterministic artifacts, and explicit failure-diff checks are enforced.

## Evidence Snapshot
- Equivalent fail-closed CI gate reviewed: `scripts/run_eval_ci_gate.py`.
- Equivalent baseline-vs-candidate and promotion logic reviewed: `spectrum_systems/modules/improvement/simulation_compare.py` and `spectrum_systems/modules/improvement/simulation.py`.
- Policy artifact reviewed: `data/policy/eval_ci_gate_policy.json`.
- Artifact schema reviewed: `contracts/schemas/simulation_result.schema.json` and `contracts/schemas/evaluation_ci_gate_result.schema.json`.
