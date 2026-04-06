# Plan — BATCH-PQX-CLOSURE-01 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-PQX-CLOSURE-01 — Trust-by-Default Hardening (CR-1, CR-2, CR-3)

## Objective
Close the three remaining critical PQX trust seams by enforcing strict governed done-certification defaults, strict authoritative proof closure evidence requirements, and execution-admission rejection of inspection-only unknown-pending authority posture.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PQX-CLOSURE-01-2026-04-05.md | CREATE | Required PLAN artifact before multi-file hardening changes |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Enforce strict-by-default certification policy for governed/authoritative paths |
| spectrum_systems/modules/runtime/pqx_proof_closure.py | MODIFY | Add strict authoritative proof-closure mode rejecting synthetic fallback refs |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Fail-closed execution admission when preflight context is unknown_pending_execution |
| scripts/run_pqx_sequence.py | MODIFY | Prevent execution CLI admission with inspection-only unknown_pending_execution authority state |
| tests/test_done_certification.py | MODIFY | Add/update tests for governed strict certification defaults and compatibility behavior |
| tests/test_pqx_proof_closure.py | MODIFY | Add strict authoritative proof-closure pass/fail coverage |
| tests/test_pqx_slice_runner.py | MODIFY | Add execution-admission test blocking unknown_pending_execution from preflight artifact |
| tests/test_run_pqx_sequence_cli.py | MODIFY | Add CLI admission test rejecting unknown_pending_execution authority posture |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_done_certification.py tests/test_pqx_proof_closure.py tests/test_pqx_slice_runner.py tests/test_run_pqx_sequence_cli.py`
2. `pytest tests/test_contracts.py`
3. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-PQX-CLOSURE-01-2026-04-05.md`

## Scope exclusions
- Do not redesign PQX architecture, sequencing model, or governance model.
- Do not remove blocked/paused artifact paths.
- Do not weaken schemas/contracts or broaden permissive defaults outside explicit compatibility boundaries.
- Do not modify unrelated runtime/governance modules beyond the declared files.

## Dependencies
- docs/reviews/2026-04-05-pqx-architecture-review.md findings CR-1/CR-2/CR-3.
- Existing contract preflight and PQX execution policy artifacts remain authoritative.
