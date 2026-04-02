# Plan — CON-038 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-038 — Codex-to-PQX Task Wrapper

## Objective
Add a deterministic repo-native Codex-to-PQX wrapper contract, builder module, and thin CLI that fail closed on malformed or non-authoritative governed inputs while remaining compatible with existing PQX ingestion seams.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-038-CODEX-TO-PQX-TASK-WRAPPER-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file implementation slice. |
| PLANS.md | MODIFY | Register this plan in the active plans table per repo policy. |
| contracts/schemas/codex_pqx_task_wrapper.schema.json | CREATE | Canonical schema-backed wrapper contract for Codex intent to PQX task translation. |
| contracts/examples/codex_pqx_task_wrapper.json | CREATE | Golden-path deterministic example payload for the new wrapper contract. |
| contracts/standards-manifest.json | MODIFY | Register and version-pin the new wrapper contract in the canonical manifest. |
| spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py | CREATE | Pure wrapper module that validates normalized inputs and builds deterministic wrapper payloads. |
| scripts/run_codex_to_pqx_wrapper.py | CREATE | Thin CLI entrypoint for wrapper creation and optional PQX seam execution. |
| tests/test_codex_to_pqx_wrapper.py | CREATE | Focused tests for governed/non-governed wrapper behavior, fail-closed semantics, determinism, CLI behavior, and seam compatibility. |
| tests/test_contracts.py | MODIFY | Add contract validation coverage for the new wrapper example. |

## Contracts touched
- CREATE `contracts/schemas/codex_pqx_task_wrapper.schema.json`
- MODIFY `contracts/standards-manifest.json` (register new contract and bump manifest version)

## Tests that must pass after execution

1. `pytest -q tests/test_codex_to_pqx_wrapper.py`
2. `pytest -q tests/test_pqx_slice_runner.py`
3. `pytest -q tests/test_contract_preflight.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/run_contract_preflight.py --changed-path contracts/schemas/codex_pqx_task_wrapper.schema.json --changed-path contracts/examples/codex_pqx_task_wrapper.json --changed-path contracts/standards-manifest.json --changed-path spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py --changed-path scripts/run_codex_to_pqx_wrapper.py --changed-path tests/test_codex_to_pqx_wrapper.py --changed-path tests/test_contracts.py`
8. `python scripts/run_codex_to_pqx_wrapper.py --task-id con-038-golden --step-id AI-01 --step-name "Golden path" --prompt "Implement CON-038" --execution-context exploration --changed-path docs/vision.md --output-path /tmp/con-038-wrapper.json`
9. `python scripts/run_codex_to_pqx_wrapper.py --task-id con-038-governed-missing-auth --step-id AI-01 --step-name "Fail closed" --prompt "Governed run" --execution-context pqx_governed --changed-path contracts/schemas/pqx_execution_request.schema.json`
10. `PLAN_FILES="docs/review-actions/PLAN-CON-038-CODEX-TO-PQX-TASK-WRAPPER-2026-04-02.md PLANS.md contracts/schemas/codex_pqx_task_wrapper.schema.json contracts/examples/codex_pqx_task_wrapper.json contracts/standards-manifest.json spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py scripts/run_codex_to_pqx_wrapper.py tests/test_codex_to_pqx_wrapper.py tests/test_contracts.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions

- Do not redesign or refactor core PQX runner/orchestration architecture.
- Do not broaden this into a generic agent framework or scheduler.
- Do not add heuristic governance posture inference from free text.
- Do not weaken existing CON-036/CON-037 fail-closed boundaries.

## Dependencies

- CON-036 default PQX execution path is active.
- CON-037 governed authority/context policy seam is available for deterministic enforcement.
