# Plan — CON-039-FIX — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-039 FIX — Schema-backed preflight artifact support for PQX required-context enforcement

## Objective
Complete CON-039 by extending the authoritative contract_preflight_result_artifact schema/example and wiring so PQX required-context enforcement is first-class machine-readable artifact data consumed consistently by gating outcomes.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-039-FIX-SCHEMA-BACKED-PREFLIGHT-REQUIRED-CONTEXT-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file contract-completion fix. |
| PLANS.md | MODIFY | Register this fix plan in active plans table. |
| contracts/schemas/contract_preflight_result_artifact.schema.json | MODIFY | Add schema-backed required-context enforcement object and bump schema version for artifact contract authority. |
| contracts/examples/contract_preflight_result_artifact.json | MODIFY | Update canonical preflight artifact example with required-context enforcement payload. |
| contracts/examples/contract_preflight_result_artifact.example.json | MODIFY | Keep example-suffix companion aligned with canonical preflight artifact schema fields. |
| contracts/standards-manifest.json | MODIFY | Version bump + updated contract entry reflecting schema evolution. |
| scripts/run_contract_preflight.py | MODIFY | Populate required-context enforcement into authoritative preflight artifact output. |
| tests/test_contract_preflight.py | MODIFY | Add coverage for artifact-level required-context allow/block semantics and CI-style base/head path coherence. |
| tests/test_contracts.py | MODIFY | Assert updated preflight artifact examples validate against evolved schema. |
| tests/test_pqx_slice_runner.py | MODIFY | Keep preflight artifact test fixtures contract-valid after schema evolution. |

## Contracts touched
- MODIFY `contracts/schemas/contract_preflight_result_artifact.schema.json`
- MODIFY `contracts/standards-manifest.json` (version bump and contract metadata update)

## Tests that must pass after execution

1. `pytest -q tests/test_contract_preflight.py`
2. `pytest -q tests/test_contracts.py`
3. `pytest -q tests/test_contract_enforcement.py`
4. `pytest -q tests/test_pqx_slice_runner.py`
5. `python scripts/run_contract_enforcement.py`
6. `python scripts/run_contract_preflight.py --execution-context pqx_governed --pqx-wrapper-path /tmp/con039-fix-wrapper.json --authority-evidence-ref data/pqx_runs/AI-01/example.pqx_slice_execution_record.json --changed-path contracts/schemas/contract_preflight_result_artifact.schema.json --changed-path contracts/examples/contract_preflight_result_artifact.json --changed-path contracts/examples/contract_preflight_result_artifact.example.json --changed-path contracts/standards-manifest.json --changed-path scripts/run_contract_preflight.py --changed-path tests/test_contract_preflight.py --changed-path tests/test_contracts.py --changed-path tests/test_pqx_slice_runner.py`
7. `python scripts/run_contract_preflight.py --base-ref origin/main --head-ref HEAD --execution-context pqx_governed --pqx-wrapper-path /tmp/con039-fix-wrapper.json --authority-evidence-ref data/pqx_runs/AI-01/example.pqx_slice_execution_record.json`
8. `PLAN_FILES="docs/review-actions/PLAN-CON-039-FIX-SCHEMA-BACKED-PREFLIGHT-REQUIRED-CONTEXT-2026-04-02.md PLANS.md contracts/schemas/contract_preflight_result_artifact.schema.json contracts/examples/contract_preflight_result_artifact.json contracts/examples/contract_preflight_result_artifact.example.json contracts/standards-manifest.json scripts/run_contract_preflight.py tests/test_contract_preflight.py tests/test_contracts.py tests/test_pqx_slice_runner.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions

- Do not redesign PQX policy or wrapper model.
- Do not weaken fail-closed enforcement semantics.
- Do not add report-only fields without schema-backed artifact representation.
- Do not introduce new ontologies or alternate artifact families.

## Dependencies

- CON-039 enforcement logic module and preflight/report wiring already exist.
- CON-038 codex_pqx_task_wrapper contract remains the canonical wrapper shape.
