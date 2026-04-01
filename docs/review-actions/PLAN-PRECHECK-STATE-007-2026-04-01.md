# Plan — PRECHECK-STATE-007 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
PRECHECK-STATE-007

## Objective
Integrate contract preflight outcomes as a governed PQX input artifact with deterministic BLOCK/FREEZE/WARN/ALLOW mapping and observability propagation before execution decisions.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PRECHECK-STATE-007-2026-04-01.md | CREATE | Required PLAN artifact before multi-file contract + runtime changes. |
| contracts/schemas/contract_preflight_result_artifact.schema.json | CREATE | Governed artifact contract for preflight status/result consumed by PQX. |
| contracts/examples/contract_preflight_result_artifact.json | CREATE | Golden-path example for new governed preflight artifact. |
| contracts/examples/contract_preflight_result_artifact.example.json | CREATE | Golden-path fixture alias consumed by the golden-path-check skill. |
| contracts/standards-manifest.json | MODIFY | Register new governed artifact contract version and metadata. |
| scripts/run_contract_preflight.py | MODIFY | Emit governed preflight result artifact payload shape with required fields and provenance. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Ingest preflight artifact and enforce deterministic BLOCK/FREEZE/WARN/ALLOW semantics before execution output finalization. |
| tests/test_contracts.py | MODIFY | Validate new contract example and registration coverage. |
| tests/test_contract_preflight.py | MODIFY | Validate preflight script emits governed artifact fields/mapping metadata. |
| tests/test_pqx_slice_runner.py | MODIFY | Add PQX integration tests for pass/fail/masking/degraded preflight mappings. |

## Contracts touched
- Add `contract_preflight_result_artifact` schema.
- Update `contracts/standards-manifest.json` with new artifact + standards version bump.

## Tests that must pass after execution
1. `pytest tests/test_pqx_slice_runner.py tests/test_contract_preflight.py tests/test_contracts.py`
2. `pytest tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/golden-path-check/run.sh contract_preflight_result_artifact`

## Scope exclusions
- Do not refactor unrelated PQX queue/bundle orchestration modules.
- Do not modify roadmap authorities or strategy-control documents.
- Do not alter existing contract impact artifact semantics beyond preflight integration.

## Dependencies
- Existing G13 contract impact gate and G14 execution change impact gate must remain fail-closed and authoritative.
