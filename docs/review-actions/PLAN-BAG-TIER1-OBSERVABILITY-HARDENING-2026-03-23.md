# Plan — BAG Tier-1 Observability Hardening — 2026-03-23

## Prompt type
PLAN

## Roadmap item
Prompt BAG — Replay Engine + governed runtime observability hardening

## Objective
Make governed runtime/replay execution fail closed on observability emission failures, enforce mandatory correlation keys, remove governed legacy replay schema acceptance, and harden deterministic event vocabulary and persistence behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAG-TIER1-OBSERVABILITY-HARDENING-2026-03-23.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| spectrum_systems/modules/runtime/control_chain.py | MODIFY | Remove silent observability drops and block governed execution on emission failure. |
| spectrum_systems/modules/runtime/control_executor.py | MODIFY | Enforce fail-closed trace emission, deterministic event vocabulary, and mandatory correlation fields on execution result emitters. |
| spectrum_systems/modules/runtime/validator_engine.py | MODIFY | Replace swallowed trace emission failures with explicit fail-closed handling and deterministic event constants. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Remove governed legacy replay schema fallback and enforce persist_result contract behavior. |
| contracts/schemas/control_execution_result.schema.json | MODIFY | Require correlation keys (`trace_id`, `run_id`, `artifact_id`) in control execution artifacts. |
| contracts/schemas/trace.schema.json | MODIFY | Enforce governed `event_type` vocabulary format normalization (lowercase snake_case). |
| contracts/standards-manifest.json | MODIFY | Version bump entries for modified governed contracts. |
| tests/test_control_executor.py | MODIFY | Add/adjust fail-closed observability and correlation-key tests. |
| tests/test_replay_engine.py | MODIFY | Add canonical-only replay schema and persistence enforcement tests. |
| tests/test_validator_engine.py | MODIFY | Add fail-closed observability and event vocabulary consistency assertions. |

## Contracts touched
- `contracts/schemas/control_execution_result.schema.json` (required fields expansion for correlation keys)
- `contracts/schemas/trace.schema.json` (event_type normalization constraints)
- `contracts/standards-manifest.json` (schema version updates)

## Tests that must pass after execution
1. `pytest tests/test_control_executor.py tests/test_validator_engine.py tests/test_replay_engine.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify non-runtime modules outside the declared file list.
- Do not introduce new artifact types or expand system scope beyond Tier-1 observability hardening.
- Do not weaken any schema requirements to satisfy tests.

## Dependencies
- Existing BAG replay contract baseline and runtime control loop modules must remain the authoritative implementation surface.
