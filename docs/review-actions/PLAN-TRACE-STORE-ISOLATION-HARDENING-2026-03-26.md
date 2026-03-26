# Plan — TRACE-STORE-ISOLATION-HARDENING — 2026-03-26

## Prompt type
PLAN

## Roadmap item
system_roadmap.md active execution context — runtime hardening narrow slice

## Objective
Harden the governed failure injection trace path so injected trace stores remain isolated from the global trace store, with deterministic regression tests and a CI gate.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-TRACE-STORE-ISOLATION-HARDENING-2026-03-26.md | CREATE | Required PLAN artifact for multi-file hardening slice |
| PLANS.md | MODIFY | Register the new active plan entry |
| spectrum_systems/modules/runtime/trace_engine.py | MODIFY | Thread optional injected store through thin helper seams to remove hidden global coupling |
| tests/test_trace_engine.py | MODIFY | Add regression coverage for injected-store isolation and mixed global/injected execution |
| tests/test_governed_failure_injection.py | MODIFY | Add end-to-end isolation regression checks for governed failure injection |
| .github/workflows/lifecycle-enforcement.yml | MODIFY | Add dedicated CI regression gate for governed failure injection |
| docs/runtime/trace-state-isolation.md | CREATE | Document invariant and usage guidance for default vs injected trace stores |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_trace_engine.py -q`
2. `pytest tests/test_governed_failure_injection.py -q`
3. `python scripts/run_governed_failure_injection.py --output-dir outputs/governed_failure_injection`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign trace architecture or introduce new registries/subsystems.
- Do not change control-loop runtime semantics.
- Do not add network, async, or LLM behaviors.
- Do not widen changes beyond audited trace-store coupling, regression tests, CI wiring, and short developer note.

## Dependencies
- Existing governed_failure_injection isolation behavior must remain intact while hardening helper seams.
