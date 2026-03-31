# Plan — G17 Scope Repair — 2026-03-31

## Prompt type
PLAN

## Roadmap item
G17 — Manifest Completeness Gate Scope Repair

## Objective
Restrict manifest completeness gate to explicit/preflight invocation paths, restore canonical runtime happy-path behavior, and re-enable strict persisted reload tamper detection in sequence runner.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-G17-SCOPE-REPAIR-2026-03-31.md | CREATE | Required multi-file plan before BUILD changes. |
| PLANS.md | MODIFY | Register active G17 scope-repair execution plan. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Narrow manifest gate to opt-in enforcement boundary. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Restore strict persisted reload mismatch fail-closed behavior. |
| tests/test_pqx_slice_runner.py | MODIFY | Cover default non-blocking behavior and explicit manifest gate block path. |
| tests/test_pqx_sequence_runner.py | MODIFY | Ensure tampered persisted reload mismatch raises fail-closed error. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_manifest_completeness.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_pqx_backbone.py`
4. `pytest tests/test_pqx_bundle_orchestrator.py`
5. `pytest tests/test_pqx_fix_execution.py`
6. `pytest tests/test_pqx_sequence_runner.py`
7. `pytest tests/test_prompt_queue_sequence_cli.py`

## Scope exclusions
- Do not modify `contracts/standards-manifest.json` in this repair slice.
- Do not redesign PQX orchestration semantics beyond manifest-gate boundary repair and tamper detection restoration.
- Do not add non-stdlib dependencies.

## Dependencies
- docs/roadmaps/system_roadmap.md remains authoritative execution roadmap.
