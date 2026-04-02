# Plan — CON-033-FIX PREFLIGHT BLOCK RECONCILIATION — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-033-FIX — Reconcile exact contract preflight BLOCK

## Objective
Reproduce the exact CI-shaped preflight BLOCK for CON-033 and apply the smallest fail-closed reconciliation needed to make that exact command return ALLOW.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-033-FIX-PREFLIGHT-BLOCK-2026-04-02.md | CREATE | Required plan-first artifact for this fix slice. |
| PLANS.md | MODIFY | Register CON-033-FIX plan entry. |
| scripts/run_contract_preflight.py | MODIFY (if needed) | Narrow seam reconciliation only if exact BLOCK root-cause is in preflight propagation/mapping logic. |
| tests/test_contract_preflight.py | MODIFY (if needed) | Add/adjust narrow deterministic regression test for exact failing seam. |
| contracts/examples/*.json | MODIFY (if needed) | Only if exact BLOCK proves stale example mismatch. |
| contracts/schemas/*.json | MODIFY (if needed) | Only if exact BLOCK proves schema/example/runtime inconsistency. |

## Contracts touched
None expected; contract changes allowed only if exact failing seam proves a schema/example inconsistency.

## Tests that must pass after execution
1. `python scripts/run_contract_preflight.py --base-ref "5e306549101a83f8c5ff746d043cda3aed3dcf60" --head-ref "36390a411e18f28dafedf2f2d5c505f8d519b161" --output-dir outputs/contract_preflight`
2. Targeted `pytest` for changed files
3. `python scripts/run_contract_enforcement.py` (only if any contract/example/schema changed)
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign CON-033 cohesion evaluator or gating architecture.
- Do not broaden preflight policy.
- Do not add bypasses, warnings, or masking behavior.
- Do not touch unrelated modules, tests, or roadmap files.

## Dependencies
- Existing CON-033 implementation must remain fail-closed.
- CI-shaped repro command/output artifacts are source of truth for this fix.
