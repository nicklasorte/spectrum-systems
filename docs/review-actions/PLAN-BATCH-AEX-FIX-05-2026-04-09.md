# Plan — BATCH-AEX-FIX-05 — 2026-04-09

## Prompt type
PLAN

## Roadmap item
BATCH-AEX-FIX-05

## Objective
Harden repo-write lineage trust validation so forged, stale, issuer-mismatched, or replayed lineage is rejected fail-closed at the PQX boundary.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/lineage_authenticity.py | MODIFY | Remove default secret fallback, enforce issuer-scoped key resolution, and add freshness fields/signing helpers. |
| spectrum_systems/modules/runtime/repo_write_lineage_guard.py | MODIFY | Strengthen authoritative repo-write validator with issuer/key binding, freshness checks, and replay rejection. |
| spectrum_systems/modules/runtime/*.py | MODIFY (targeted) | Update lineage emitters (`build_admission_record`, `normalized_execution_request`, `tlc_handoff_record`) to emit new authenticity fields through a shared helper. |
| contracts/schemas/build_admission_record.schema.json | MODIFY | Require new authenticity fields and strict shape for updated trust model. |
| contracts/schemas/normalized_execution_request.schema.json | MODIFY | Require new authenticity fields and strict shape for updated trust model. |
| contracts/schemas/tlc_handoff_record.schema.json | MODIFY | Require new authenticity fields and strict shape for updated trust model. |
| contracts/examples/*.json | MODIFY (if present for changed contracts) | Keep examples aligned with contract requirements. |
| tests/test_*lineage*.py | MODIFY | Add adversarial regression coverage for missing secret, issuer mismatch, forgery, freshness, and replay. |
| tests/test_*pqx*.py | MODIFY | Add boundary-level forged-lineage rejection coverage through public caller path. |
| docs/architecture/foundation_pqx_eval_control.md | MODIFY | Minimal truthfulness update about issuer-scoped authenticity and replay rejection. |

## Contracts touched
- `build_admission_record.schema.json`
- `normalized_execution_request.schema.json`
- `tlc_handoff_record.schema.json`
- `contracts/standards-manifest.json` (version bumps for touched contract versions)

## Tests that must pass after execution
1. `pytest tests/test_repo_write_lineage_guard.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `pytest` (targeted boundary/runtime tests impacted by lineage guard updates)

## Scope exclusions
- Do not introduce external KMS, PKI, or distributed trust frameworks.
- Do not redesign PQX architecture or broaden authorization model.
- Do not duplicate repo-write validation logic outside the authoritative validator.
- Do not modify unrelated governance or roadmap artifacts.

## Dependencies
- Existing AEX lineage authenticity and repo-write guard paths remain the integration seam.
