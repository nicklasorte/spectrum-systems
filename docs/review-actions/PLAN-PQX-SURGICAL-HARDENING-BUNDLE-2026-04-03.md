# Plan — PQX Surgical Hardening Bundle (V-4, V-2, V-1, V-5, V-3) — 2026-04-03

## Prompt type
PLAN

## Roadmap item
Post-MVP red-team remediation bundle for PQX runtime trust gaps

## Intent
Implement a narrow hardening patch that closes five audited runtime trust gaps without redesigning PQX architecture or weakening fail-closed semantics.

## Scope
- Remove premature row-completion side effects from `run_pqx_slice` and move final completion authority to sequential control flow after enforcement ALLOW.
- Replace fixture decision derivation based on path/output substring sniffing with explicit `fixture_decision_mode` input and strict validation.
- Enforce blocked-slice trace evidence invariants (`wrapper_ref` required for blocked rows), and record typed block source for context-enforcement blocks.
- Require explicit `run_id` from context or wrapper identity; remove fallback to deterministic `trace_id`.
- Add optional canonical timestamp injection in enforcement mapping for deterministic replay/verification artifact bodies.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-SURGICAL-HARDENING-BUNDLE-2026-04-03.md | CREATE | Required plan-first artifact for multi-file BUILD scope |
| spectrum_systems/modules/pqx_backbone.py | MODIFY | Add explicit state-layer completion transition helper for post-enforcement authority |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | V-4 and V-2 fixes at slice execution seam |
| spectrum_systems/modules/runtime/pqx_sequential_loop.py | MODIFY | V-4, V-1, V-5 completion/run-id/trace-invariant hardening |
| spectrum_systems/modules/runtime/enforcement_engine.py | MODIFY | V-3 optional timestamp injection |
| tests/test_pqx_slice_runner.py | MODIFY | Regression tests for V-2 and V-4 behaviors |
| tests/test_pqx_sequential_loop.py | MODIFY | Regression tests for V-1, V-4, V-5 behaviors |
| tests/test_enforcement_engine.py | MODIFY | Regression tests for V-3 timestamp behavior |

## Invariants to preserve
- Fail-closed behavior for missing/invalid inputs.
- Deterministic control decisions and deterministic artifact identities.
- Explicit authority boundaries (runner executes, control/enforcement authorizes completion).
- Existing schema-first and post-emission validation patterns.
- Thin orchestration seams and pure helper functions.

## Risks
- State status transition changes can impact row selection behavior if not synchronized with existing resolver rules.
- Fixture mode hardening can break tests/fixtures that relied on implicit substring behavior.
- Run identity strictness can fail existing callers lacking explicit `run_id`.
- Trace invariant tightening can reject previously accepted blocked traces.

## Acceptance criteria
- Rows only transition to `complete` after enforcement ALLOW; blocked/review slices are not complete.
- Fixture decision logic is controlled only by explicit `fixture_decision_mode`; invalid mode fails closed.
- Blocked slices without `wrapper_ref` fail trace invariant validation.
- Missing explicit `run_id` in both context and wrapper fails closed.
- Enforcement result supports caller-supplied timestamp while preserving existing live-mode behavior.

## Test plan
1. `pytest tests/test_pqx_slice_runner.py`
2. `pytest tests/test_pqx_sequential_loop.py`
3. `pytest tests/test_enforcement_engine.py`
4. `pytest tests/test_contracts.py` (confirm unchanged contract surface still valid)
5. `pytest tests/test_module_architecture.py` (guard module-boundary integrity)
6. `.codex/skills/verify-changed-scope/run.sh` (changed-scope verification after BUILD)

## Non-goals
- No architectural redesign of PQX runtime/control loop.
- No new orchestration framework or cross-module refactor.
- No schema/version bump unless strictly required by implementation constraints.
- No expansion beyond V-4, V-2, V-1, V-5, and V-3 remediations.
