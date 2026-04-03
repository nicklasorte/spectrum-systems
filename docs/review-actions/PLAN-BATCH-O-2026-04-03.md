# Plan — BATCH-O — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-O — CTX Governed Context Pipeline (CTX-001..CTX-005)

## Objective
Implement a deterministic, schema-bound context pipeline that selects, ranks, injects, and lifecycles governed context for Codex/PQX execution using explicit contracts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-O-2026-04-03.md | CREATE | Required PLAN-first artifact for multi-file contract/module/test change. |
| contracts/schemas/context_bundle_v2.schema.json | CREATE | Define strict governed context bundle v2 contract. |
| contracts/examples/context_bundle_v2.json | CREATE | Golden-path example for context_bundle_v2 contract. |
| contracts/schemas/build_report.schema.json | CREATE | Minimal governed build_report artifact required for context input integration. |
| contracts/examples/build_report.json | CREATE | Golden-path example for build_report artifact. |
| contracts/schemas/next_slice_handoff.schema.json | CREATE | Minimal governed handoff artifact required for context input integration. |
| contracts/examples/next_slice_handoff.json | CREATE | Golden-path example for next_slice_handoff artifact. |
| contracts/standards-manifest.json | MODIFY | Publish contract versions and examples in canonical manifest. |
| spectrum_systems/modules/runtime/context_selector.py | CREATE | Implement deterministic context selection, ranking, and lifecycle management. |
| spectrum_systems/modules/runtime/context_injection.py | CREATE | Implement bounded/replayable context injection adapter for Codex/PQX. |
| spectrum_systems/modules/runtime/repo_process_flow_doc.py | MODIFY | Update process flow to include context selection/ranking/injection and authority boundary statement. |
| docs/runtime/context_bundle_v2.md | MODIFY | Document CTX ranking, injection contract, and lifecycle governance behavior. |
| tests/test_context_bundle_v2.py | MODIFY | Add contract validation and deterministic serialization checks for context_bundle_v2. |
| tests/test_context_selector.py | CREATE | Add deterministic selection/ranking/lifecycle integration tests. |
| tests/test_context_injection.py | CREATE | Add bounded injection and source-ref preservation tests. |
| tests/test_contracts.py | MODIFY | Validate new governed contract examples (context_bundle_v2/build_report/next_slice_handoff). |

## Contracts touched
- `context_bundle_v2` (new)
- `build_report` (new minimal governed artifact)
- `next_slice_handoff` (new minimal governed artifact)
- `contracts/standards-manifest.json` version bump + contract publication entries

## Tests that must pass after execution
1. `pytest tests/test_context_selector.py`
2. `pytest tests/test_context_bundle_v2.py`
3. `pytest tests/test_context_injection.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing `context_bundle` v2.3.0 contract semantics.
- Do not introduce memory-style long-term history retention.
- Do not add model-based or probabilistic ranking logic.
- Do not alter unrelated runtime control/certification enforcement modules.

## Dependencies
- Existing runtime contract loader and enforcement scripts remain authoritative and must continue to pass.
- Existing review/eval artifact contracts remain unchanged and are consumed as inputs only.
