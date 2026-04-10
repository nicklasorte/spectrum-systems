# Plan — BATCH-BRF-ENFORCE-01 — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-BRF-ENFORCE-01

## Objective
Enforce Build → Test → Review → Decision as a fail-closed batch progression invariant with an explicit batch decision artifact required for governed progression.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/batch_decision_artifact.schema.json | CREATE | Define explicit governed batch decision artifact contract. |
| contracts/examples/batch_decision_artifact.json | CREATE | Provide canonical example payload for the new contract. |
| contracts/schemas/prompt_queue_step_decision.schema.json | MODIFY | Require validation/preflight/review evidence in step decision inputs. |
| contracts/schemas/prompt_queue_transition_decision.schema.json | MODIFY | Require batch decision artifact reference before progression. |
| contracts/schemas/prompt_queue_execution_result.schema.json | MODIFY | Carry validation/preflight evidence required for decision emission. |
| contracts/standards-manifest.json | MODIFY | Register new/updated contract versions for BRF enforcement changes. |
| spectrum_systems/modules/prompt_queue/findings_normalizer.py | MODIFY | Emit validation/preflight/review evidence in normalized findings. |
| spectrum_systems/modules/prompt_queue/step_decision.py | MODIFY | Fail closed when validation/preflight/review evidence is missing before decision. |
| spectrum_systems/modules/prompt_queue/post_execution_policy.py | MODIFY | Require batch decision artifact to build progression transition decisions. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Enforce decision-artifact-backed progression in governed queue loop. |
| spectrum_systems/modules/prompt_queue/prompt_queue_transition_artifact_io.py | MODIFY | Validate updated transition schema with batch decision reference. |
| spectrum_systems/modules/prompt_queue/batch_decision_artifact.py | CREATE | Build/validate explicit batch decision artifact from BRF evidence. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export batch decision artifact APIs. |
| tests/test_prompt_queue_execution_loop.py | MODIFY | Add BRF invariant tests for validation/review/decision/progression rules. |
| tests/test_prompt_queue_post_execution_policy.py | MODIFY | Cover transition decision enforcement requiring batch decision artifact. |
| tests/test_prompt_queue_next_step_integration.py | MODIFY | Ensure progression seams fail closed on missing batch decision linkage. |
| docs/governance/prompt_queue_brf_invariant.md | CREATE | Minimal BRF invariant documentation update. |
| docs/reviews/brf_enforce_redteam.md | CREATE | Mandatory targeted red-team review artifact for BRF enforcement. |

## Contracts touched
- New: `batch_decision_artifact`
- Updated: `prompt_queue_execution_result`, `prompt_queue_step_decision`, `prompt_queue_transition_decision`
- Manifest version bump in `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_execution_loop.py`
2. `pytest tests/test_prompt_queue_post_execution_policy.py tests/test_prompt_queue_next_step_integration.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign overall orchestration architecture.
- Do not alter CDE closure authority model.
- Do not introduce new authority systems beyond batch progression decision enforcement.
- Do not refactor unrelated prompt queue subsystems.

## Dependencies
- Existing AEX, GOV-A, GOV-B, and preflight hardening surfaces remain unchanged and are treated as upstream inputs.
