# Plan — SLH-001-INTEGRATION-001 — 2026-04-17

## Prompt type
PLAN

## Roadmap item
SLH-001 integration and enforcement completion

## Objective
Make SLH-001 the mandatory execution front door by enforcing pre-pytest gating, fail-closed coverage auditing, deterministic remediation hints, and targeted rerun routing.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SLH-001-INTEGRATION-001-2026-04-17.md | CREATE | Required multi-file execution plan before integration work |
| scripts/run_shift_left_preflight.py | CREATE | Mandatory pre-pytest wrapper entrypoint for SLH gating and rerun enforcement |
| scripts/run_shift_left_entrypoint_coverage_audit.py | CREATE | Coverage and bypass audit for pytest/entrypoint paths |
| spectrum_systems/modules/runtime/shift_left_hardening_superlayer.py | MODIFY | Add remediation hints, fail-open/bypass detection, rerun routing helpers, and reason-code hardening helpers |
| tests/test_shift_left_hardening_superlayer.py | MODIFY | Validate deterministic remediation and reason/routing enforcement behavior |
| tests/test_shift_left_preflight.py | CREATE | Validate wrapper enforcement, blocking behavior, and targeted rerun guard |
| contracts/schemas/fre_shift_left_remediation_hint_record.schema.json | CREATE | Canonical remediation artifact schema for SLH failures |
| contracts/examples/fre_shift_left_remediation_hint_record.json | CREATE | Canonical contract example for remediation hint artifact |
| contracts/standards-manifest.json | MODIFY | Register remediation hint contract in canonical manifest |
| docs/reviews/SLH-001-INTEGRATION-001_delivery_report.md | CREATE | Delivery report documenting enforcement, fixed gaps, and residual risk |

## Contracts touched
- Add `fre_shift_left_remediation_hint_record` schema and example.
- Update `contracts/standards-manifest.json` for canonical registration.

## Tests that must pass after execution
1. `pytest tests/test_shift_left_hardening_superlayer.py -q`
2. `pytest tests/test_shift_left_preflight.py -q`
3. `python scripts/run_shift_left_entrypoint_coverage_audit.py`

## Scope exclusions
- Do not redesign SLH architecture beyond integration/enforcement requirements.
- Do not refactor unrelated runtime modules.
- Do not remove or disable existing tests.

## Dependencies
- Existing `scripts/run_shift_left_hardening_superlayer.py` and `spectrum_systems.modules.runtime.shift_left_hardening_superlayer` baseline must remain canonical.
