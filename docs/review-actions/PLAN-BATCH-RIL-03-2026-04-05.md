# Plan — BATCH-RIL-03 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
RIL-003 — Review Signal Consumption Wiring

## Objective
Implement a deterministic, fail-closed review signal consumer that transforms `review_control_signal_artifact` into a bounded `review_integration_packet_artifact` for downstream control-loop, roadmap, and readiness intake without introducing enforcement or policy mutation.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RIL-03-2026-04-05.md | CREATE | Required PLAN artifact for multi-file BUILD scope. |
| contracts/schemas/review_integration_packet_artifact.schema.json | CREATE | Define authoritative contract for RIL-003 downstream integration packet. |
| contracts/examples/review_integration_packet_artifact.json | CREATE | Provide canonical golden-path example for the new contract. |
| contracts/standards-manifest.json | MODIFY | Register `review_integration_packet_artifact` and bump manifest version metadata. |
| spectrum_systems/modules/runtime/review_signal_consumer.py | CREATE | Implement deterministic RIL-003 packet generator from RIL-002 output. |
| tests/test_review_signal_consumer.py | CREATE | Validate routing, determinism, fail-closed behavior, traceability, and summary counts. |

## Contracts touched
- Create `review_integration_packet_artifact` schema at `contracts/schemas/review_integration_packet_artifact.schema.json` (v1.0.0).
- Update `contracts/standards-manifest.json` with new contract entry and version metadata bump.

## Tests that must pass after execution
1. `pytest tests/test_review_signal_consumer.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify RIL-001 extraction logic.
- Do not modify RIL-002 classification logic.
- Do not add direct enforcement actions, allow/block decisions, or policy mutation logic.
- Do not change unrelated contracts, modules, or tests outside declared files.

## Dependencies
- RIL-001 (`review_signal_artifact`) must remain contract-valid.
- RIL-002 (`review_control_signal_artifact`) must remain contract-valid and be treated as authoritative input.
