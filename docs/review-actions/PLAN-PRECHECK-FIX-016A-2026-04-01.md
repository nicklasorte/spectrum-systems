# Plan — PRECHECK-FIX-016A Contract Preflight rg-Portability Fix — 2026-04-01

## Prompt type
PLAN

## Roadmap item
Preflight portability hardening (surgical follow-up)

## Objective
Eliminate remaining `rg` dependency in `scripts/run_contract_preflight.py` by replacing test-target discovery with repo-native Python scanning and ensuring graceful degradation when optional tooling is absent.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PRECHECK-FIX-016A-2026-04-01.md | CREATE | Declare constrained scope for this surgical portability fix. |
| scripts/run_contract_preflight.py | MODIFY | Remove `rg` shell-out in `resolve_test_targets()` and harden command execution behavior for missing optional tools. |
| tests/test_contract_preflight.py | MODIFY | Add regression tests proving no `rg` shell-out is required and report generation remains intact. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_contract_preflight.py -q`
2. `python scripts/run_contract_preflight.py --changed-path contracts/schemas/control_loop_certification_pack.schema.json --output-dir outputs/contract_preflight_smoke`
3. `rg -n "\brg\b|ripgrep" scripts/run_contract_preflight.py`
4. `PLAN_FILES="docs/review-actions/PLAN-PRECHECK-FIX-016A-2026-04-01.md scripts/run_contract_preflight.py tests/test_contract_preflight.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not alter contract schemas/examples/manifest.
- Do not change preflight policy semantics or gate thresholds.
- Do not refactor unrelated detection/classification flows.

## Dependencies
- Existing preflight detection/report behavior remains authoritative and must remain deterministic.
