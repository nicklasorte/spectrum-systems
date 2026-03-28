# Plan — PQX-QUEUE-04 — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-04] Unified Transition Policy and Next-Step Decision Spine

## Objective
Establish a single fail-closed transition decision artifact and policy builder that consolidates queue transition reasoning across post-execution, next-step, and loop-control seams without introducing queue-loop orchestration or direct queue-state mutation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/prompt_queue_transition_decision.schema.json | CREATE | New governed transition decision contract for QUEUE-04. |
| contracts/examples/prompt_queue_transition_decision.json | CREATE | Golden-path example for new transition artifact. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version. |
| spectrum_systems/modules/prompt_queue/prompt_queue_transition_artifact_io.py | CREATE | Schema validation and deterministic IO for transition artifact. |
| spectrum_systems/modules/prompt_queue/post_execution_policy.py | MODIFY | Add unified transition decision builder; fail-closed mapping from step decisions/findings. |
| spectrum_systems/modules/prompt_queue/next_step_orchestrator.py | MODIFY | Consume unified transition decision artifact for next-step action derivation. |
| spectrum_systems/modules/prompt_queue/loop_control_policy.py | MODIFY | Add transition-aware policy helper to preserve bounded deterministic outcomes. |
| spectrum_systems/modules/prompt_queue/execution_gating_policy.py | MODIFY | Add transition decision compatibility guard helper for bounded fail-closed gating behavior. |
| spectrum_systems/modules/prompt_queue/review_trigger_policy.py | MODIFY | Add transition artifact compatibility mapping for review triggering. |
| spectrum_systems/modules/prompt_queue/next_step_queue_integration.py | MODIFY | Consume transition decision artifacts and avoid direct queue advancement. |
| spectrum_systems/modules/prompt_queue/post_execution_queue_integration.py | MODIFY | Emit transition integration receipt only; no queue mutation. |
| spectrum_systems/modules/prompt_queue/loop_control_queue_integration.py | MODIFY | Consume transition decisions and emit deterministic integration receipts without queue mutation. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export transition artifact IO + unified builder/integration helpers. |
| tests/test_prompt_queue_transition_decision.py | CREATE | Contract + policy tests for unified transition decision behavior. |
| tests/test_prompt_queue_post_execution_policy.py | CREATE | Post-execution policy alignment tests for transition decision spine. |
| tests/test_prompt_queue_next_step_integration.py | CREATE | Integration tests asserting no queue advancement and deterministic decisions. |
| PLANS.md | MODIFY | Register active plan entry for QUEUE-04. |

## Contracts touched
- New: `prompt_queue_transition_decision` schema + example.
- Updated: `contracts/standards-manifest.json` (version bump and contract registration).

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_transition_decision.py tests/test_prompt_queue_post_execution_policy.py tests/test_prompt_queue_next_step_integration.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement queue runner loop orchestration.
- Do not implement retry execution logic.
- Do not mutate queue state in transition integration helpers.
- Do not alter unrelated prompt queue modules outside declared files.

## Dependencies
- [ROW: QUEUE-03] outputs (`prompt_queue_step_decision` and review parsing findings handoff) must remain authoritative inputs.
