# Plan — PREFLIGHT-BLOCK-RECOVERY-LOOP — 2026-04-13

## Prompt type
PLAN

## Roadmap item
Unscheduled fail-closed preflight recovery hardening

## Objective
Convert contract-preflight BLOCK outcomes from opaque CI dead-ends into deterministic governed artifact bundles with bounded repair/escalation routing while preserving fail-closed exits.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| scripts/run_contract_preflight.py | MODIFY | Emit classification, repair-eligibility, rerun decision, escalation artifacts on BLOCK. |
| scripts/build_preflight_pqx_wrapper.py | MODIFY | Ensure wrapper includes stable hooks/paths for preflight recovery artifacts. |
| scripts/run_github_pr_autofix_contract_preflight.py | MODIFY | Bridge BLOCK outputs into governed pre-PR repair loop handoff. |
| contracts/schemas/contract_preflight_result_artifact.schema.json | MODIFY | Add/require normalized failure-class + reason-code bundle fields. |
| contracts/schemas/preflight_block_diagnosis_record.schema.json | MODIFY | Harden diagnosis payload schema for deterministic classes/codes. |
| contracts/schemas/preflight_repair_plan_record.schema.json | MODIFY | Include bounded retry budget and rerun prerequisites. |
| contracts/schemas/preflight_repair_result_record.schema.json | MODIFY | Add rerun_allowed/prohibited and escalation linkage. |
| contracts/schemas/failure_repair_candidate_artifact.schema.json | MODIFY | Normalize candidate output for preflight BLOCK workflows. |
| .github/workflows/pr-autofix-contract-preflight.yml | MODIFY | Publish actionable BLOCK artifact outputs and upload bundle paths. |
| tests/test_contract_preflight.py | MODIFY | Cover BLOCK classification + artifact emission behavior. |
| tests/test_build_preflight_pqx_wrapper.py | MODIFY | Assert wrapper contains deterministic recovery artifact paths. |
| tests/test_governed_preflight_remediation_loop.py | MODIFY | Cover repairable/non-repairable/unknown + retry-budget behavior. |
| tests/test_run_github_pr_autofix_contract_preflight.py | MODIFY | Assert CI-facing report paths and surfaced guidance. |

## Contracts touched
Preflight and failure/repair contracts listed above; no unrelated schema family changes.

## Tests that must pass after execution
1. `pytest tests/test_contract_preflight.py tests/test_build_preflight_pqx_wrapper.py tests/test_governed_preflight_remediation_loop.py tests/test_run_github_pr_autofix_contract_preflight.py`
2. `python scripts/run_contract_preflight.py --help`
3. `python scripts/build_preflight_pqx_wrapper.py --help`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- No weakening of fail-closed BLOCK semantics or exit code 2 behavior.
- No replacement of existing governance owners (TPA/SEL/CDE/PQX boundaries remain unchanged).
- No broad refactor of unrelated contract families.

## Dependencies
- Existing preflight wrapper + contract preflight scripts and current pre-PR autofix workflow.
