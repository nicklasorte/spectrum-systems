# Plan — CONVERGENCE-025 Trust-Spine Invariants — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CONVERGENCE-025 — Trust-Spine Invariants + Cross-Seam Drift Detection Hardening

## Objective
Add deterministic, fail-closed cross-seam trust-spine invariant validation so promotion and certification block when replay/control/enforcement/coverage/gate-proof/closure semantics drift.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CONVERGENCE-025-TRUST-SPINE-INVARIANTS-2026-04-01.md | CREATE | Required BUILD plan artifact for this slice. |
| PLANS.md | MODIFY | Register CONVERGENCE-025 plan. |
| spectrum_systems/modules/runtime/trust_spine_invariants.py | CREATE | Centralized reusable cross-seam invariant validator helpers. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Enforce invariant validation on active promotion authority seam. |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Enforce invariant validation on certification trust spine and emit invariant results. |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Add governed machine-readable invariant signal fields in done certification artifact. |
| contracts/examples/done_certification_record.json | MODIFY | Keep canonical example aligned to updated done certification schema. |
| contracts/standards-manifest.json | MODIFY | Version bump and contract version pin update for done_certification_record schema update. |
| tests/test_sequence_transition_policy.py | MODIFY | Add contradiction-path and invariant-blocking promotion tests. |
| tests/test_done_certification.py | MODIFY | Add certification invariant regression tests and machine-readable result assertions. |

## Contracts touched
- `contracts/schemas/done_certification_record.schema.json` (additive schema update + version bump)
- `contracts/standards-manifest.json` (schema version pin + manifest version update)

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_control.py tests/test_sequence_transition_policy.py tests/test_cycle_runner.py tests/test_policy_backtesting.py tests/test_policy_backtest_accuracy.py tests/test_policy_enforcement_integrity.py tests/test_end_to_end_failure_simulation.py tests/test_control_loop_certification.py tests/test_enforcement_engine.py`
2. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
3. `pytest -q tests/test_done_certification.py`
4. `python scripts/run_contract_enforcement.py`
5. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight_convergence_025 --changed-path spectrum_systems/modules/runtime/trust_spine_invariants.py --changed-path spectrum_systems/modules/governance/done_certification.py --changed-path spectrum_systems/orchestration/sequence_transition_policy.py --changed-path contracts/schemas/done_certification_record.schema.json --changed-path contracts/examples/done_certification_record.json --changed-path contracts/standards-manifest.json --changed-path tests/test_sequence_transition_policy.py --changed-path tests/test_done_certification.py`
6. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-CONVERGENCE-025-TRUST-SPINE-INVARIANTS-2026-04-01.md' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign sequence states, cycle runner architecture, or certification workflow topology.
- Do not loosen any existing schema constraints or add permissive fallback logic.
- Do not alter active-runtime vs comparative-analysis semantics in evaluation control.
- Do not introduce new external dependencies.

## Dependencies
- CONVERGENCE-024 threshold context separation and gate-proof hardening must remain intact.
- Existing replay/enforcement/promotion/certification contracts and fixtures remain authoritative inputs.

## Explicit hardening stance
This is a surgical hardening slice, not an architecture redesign.
