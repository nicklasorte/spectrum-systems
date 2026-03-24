# Plan — SF-05 Eval Harness + CI Gate — 2026-03-23

## Prompt type
PLAN

## Roadmap item
SF-05 — Eval Harness + CI Gate for spectrum-systems

## Objective
Implement a fail-closed CI eval gate entrypoint that runs governed eval execution, validates required artifacts against canonical schemas, computes blocking decisions from thresholds/control policy, emits a machine-readable gate summary artifact, and is wired into GitHub Actions with focused tests and docs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SF-05-EVAL-CI-GATE-2026-03-23.md | CREATE | Required PLAN artifact before multi-file BUILD/WIRE work. |
| scripts/run_eval_ci_gate.py | CREATE | Canonical CI gate entrypoint that orchestrates eval run, schema validation, threshold gating, control decision gating, summary artifact emission, and exit code handling. |
| data/policy/eval_ci_gate_policy.json | CREATE | Minimal governed config for deterministic gate thresholds and required artifact expectations. |
| contracts/schemas/evaluation_ci_gate_result.schema.json | CREATE | Canonical schema for machine-readable CI summary artifact. |
| contracts/examples/evaluation_ci_gate_result.json | CREATE | Golden-path contract example for CI summary artifact. |
| contracts/standards-manifest.json | MODIFY | Register/pin the new evaluation_ci_gate_result contract version entry and bump manifest version metadata. |
| tests/test_eval_ci_gate.py | CREATE | Focused tests for pass path and fail-closed blocking conditions. |
| .github/workflows/lifecycle-enforcement.yml | MODIFY | Wire CI to invoke the new eval CI gate script and preserve summary artifacts. |
| docs/reliability/eval-ci-gate.md | CREATE | Operator/developer documentation for purpose, inputs, blocking conditions, exit behavior, and local usage. |

## Contracts touched
- Create: `contracts/schemas/evaluation_ci_gate_result.schema.json` (new contract)
- Modify: `contracts/standards-manifest.json` (version bump + contract registry update)

## Tests that must pass after execution
1. `pytest tests/test_eval_ci_gate.py -v`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -v`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign eval architecture or replace existing eval modules.
- Do not add UI/frontend changes.
- Do not introduce new non-standard dependencies unless strictly required.
- Do not modify unrelated workflows or broad governance docs.

## Dependencies
- Existing eval contracts and runtime control decision flow in `spectrum_systems/modules/evaluation/` and `spectrum_systems/modules/runtime/` must remain authoritative and be reused.
