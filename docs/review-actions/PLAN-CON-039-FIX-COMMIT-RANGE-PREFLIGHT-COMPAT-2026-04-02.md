# Plan — CON-039-FIX-COMMIT-RANGE — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-039 FIX — Commit-Range Preflight Compatibility (PQX Enforcement-Aware)

## Objective
Restore CI-safe commit-range inspection behavior by distinguishing preflight inspection posture from execution admission while preserving fail-closed governed execution enforcement and emitting schema-backed machine-readable pending-execution state.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-039-FIX-COMMIT-RANGE-PREFLIGHT-COMPAT-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file enforcement compatibility fix. |
| PLANS.md | MODIFY | Register this fix plan in active plans table. |
| spectrum_systems/modules/runtime/pqx_required_context_enforcement.py | MODIFY | Add commit-range inspection mode semantics and machine-readable authority/execution requirement fields. |
| scripts/run_contract_preflight.py | MODIFY | Detect commit-range inspection mode and wire updated enforcement semantics into report/artifact. |
| contracts/schemas/contract_preflight_result_artifact.schema.json | MODIFY | Extend artifact contract with authority_state/requires_pqx_execution/enforcement_decision fields for required-context enforcement object. |
| contracts/examples/contract_preflight_result_artifact.json | MODIFY | Update canonical artifact example for evolved enforcement object fields/schema version. |
| contracts/examples/contract_preflight_result_artifact.example.json | MODIFY | Keep companion example aligned with schema-backed artifact contract. |
| contracts/standards-manifest.json | MODIFY | Bump standards publication and contract schema pin for preflight artifact evolution. |
| tests/test_pqx_required_context_enforcement.py | MODIFY | Add focused tests for commit-range inspection allow/block semantics. |
| tests/test_contract_preflight.py | MODIFY | Validate commit-range no-context allow pending execution state and explicit direct-context block behavior. |
| tests/test_contracts.py | MODIFY | Assert evolved example includes required machine-readable enforcement fields. |

## Contracts touched
- MODIFY `contracts/schemas/contract_preflight_result_artifact.schema.json`
- MODIFY `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest -q tests/test_pqx_required_context_enforcement.py`
2. `pytest -q tests/test_contract_preflight.py`
3. `pytest -q tests/test_contracts.py`
4. `pytest -q tests/test_contract_enforcement.py`
5. `python scripts/run_contract_preflight.py --base-ref origin/main --head-ref HEAD`
6. `python scripts/run_contract_preflight.py --base-ref origin/main --head-ref HEAD --execution-context direct --changed-path contracts/schemas/roadmap_eligibility_artifact.schema.json`
7. `PLAN_FILES="docs/review-actions/PLAN-CON-039-FIX-COMMIT-RANGE-PREFLIGHT-COMPAT-2026-04-02.md PLANS.md spectrum_systems/modules/runtime/pqx_required_context_enforcement.py scripts/run_contract_preflight.py contracts/schemas/contract_preflight_result_artifact.schema.json contracts/examples/contract_preflight_result_artifact.json contracts/examples/contract_preflight_result_artifact.example.json contracts/standards-manifest.json tests/test_pqx_required_context_enforcement.py tests/test_contract_preflight.py tests/test_contracts.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not weaken governed execution PQX requirements.
- Do not special-case CI by bypassing enforcement.
- Do not move enforcement to report-only output.
- Do not redesign wrapper or authority model.

## Dependencies
- CON-039 schema-backed required-context artifact fields are already in place.
- CON-038 wrapper contract remains authoritative.
