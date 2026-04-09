# Plan — BATCH-GOV-A-FIX-02 — 2026-04-09

## Prompt type
BUILD

## Scope
Surgical trust-boundary correction so TPA gate authority is derived only from verified TPA issuance authenticity and request binding, with fail-closed PQX boundary enforcement.

## Files in scope
| File | Action | Purpose |
| --- | --- | --- |
| `spectrum_systems/modules/runtime/lineage_authenticity.py` | MODIFY | Add TPA issuer support and issuance authority binding for `tpa_slice_artifact`. |
| `spectrum_systems/modules/runtime/pqx_sequence_runner.py` | MODIFY | Emit `authenticity` on canonical TPA slice artifacts. |
| `spectrum_systems/modules/review_fix_execution_loop.py` | MODIFY | Replace forgeable local-file/token authority check with authenticity + payload/request binding validation. |
| `contracts/schemas/tpa_slice_artifact.schema.json` | MODIFY | Require authenticity object on TPA slice artifact contract. |
| `contracts/examples/tpa_slice_artifact.json` | MODIFY | Update golden example to include authenticity. |
| `contracts/examples/review_fix_execution_request_artifact.json` | MODIFY | Update embedded TPA gate artifact to include authenticity. |
| `contracts/standards-manifest.json` | MODIFY | Version bump for additive schema change. |
| `tests/test_review_fix_execution_loop.py` | MODIFY | Add adversarial tests for forged/fake/valid TPA authority at gate boundary. |
| `tests/test_pqx_fix_execution.py` | MODIFY | Update fixtures/helpers to provide authentic TPA artifact issuance instead of token file authority. |
| `tests/test_pqx_bundle_orchestrator.py` | MODIFY | Update boundary test setup for authentic TPA gate artifacts and forged rejection behavior. |
| `tests/test_contracts.py` | MODIFY (if needed) | Keep contract/example expectations aligned with schema updates. |
| `docs/governance/*` (single minimal note file) | ADD | Minimal governance note that file/token are audit-only and non-authoritative. |

## Constraints
- No redesign of GOV-A flow.
- No new subsystem introduction.
- Fail-closed preserved for all mismatches.
- No duplicate validation paths.

## Validation
1. `pytest -q tests/test_review_fix_execution_loop.py`
2. `pytest -q tests/test_pqx_fix_execution.py`
3. `pytest -q tests/test_pqx_bundle_orchestrator.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
