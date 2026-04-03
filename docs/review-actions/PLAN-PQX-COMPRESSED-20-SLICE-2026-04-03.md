# Plan — PQX Compressed 20-Slice Push — 2026-04-03

## Prompt type
PLAN

## Roadmap item
PQX Compressed 20-Slice Push (CON-064 / PQX-BATCH-01/02/03)

## Intent
Implement a bounded, repo-native admission + sequential batch execution path that can run an admitted ordered 10/20-slice set in one invocation while preserving per-slice post-enforcement authority semantics.

## Exact scope
- Add a deterministic batch admission validator for slice requests against authoritative executable steps and dependency ordering.
- Wire admission into sequence execution before runtime progression.
- Extend sequence-run output to include explicit batch-result semantics (overall status, per-slice statuses, stopping slice, completed and remaining slices).
- Keep existing per-slice eval/control/enforcement flow authoritative; no premature completion.
- Add focused deterministic regression tests for repeated admitted input parity and incidental text/path insensitivity.
- Keep CLI thin while ensuring it executes the admitted batch path.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-COMPRESSED-20-SLICE-2026-04-03.md | CREATE | Required plan-first artifact for multi-file runtime/test changes |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Add admission model + governed batch result projection + deterministic helpers |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Preserve existing bundle/fix single-step flows while enabling sequence admission on true batch path |
| scripts/run_prompt_queue_sequence.py | MODIFY | Keep CLI thin while consuming admitted batch behavior |
| tests/test_pqx_sequence_runner.py | MODIFY | Add admission, stop behavior, authority, and determinism coverage |
| tests/test_prompt_queue_sequence_cli.py | MODIFY | Assert CLI behavior over admitted batch execution path |

## Invariants to preserve
- Fail-closed behavior on invalid inputs and invalid transitions.
- No bypass of per-slice eval/control/enforcement.
- Slice completion is only authoritative after post-enforcement ALLOW.
- BLOCK/REQUIRE_REVIEW outcomes never finalize a slice as complete.
- Thin CLI shape and deterministic state persistence semantics.

## Contracts touched
None.

## Risks
- Admission validation could over-constrain previously valid narrow flows.
- New batch summary fields could drift from persisted final state if derived inconsistently.
- Resume path could accidentally bypass admission parity constraints.

## Acceptance criteria
- Invalid/missing/duplicate/dependency-invalid slice sets fail closed before execution.
- Valid ordered 10/20-slice set is admitted and becomes run source-of-truth.
- Batch run executes slice-by-slice and stops on block/review while preserving prior completions.
- completed_step_ids/completed_slice_ids include only post-enforcement-authorized slices.
- Repeated admitted batch execution yields identical logical outcomes.

## Test plan
1. `pytest tests/test_pqx_sequence_runner.py`
2. `pytest tests/test_pqx_sequential_loop.py`
3. `pytest tests/test_pqx_n_slice_validation.py`
4. `pytest tests/test_prompt_queue_sequence_cli.py`
5. `pytest tests/test_pqx_backbone.py`
6. `pytest tests/test_pqx_fix_execution.py`
7. `pytest tests/test_contracts.py`

## Non-goals
- No new orchestrator subsystem.
- No architecture redesign for PQX/bundle/control loop.
- No CI/systemization expansion beyond focused deterministic tests.
- No weakening of fail-closed governance boundaries.

## Dependencies
- Existing post-enforcement completion fix remains in place and is not reverted.
