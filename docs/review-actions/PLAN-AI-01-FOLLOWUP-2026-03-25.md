# Plan — AI-01 Follow-up — 2026-03-25

## Prompt type
PLAN

## Roadmap item
AI-01 follow-up hardening

## Objective
Close the governed runtime model-call bypass by making prompt registry backing mandatory on governed runtime paths and align roadmap authority in AGENTS.md to system_roadmap.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-AI-01-FOLLOWUP-2026-03-25.md | CREATE | Required plan artifact for surgical follow-up before BUILD edits. |
| AGENTS.md | MODIFY | Correct authoritative roadmap path to docs/roadmaps/system_roadmap.md and mark non-authoritative paths clearly. |
| spectrum_systems/modules/agents/agent_executor.py | MODIFY | Enforce mandatory registry-backed prompt identity for governed model steps. |
| spectrum_systems/modules/runtime/agent_golden_path.py | MODIFY | Ensure governed golden-path runtime passes registry entries into model adapter. |
| tests/test_agent_executor.py | MODIFY | Add/update tests proving missing registry backing and incomplete prompt identity block governed runtime model execution. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_agent_executor.py tests/test_agent_golden_path.py tests/test_model_adapter.py tests/test_prompt_registry.py`
2. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not redesign model adapter architecture.
- Do not add new contracts or schema versions.
- Do not modify unrelated modules outside governed runtime enforcement and roadmap authority correction.

## Dependencies
- Existing AI-01 seams in model_adapter.py and prompt_registry.py.
