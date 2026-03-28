# Plan — [ROW: QUEUE-06] Retry and Remediation Branching — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-06] Retry and Remediation Branching

## Objective
Implement deterministic, fail-closed retry/remediation branching that emits explicit governed artifacts for retry, repair prompt, findings reentry, blocked recovery, and loop continuation while preventing duplicate/conflicting branch actions and silent retries.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-06-2026-03-28.md | CREATE | Required plan-first artifact for this multi-file BUILD slice. |
| PLANS.md | MODIFY | Register active QUEUE-06 plan in active plan table. |
| spectrum_systems/modules/prompt_queue/retry_policy.py | MODIFY | Harden retry eligibility to require transition-compatible explicit decisions and deterministic fail-closed checks. |
| spectrum_systems/modules/prompt_queue/retry_queue_integration.py | MODIFY | Enforce explicit artifact path and fail-closed duplicate/conflicting retry application rules. |
| spectrum_systems/modules/prompt_queue/repair_prompt_generator.py | MODIFY | Harden lineage preconditions and deterministic repair prompt branch metadata. |
| spectrum_systems/modules/prompt_queue/repair_child_creator.py | MODIFY | Harden duplicate child identity checks and deterministic child lineage preconditions. |
| spectrum_systems/modules/prompt_queue/findings_reentry.py | MODIFY | Tighten findings-driven reentry gating and lineage fail-closed behavior before remediation branching. |
| spectrum_systems/modules/prompt_queue/blocked_recovery_policy.py | MODIFY | Add explicit fail-closed handling for missing blocking lineage inputs and incompatible blocked recovery inputs. |
| spectrum_systems/modules/prompt_queue/loop_continuation.py | MODIFY | Require explicit continuation gating for child spawn and fail-closed conflicting continuation/recovery signals. |
| tests/test_prompt_queue_retry.py | MODIFY | Add retry eligibility, duplicate/conflicting retry, and no-silent-retry coverage. |
| tests/test_prompt_queue_repair_child_creation.py | MODIFY | Add deterministic lineage and duplicate child hard-fail coverage. |
| tests/test_prompt_queue_findings_reentry.py | MODIFY | Add malformed findings/lineage fail-closed coverage and bounded reentry gating checks. |
| tests/test_prompt_queue_blocked_recovery.py | MODIFY | Add explicit artifact requirement and incompatible recovery input fail-closed coverage. |
| tests/test_prompt_queue_loop_continuation.py | MODIFY | Add explicit continuation artifact requirement and conflicting blocked/continue fail-closed coverage. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_retry.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_findings_reentry.py tests/test_prompt_queue_blocked_recovery.py tests/test_prompt_queue_loop_continuation.py`
2. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not add queue observability aggregation (QUEUE-07).
- Do not add replay/resume logic (QUEUE-08).
- Do not add certification logic (QUEUE-10).
- Do not implement multi-step queue execution changes outside governed branch artifacts.

## Dependencies
- [ROW: QUEUE-01] Queue manifest/state contract spine complete.
- [ROW: QUEUE-04] Transition decision spine complete.
- [ROW: QUEUE-05] Execution loop state-update behavior complete.
