# Plan — ALIGNMENT-020-PREFLIGHT-FIX — 2026-04-01

## Prompt type
PLAN

## Roadmap item
FOUNDATION-ALIGNMENT-019 follow-up fail-closed seam repair

## Objective
Resolve contract preflight BLOCK by repairing the exact producer/consumer propagation seams identified in preflight artifacts (certification producer output shape and promotion fixture/consumer coverage), without weakening gates.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-ALIGNMENT-020-PREFLIGHT-FIX-2026-04-01.md | CREATE | Record governed repair scope and validation obligations. |
| PLANS.md | MODIFY | Register active plan for this preflight repair. |
| scripts/run_control_loop_certification.py | MODIFY | Producer must emit schema_version and required gate_proof fields compatible with updated contract. |
| tests/test_control_loop_certification.py | MODIFY | Remove masking by asserting updated contract-required fields in targeted producer tests. |
| tests/test_cycle_runner.py | MODIFY | Update promotion-path fixtures to include required closure evidence so expected promotion behavior remains valid. |
| tests/fixtures/autonomous_cycle/cycle_status_blocked_manifest.json | MODIFY | Propagate required closure evidence into impacted fixture seam from preflight report. |

## Contracts touched
None (no schema changes). Producer/fixture/consumer propagation only.

## Tests that must pass after execution
1. `pytest tests/test_control_loop_certification.py tests/test_cycle_runner.py tests/test_sequence_transition_policy.py`
2. `pytest tests/test_contracts.py tests/test_control_loop_closure.py`
3. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight --changed-path contracts/schemas/control_loop_certification_pack.schema.json --changed-path contracts/schemas/control_loop_closure_evidence_bundle.schema.json --changed-path contracts/schemas/recurrence_prevention_closure.schema.json`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- No contract/schema weakening or field removal.
- No roadmap rewrite.
- No unrelated runtime refactors.

## Dependencies
- Must use `outputs/contract_preflight/*` artifacts as source of truth for seam repair.
