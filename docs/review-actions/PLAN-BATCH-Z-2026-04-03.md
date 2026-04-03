# Plan — BATCH-Z — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-Z

## Objective
Add a governed cross-layer integration validator and contract surface proving deterministic, fail-closed coherence across PRG/RVW/CTX/TPA/MAP-RDX/control-certification interactions.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-Z-2026-04-03.md | CREATE | Required plan-first artifact for this multi-file contract+module change. |
| PLANS.md | MODIFY | Register active BATCH-Z plan entry. |
| spectrum_systems/modules/runtime/system_integration_validator.py | CREATE | Implement cross-layer integration validation and fail-closed probes. |
| contracts/schemas/core_system_integration_validation.schema.json | CREATE | Governed contract for integration validation artifact output. |
| contracts/examples/core_system_integration_validation.json | CREATE | Golden-path example for the new integration validation artifact. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version metadata. |
| tests/test_system_integration_validator.py | CREATE | Determinism, authority-boundary, replayability, and failure-probe coverage for the validator. |
| spectrum_systems/modules/runtime/repo_process_flow_doc.py | MODIFY | Document full integrated machine flow across program/review/context/TPA/roadmap/control layers. |
| docs/reviews/repo_process_flow.md | MODIFY | Refresh maintained process-flow document with integrated layer ordering and controls. |

## Contracts touched
- `core_system_integration_validation` (new contract)
- `contracts/standards-manifest.json` (new registration + version bump)

## Tests that must pass after execution
1. `pytest tests/test_system_integration_validator.py`
2. `pytest tests/test_program_layer.py`
3. `pytest tests/test_review_signal_extractor.py`
4. `pytest tests/test_review_eval_bridge.py`
5. `pytest tests/test_context_selector.py`
6. `pytest tests/test_tpa_sequence_runner.py`
7. `pytest tests/test_roadmap_execution_loop_validator.py`
8. `pytest tests/test_roadmap_multi_batch_executor.py`
9. `pytest tests/test_contracts.py`
10. `pytest tests/test_contract_enforcement.py`
11. `python scripts/run_contract_enforcement.py`
12. `python scripts/run_contract_preflight.py --base-ref "HEAD~1" --head-ref "HEAD" --output-dir outputs/contract_preflight`

## Scope exclusions
- Do not redesign existing roadmap/control architecture.
- Do not add new execution subsystems.
- Do not refactor unrelated modules/tests/contracts outside declared files.

## Dependencies
- Existing BATCH-M and BATCH-O PRG/RVW/CTX/TPA/MAP/RDX modules and contracts must remain authoritative inputs.
