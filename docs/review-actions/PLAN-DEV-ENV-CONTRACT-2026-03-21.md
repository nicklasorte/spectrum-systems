# Plan — DEV-ENV-CONTRACT — 2026-03-21

## Prompt type
PLAN

## Roadmap item
Operational hygiene — governed developer environment contract

## Objective
Define and enforce a repo-native development environment contract so fresh Codespaces/devcontainers provide required Python and Node prerequisites, and failures are surfaced with deterministic diagnostics.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-DEV-ENV-CONTRACT-2026-03-21.md | CREATE | Record declared scope and validation expectations before BUILD work. |
| PLANS.md | MODIFY | Register this plan in the active plans table per repo process. |
| .devcontainer/devcontainer.json | MODIFY | Make Codespaces/devcontainer config explicitly install Node and Python dependencies. |
| devcontainer-spec/devcontainer.json | MODIFY | Keep canonical devcontainer spec aligned with enforced runtime contract. |
| scripts/verify_environment.py | CREATE | Add deterministic environment verification entrypoint with clear failure signals. |
| tests/test_verify_environment.py | CREATE | Add focused deterministic tests for environment verification helper behavior. |
| README.md | MODIFY | Document runtime requirements and preflight verification command succinctly. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/verify_environment.py`
2. `pytest tests/test_verify_environment.py -q`
3. `pytest tests/test_cross_repo_compliance_scanner.py -q`
4. `pytest`

## Scope exclusions
- Do not alter governance schemas or standards manifest versions.
- Do not weaken or skip cross-repo compliance tests.
- Do not introduce new package managers or unrelated workflow tooling.
- Do not refactor unrelated scripts/tests/docs.

## Dependencies
- None.
