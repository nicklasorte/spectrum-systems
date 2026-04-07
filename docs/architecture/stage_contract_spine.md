# Stage Contract Spine (HR-01 + HR-02)

## Why this exists

The repository already enforces strong governance and fail-closed controls, but stage requirements were distributed across multiple subsystems (PQX orchestration, prompt queue transitions, checkpoint/resume artifacts, and workflow-specific logic). That made it possible for stage semantics to drift across implementation seams.

This slice introduces a single canonical artifact type (`stage_contract`) plus a runtime evaluator so stage-local requirements can be declared once and executed deterministically.

## What this slice introduces

1. **Canonical contract schema**: `contracts/schemas/stage_contract.schema.json`.
2. **Deterministic runtime**: `spectrum_systems/modules/runtime/stage_contract_runtime.py`.
3. **First integration seam**: promotion transition path in `spectrum_systems/orchestration/sequence_transition_policy.py`.

## What it does not do

- It does **not** replace control/promotion authority.
- It does **not** introduce a second policy engine.
- It does **not** migrate every workflow/harness path in one change.
- It does **not** call models.

The stage-contract runtime is stage-local readiness logic only.

## Canonical stage contract model

The `stage_contract` artifact declares:

- stage identity (`workflow_family`, `stage`, `sequence`, `status`)
- required stage inputs/outputs
- acceptance criteria
- required evaluations and validation checks
- permission/budget constraints
- deterministic transition rules and stop conditions
- handoff/provenance metadata

Schema strictness rules:

- Draft 2020-12
- `additionalProperties: false` at top-level and nested control objects
- explicit `required` fields

## Runtime evaluation semantics

`evaluate_stage_transition_readiness(...)` enforces fail-closed readiness:

- missing required input → `block`
- missing required output → `block`
- missing required eval → `block`
- failed required eval → `block`
- indeterminate required eval → `freeze` or `block` per contract (default `freeze`)
- trace incomplete (when required) → `block`
- policy violation signal → `block`
- budget exhaustion → `freeze` or `block` per contract (default `freeze`)

The output is structured and deterministic:

- `ready_to_advance`
- `recommended_state` (`advance`, `freeze`, `block`)
- machine-usable reason codes and missing-signal lists

## First integration seam

This slice wires stage contracts into one narrow seam only:

- `evaluate_sequence_transition(..., target_state="promoted")`
- opt-in through manifest `stage_contract_path`

If present, the stage contract is loaded and evaluated before allowing promotion. Failure is deterministic and fail-closed. Existing promotion gates still run and remain authoritative.

## Migration path (future HR slices)

- **HR-03**: bind canonical checkpoint/resume transitions to stage contracts.
- **HR-04**: long-running execution policy surfaces consume stage-contract budgets and stop-conditions directly.
- **HR-05**: human checkpoint and approval artifacts mapped to stage-contract handoff/permission controls.
- **HR-06/HR-10**: permission decision artifacts and workflow-compiled stage contracts consume this canonical spine.

Migration approach stays seam-by-seam with backward-compatible opt-in wiring, then hardening to required paths once coverage and fixtures are complete.
