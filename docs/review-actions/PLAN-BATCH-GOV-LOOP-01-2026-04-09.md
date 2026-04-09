# Plan — BATCH-GOV-LOOP-01 — 2026-04-09

## Prompt Type
`BUILD`

## Intent
Implement a governed build → review → fix loop with strict role separation:
- PQX executes bounded slices
- RQX reviews only
- TPA gates every fix execution
- TLC performs routing/classification only

## Scope
| File | Action | Notes |
| --- | --- | --- |
| `spectrum_systems/modules/review_fix_execution_loop.py` | UPDATE | Enforce terminal unresolved routing to TLC disposition artifact and keep execution fail-closed. |
| `tests/test_pqx_bundle_orchestrator.py` | UPDATE | Add explicit test for build-stage review trigger naming requirement. |
| `tests/test_review_fix_execution_loop.py` | UPDATE | Add/align tests for TPA gating, RQX non-execution, re-entry, and unresolved terminal behavior. |
| `docs/operations/operator_playbook.md` | UPDATE | Add concise governed-loop clarifications (mandatory review, TPA gate, no RQX execution, unresolved terminal handoff). |

## Guardrails
- No new subsystem creation.
- No schema redesign.
- Preserve fail-closed behavior.
- Keep role ownership explicit and non-overlapping.
- Keep changes limited to governed loop behavior and tests/docs needed for this slice.

## Validation
- Run focused tests:
  - `pytest tests/test_pqx_bundle_orchestrator.py -k test_build_triggers_review`
  - `pytest tests/test_review_fix_execution_loop.py -k "test_rqx_never_executes_fixes or test_fix_requires_tpa_gate or test_rqx_routes_fix_to_tpa or test_fix_reentry_triggers_review or test_unresolved_stops_execution"`
- Run full relevant files:
  - `pytest tests/test_pqx_bundle_orchestrator.py tests/test_review_fix_execution_loop.py`
