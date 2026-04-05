# Plan — BATCH-TPA-09A-INTEGRATION-FIX — 2026-04-05

## Prompt type
PLAN

## Roadmap item
TPA-ACT-08B-AR-01, TPA-ACT-08B-AR-02 (integration/preflight remediation)

## Objective
Remove the explicit contract-preflight BLOCK by ensuring control-surface manifest input is repo-generated at enforcement time, then align HITL override enforcement tests with the v1.1.0 override contract/fail-closed behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TPA-09A-INTEGRATION-FIX-2026-04-05.md | CREATE | Required plan artifact for this multi-file integration fix. |
| PLANS.md | MODIFY | Register active plan. |
| scripts/run_contract_preflight.py | MODIFY | Auto-generate/load control-surface manifest before enforcement to satisfy required input without bypassing invariants. |
| tests/test_contract_preflight.py | MODIFY | Add deterministic test coverage for manifest auto-generation path and fail-closed generation error path. |
| tests/test_hitl_override_enforcement.py | MODIFY | Align override tests to v1.1.0 required expiry semantics and updated fail-closed outcomes. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_contract_preflight.py -q`
2. `pytest tests/test_hitl_override_enforcement.py -q`
3. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight`
4. `.codex/skills/verify-changed-scope/run.sh` with declared file list

## Scope exclusions
- Do not weaken any control-surface invariant or strategy gate behavior.
- Do not redesign TPA hardening logic introduced in TPA-09A.
- Do not broadly refactor unrelated contracts/examples.

## Dependencies
- Existing TPA-09A contract and runtime hardening changes remain authoritative.
