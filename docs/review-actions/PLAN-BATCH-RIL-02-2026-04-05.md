# Plan — BATCH-RIL-02 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
RIL-002 — Review Signal Classification Engine

## Objective
Implement a deterministic, fail-closed Review Signal Classification Engine that maps `review_signal_artifact` inputs into schema-backed `review_control_signal_artifact` outputs with full source traceability.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RIL-02-2026-04-05.md | CREATE | Required PLAN artifact for this multi-file + contract-first implementation slice. |
| contracts/schemas/review_control_signal_artifact.schema.json | CREATE | Canonical JSON Schema for RIL-002 output artifact. |
| contracts/examples/review_control_signal_artifact.json | CREATE | Golden-path deterministic example for the new artifact contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version metadata. |
| spectrum_systems/modules/runtime/review_signal_classifier.py | CREATE | Deterministic classification engine implementation. |
| tests/test_review_signal_classifier.py | CREATE | Deterministic unit coverage for mapping rules, fail-closed behavior, and traceability. |

## Contracts touched
- Create `review_control_signal_artifact` contract at schema version `1.0.0`.
- Update `contracts/standards-manifest.json` with new contract entry and manifest version bump.

## Tests that must pass after execution
1. `pytest tests/test_review_signal_classifier.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not modify `review_signal_artifact` schema fields or parser behavior.
- Do not introduce policy enforcement actions or runtime side effects.
- Do not refactor unrelated runtime modules or tests.

## Dependencies
- RIL-001 review signal extraction artifacts and schema must remain authoritative input surface.
