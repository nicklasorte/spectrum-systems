# Plan — SYSTEM-LEVEL-REQUIRED-ID-ENFORCEMENT — 2026-03-29

## Prompt type
PLAN

## Roadmap item
Identity enforcement hardening (runtime fail-closed provenance boundary)

## Objective
Centralize required `run_id`/`trace_id` enforcement in runtime so artifact creation and validation paths fail closed when identity is missing.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/identity_enforcement.py | CREATE | Single source of truth for required ID injection and validation. |
| spectrum_systems/modules/runtime/__init__.py | MODIFY | Export runtime identity enforcement helpers. |
| spectrum_systems/modules/runtime/agent_golden_path.py | MODIFY | Enforce required IDs before schema checks and artifact emission in AG-01 creation path. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Enforce required IDs in replay artifact creation and validation seams. |
| spectrum_systems/modules/evaluation/eval_engine.py | MODIFY | Inject/validate required IDs for eval artifact creation path. |
| spectrum_systems/modules/evaluation/eval_coverage_reporting.py | MODIFY | Enforce required IDs at schema validation entrypoint used by coverage artifact builder. |
| spectrum_systems/modules/strategic_knowledge/validator.py | MODIFY | Add fail-closed required ID guard at strategic-knowledge validation entrypoint / registry-related validation flow. |
| tests/helpers/required_ids.py | MODIFY | Delegate test helper behavior to runtime identity enforcement module. |
| tests/test_identity_enforcement.py | CREATE | Add system-level regressions for runtime, determinism, mutation safety, replay→eval→certification propagation, and CLI coverage. |
| docs/contracts/identity_requirements.md | CREATE | Document run_id/trace_id definitions and fail-closed propagation rules. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_identity_enforcement.py tests/test_required_ids_enforced.py tests/test_eval_engine.py tests/test_replay_decision_engine.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_module_architecture.py`

## Scope exclusions
- Do not relax JSON schema required fields.
- Do not refactor unrelated runtime modules.
- Do not change contract version pins.

## Dependencies
- Existing contract schemas and examples remain authoritative inputs.
