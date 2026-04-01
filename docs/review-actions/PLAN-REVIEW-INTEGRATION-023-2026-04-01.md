# Plan — REVIEW-INTEGRATION-023 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
REVIEW-INTEGRATION-023 — Review-as-Control-Signal Integration

## Objective
Convert review markdown artifacts into deterministic governed review control signals that are consumed by control decisions, promotion gating, PQX admission, and roadmap eligibility in a fail-closed manner.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-REVIEW-INTEGRATION-023-2026-04-01.md | CREATE | Required plan-first artifact for this multi-file governance/control wiring slice |
| spectrum_systems/modules/runtime/review_signal_extractor.py | CREATE | Implement deterministic markdown-to-structured review signal extraction |
| contracts/schemas/review_control_signal.schema.json | CREATE | Governed artifact contract for extracted review control signals |
| contracts/examples/review_control_signal.json | CREATE | Golden-path example payload for the new artifact contract |
| contracts/standards-manifest.json | MODIFY | Register review_control_signal schema version and example path |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Consume review_control_signal in evaluation control decisions with fail-closed semantics |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Enforce review-driven promotion gating and expansion blocking |
| spectrum_systems/modules/runtime/pqx_n_slice_validation.py | MODIFY | Fail-closed PQX admission when required review signal is missing/failed |
| contracts/schemas/governed_roadmap_artifact.schema.json | MODIFY | Allow optional review signal inputs for roadmap feedback wiring |
| spectrum_systems/orchestration/roadmap_eligibility.py | MODIFY | Consume review signals and critical findings in next-step eligibility/blocking |
| tests/test_review_signal_extractor.py | CREATE | Validate markdown extraction, malformed fail-close, and deterministic signal generation |
| tests/test_sequence_transition_policy.py | MODIFY | Validate FAIL/NO review gating blocks promotion and expansion transitions |
| tests/test_pqx_n_slice_validation.py | MODIFY | Validate PQX admission behavior with review signal requirements |
| tests/test_roadmap_eligibility.py | MODIFY | Validate roadmap feedback loop consumption of review signals and critical findings |
| tests/test_contracts.py | MODIFY | Validate new review_control_signal example against contract |

## Contracts touched
- `contracts/schemas/review_control_signal.schema.json` (new)
- `contracts/schemas/governed_roadmap_artifact.schema.json` (add review signal input fields)
- `contracts/standards-manifest.json` (new contract registration)

## Tests that must pass after execution
1. `pytest tests/test_review_signal_extractor.py tests/test_sequence_transition_policy.py tests/test_pqx_n_slice_validation.py tests/test_roadmap_eligibility.py tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing control decision model beyond review signal consumption wiring.
- Do not add new execution states beyond minimally required review/expansion gating checks.
- Do not refactor unrelated roadmap, PQX, or prompt-queue modules.

## Dependencies
- Existing evaluation control + sequence transition policy remain authoritative control surfaces.
- Existing docs/reviews markdown artifacts remain source inputs for extraction.
