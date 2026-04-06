# Plan — BATCH-RIL-05 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-RIL-05 (RIL-005)

## Objective
Implement a deterministic fail-closed RIL-005 consumer wiring/validation layer that consumes only RIL-004 projection artifacts, emits bounded read-only consumer intake artifacts, and closes required RIL hardening items (RIL-ARCH-01 and RIL-ARCH-02, plus explicit non-authoritative language).

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RIL-05-2026-04-05.md | CREATE | Required plan-first declaration for this multi-file BUILD slice. |
| PLANS.md | MODIFY | Register this active plan in the repository plan index. |
| contracts/schemas/review_consumer_output_bundle_artifact.schema.json | CREATE | New RIL-005 top-level consumer output bundle contract. |
| contracts/schemas/roadmap_review_view_artifact.schema.json | CREATE | New RIL-005 roadmap read-only consumer view contract. |
| contracts/schemas/control_loop_review_queue_record_artifact.schema.json | CREATE | New RIL-005 control-loop queue record contract. |
| contracts/schemas/readiness_review_dashboard_artifact.schema.json | CREATE | New RIL-005 readiness dashboard contract. |
| contracts/schemas/review_consumption_validation_artifact.schema.json | CREATE | New RIL-005 projection-boundary/read-only validation contract. |
| contracts/schemas/review_projection_bundle_artifact.schema.json | MODIFY | RIL-ARCH-01 hardening: strongly type nested projection objects. |
| contracts/examples/review_consumer_output_bundle_artifact.json | CREATE | Golden-path example for output bundle contract. |
| contracts/examples/roadmap_review_view_artifact.json | CREATE | Golden-path example for roadmap consumer-view contract. |
| contracts/examples/control_loop_review_queue_record_artifact.json | CREATE | Golden-path example for control-loop queue record contract. |
| contracts/examples/readiness_review_dashboard_artifact.json | CREATE | Golden-path example for readiness dashboard contract. |
| contracts/examples/review_consumption_validation_artifact.json | CREATE | Golden-path example for projection-boundary validation contract. |
| contracts/standards-manifest.json | MODIFY | Register new RIL-005 contracts and update contract metadata versions. |
| spectrum_systems/modules/runtime/review_consumer_wiring.py | CREATE | Implement deterministic fail-closed RIL-005 consumer wiring builder. |
| spectrum_systems/modules/runtime/review_parsing_engine.py | MODIFY | RIL-ARCH-02 hardening: runtime schema validation before parser return. |
| tests/test_review_consumer_wiring.py | CREATE | RIL-005 module tests for routing boundary, read-only behavior, determinism, and fail-closed handling. |
| tests/test_review_parsing_engine.py | MODIFY | Add hardening test asserting parser rejects schema-invalid outputs via runtime validation. |
| tests/test_review_projection_adapter.py | MODIFY | Add hardening test for strongly typed nested projections in projection bundle schema. |

## Contracts touched
- Create `review_consumer_output_bundle_artifact` schema (1.0.0).
- Create `roadmap_review_view_artifact` schema (1.0.0).
- Create `control_loop_review_queue_record_artifact` schema (1.0.0).
- Create `readiness_review_dashboard_artifact` schema (1.0.0).
- Create `review_consumption_validation_artifact` schema (1.0.0).
- Modify `review_projection_bundle_artifact` schema (1.1.0) to type nested projections.
- Update `contracts/standards-manifest.json` registrations and version metadata.

## Tests that must pass after execution
1. `pytest tests/test_review_consumer_wiring.py`
2. `pytest tests/test_review_projection_adapter.py tests/test_review_parsing_engine.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add enforcement decision logic.
- Do not add policy mutation/reprioritization behavior.
- Do not consume raw review markdown or pre-RIL-04 artifacts in RIL-005 runtime wiring.
- Do not refactor unrelated runtime modules or contracts.

## Dependencies
- RIL-004 projection contracts and module outputs must remain the sole intake boundary for this slice.
