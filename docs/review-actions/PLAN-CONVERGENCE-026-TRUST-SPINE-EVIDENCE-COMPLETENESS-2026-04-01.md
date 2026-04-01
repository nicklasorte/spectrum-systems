# Plan — CONVERGENCE-026 Trust-Spine Evidence Completeness — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CONVERGENCE-026 — Trust-Spine Evidence Completeness

## Objective
Add a deterministic fail-closed trust-spine evidence completeness validator and enforce it on promotion and done-certification authority paths so incomplete active authority evidence is always blocked with machine-readable reasons.

## Declared files
List every file that will be created, modified, or deleted. No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CONVERGENCE-026-TRUST-SPINE-EVIDENCE-COMPLETENESS-2026-04-01.md | CREATE | Required plan-first artifact for this slice. |
| PLANS.md | MODIFY | Register CONVERGENCE-026 plan in active plans table. |
| spectrum_systems/modules/runtime/trust_spine_invariants.py | MODIFY | Add centralized deterministic trust-spine evidence completeness validator and reason codes. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Wire promotion authority path to completeness validator and fail-closed gating. |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Wire active authority certification path to completeness validator and emit machine-readable result. |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Add schema-enforced machine-readable completeness result surfaces. |
| contracts/examples/done_certification_record.json | MODIFY | Keep canonical example aligned with updated schema/result shape. |
| contracts/standards-manifest.json | MODIFY | Bump done_certification_record schema version and manifest standards version pin. |
| tests/test_sequence_transition_policy.py | MODIFY | Add/update promotion completeness regression coverage. |
| tests/test_done_certification.py | MODIFY | Add/update done-certification completeness regression coverage. |

## Contracts touched
- `contracts/schemas/done_certification_record.schema.json` (additive shape extension)
- `contracts/standards-manifest.json` version pin updates for `done_certification_record`

## Tests that must pass after execution
1. `pytest -q tests/test_sequence_transition_policy.py tests/test_done_certification.py`
2. `pytest -q tests/test_control_loop_certification.py tests/test_cycle_runner.py tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight_convergence_026 --changed-path spectrum_systems/modules/runtime/trust_spine_invariants.py --changed-path spectrum_systems/orchestration/sequence_transition_policy.py --changed-path spectrum_systems/modules/governance/done_certification.py --changed-path contracts/schemas/done_certification_record.schema.json --changed-path contracts/examples/done_certification_record.json --changed-path contracts/standards-manifest.json --changed-path tests/test_sequence_transition_policy.py --changed-path tests/test_done_certification.py`
5. `PLAN_FILES="docs/review-actions/PLAN-CONVERGENCE-026-TRUST-SPINE-EVIDENCE-COMPLETENESS-2026-04-01.md PLANS.md spectrum_systems/modules/runtime/trust_spine_invariants.py spectrum_systems/orchestration/sequence_transition_policy.py spectrum_systems/modules/governance/done_certification.py contracts/schemas/done_certification_record.schema.json contracts/examples/done_certification_record.json contracts/standards-manifest.json tests/test_sequence_transition_policy.py tests/test_done_certification.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign trust-spine invariant semantics outside completeness gating.
- Do not change non-target contracts or unrelated module interfaces.
- Do not introduce new orchestration modules or alter unrelated sequence states.
- Do not modify tests beyond targeted regression coverage for this slice.

## Dependencies
- CONVERGENCE-025 trust-spine invariant baseline must remain intact; this slice extends it with completeness gating.
