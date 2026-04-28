# TST-01 CI/Test Inventory

## Summary counts
- Total workflow count: **17**
- Total pytest test file count: **816**
- Total pytest collected test count: **10209 tests collected in 20.21s**
- Total Jest test file count: **39**
- Total scripts used in CI workflows: **32**

## Generated CI artifacts (observed paths)
- `outputs/contract_preflight/*`
- `outputs/eval_ci_gate/*`
- `outputs/authority_shape_preflight/*`
- `outputs/sel_replay_gate/*`
- `outputs/required_check_alignment_audit/*`

## Duplication observations
- Contract preflight appears in both `pr-pytest.yml` and `artifact-boundary.yml`.
- Autofix preflight workflow duplicates trust checks from PR workflow.
- Governance/registry checks are split across multiple workflows with no single gate result artifact in legacy mode.

## Components without clear canonical mapping (pre-consolidation)
- `dashboard-deploy-gate.yml` tests dashboard publication paths outside a single canonical runtime gate path.
- `review_*` workflows produce review outputs outside a single canonical gate result contract.

## Canonical gate mapping snapshot
- Contract Gate: contract/schema validation workflows and scripts.
- Runtime Test Gate: pytest/jest execution and dashboard runtime tests.
- Governance Signal Gate: required-check alignment, system registry guard, governance manifest checks.
- Readiness Evidence Gate: replay/lineage and GOV-10 input evidence checks.
