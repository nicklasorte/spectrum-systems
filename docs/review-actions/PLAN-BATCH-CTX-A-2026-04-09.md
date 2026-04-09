# Plan — BATCH-CTX-A — 2026-04-09

## Prompt type
BUILD

## Roadmap item
BATCH-CTX-A

## Objective
Implement the first governed context foundation slice with strict ownership boundaries and fail-closed lineage enforcement for context-capability repo-mutating execution.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-CTX-A-2026-04-09.md | CREATE | Required plan-first artifact for multi-file change set. |
| contracts/schemas/context_bundle_record.schema.json | CREATE | Add canonical governed context bundle artifact contract. |
| contracts/schemas/context_source_admission_record.schema.json | CREATE | Add canonical source-level admission artifact contract for context inputs. |
| contracts/schemas/context_conflict_record.schema.json | CREATE | Add canonical context conflict artifact contract. |
| contracts/schemas/context_recipe_spec.schema.json | CREATE | Add canonical context recipe specification contract. |
| contracts/examples/context_bundle_record.json | CREATE | Golden valid example for context bundle record contract. |
| contracts/examples/context_source_admission_record.json | CREATE | Golden valid example for context source admission contract. |
| contracts/examples/context_conflict_record.json | CREATE | Golden valid example for context conflict contract. |
| contracts/examples/context_recipe_spec.json | CREATE | Golden valid example for context recipe contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract artifacts and bump standards manifest version metadata. |
| spectrum_systems/aex/classifier.py | MODIFY | Add deterministic context-capability request detection for admission classification. |
| spectrum_systems/aex/engine.py | MODIFY | Emit context-capability classification reason code and fail-closed handling while preserving AEX ownership. |
| spectrum_systems/modules/runtime/hnx_execution_state.py | MODIFY | Add HNX-owned context stage semantics and continuity validation helpers (no execution/policy logic). |
| spectrum_systems/modules/runtime/context_governed_flow.py | CREATE | Add narrow TLC routing, TPA admissibility evaluation, and PQX bounded context assembly execution path with lineage checks. |
| tests/test_context_governed_foundation.py | CREATE | Validate CTX-01..CTX-06 ownership boundaries, contracts, and fail-closed lineage behavior. |

## Scope exclusions
- No new subsystem creation.
- No SEL/CDE/FRE/RIL scope expansion.
- No runtime policy enforcement side effects outside deterministic artifact emission.
- No review-loop, closure, or promotion implementation.

## Validation commands
1. `pytest tests/test_context_governed_foundation.py`
2. `pytest tests/test_aex_admission.py tests/test_tlc_handoff_flow.py tests/test_pqx_required_context_enforcement.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
