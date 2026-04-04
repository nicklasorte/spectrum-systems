# Plan — BATCH-HANDOFF-MEMORY — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-HANDOFF-MEMORY — Batch Delivery + Handoff Memory

## Objective
Add governed batch delivery/handoff memory contracts and deterministic runtime wiring so each new governed batch auto-ingests the latest valid prior handoff bundle and uses it for safe continuation decisions.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-HANDOFF-MEMORY-2026-04-04.md | CREATE | Required PLAN artifact before multi-file/schema work |
| PLANS.md | MODIFY | Register active plan |
| contracts/schemas/batch_delivery_report.schema.json | CREATE | New governed delivery artifact contract |
| contracts/schemas/batch_handoff_bundle.schema.json | CREATE | New governed prior-batch carry-forward contract |
| contracts/examples/batch_delivery_report.json | CREATE | Golden-path example for delivery report contract |
| contracts/examples/batch_handoff_bundle.json | CREATE | Golden-path example for handoff bundle contract |
| contracts/standards-manifest.json | MODIFY | Register both contracts and bump manifest version metadata |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Emit delivery report, derive handoff bundle, auto-load prior handoff, propagate governed signals |
| tests/test_contracts.py | MODIFY | Add contract example validation coverage for new artifacts |
| tests/test_roadmap_selector.py | MODIFY | Add selector-bias and unsafe-block coverage driven by handoff signals |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add deterministic handoff derivation + stale cleanup coverage |
| tests/test_system_cycle_operator.py | MODIFY | Add prior-handoff auto-ingestion, fail-closed malformed handling, and required validation propagation coverage |

## Contracts touched
- Create `batch_delivery_report` schema (version 1.0.0)
- Create `batch_handoff_bundle` schema (version 1.0.0)
- Update `contracts/standards-manifest.json` version and contract registry entries

## Tests that must pass after execution
1. `pytest tests/test_roadmap_selector.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_system_cycle_operator.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `pytest`
8. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign roadmap execution architecture.
- Do not add autonomous execution modes outside existing governed selection/execution path.
- Do not change unrelated contracts, modules, or tests beyond batch handoff memory wiring.

## Dependencies
- Existing RDX/BATCH-U governed roadmap execution path must remain authoritative and unchanged in control ownership.
