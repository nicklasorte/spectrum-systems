# Plan — PREFLIGHT-AUTOREPAIR-INVOCATION-LOOP — 2026-04-13

## Prompt type
PLAN

## Roadmap item
Unscheduled governed preflight automation gap closure

## Objective
Ensure BLOCK + auto_repair_allowed preflight outcomes route into bounded governed repair/rerun automatically and produce a deterministic terminal recovery outcome artifact for CI.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py | MODIFY | Emit terminal recovery outcome and stop treating initial BLOCK as terminal dead-end for auto-repairable paths. |
| scripts/run_github_pr_autofix_contract_preflight.py | MODIFY | Surface recovery outcome paths/status to CI callers. |
| .github/workflows/pr-autofix-contract-preflight.yml | MODIFY | Run autorepair in bounded continuation mode and gate job on final recovery outcome. |
| contracts/schemas/preflight_recovery_outcome_record.schema.json | CREATE | Schema-bound terminal artifact for block->repair->rerun chain. |
| contracts/examples/preflight_recovery_outcome_record.json | CREATE | Example payload for recovery outcome artifact. |
| tests/test_github_pr_autofix_contract_preflight.py | MODIFY | Validate final recovery outcomes for success/fail/escalation branches. |
| tests/test_run_github_pr_autofix_contract_preflight.py | MODIFY | Validate CLI reporting of recovery outcome details. |
| tests/test_contract_preflight.py | MODIFY | Validate block bundle+recovery contract linkage. |
| tests/test_preflight_autofix_contracts.py | MODIFY | Validate new recovery outcome contract example. |

## Contracts touched
`preflight_recovery_outcome_record` (new) and preflight autorepair output linkage.

## Tests that must pass after execution
1. `pytest tests/test_github_pr_autofix_contract_preflight.py tests/test_run_github_pr_autofix_contract_preflight.py tests/test_contract_preflight.py tests/test_preflight_autofix_contracts.py`
2. `python scripts/run_contract_enforcement.py`
3. `git diff --check`

## Scope exclusions
- No weakening of BLOCK fail-closed semantics for non-repairable or failed-repair paths.
- No broad redesign of PQX/TPA/SEL ownership layers.

## Dependencies
- Existing BLOCK bundle emission from `scripts/run_contract_preflight.py`.
