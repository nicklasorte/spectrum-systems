# Plan — BATCH-RDX-EXEC-REAL-01 — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-RDX-EXEC-REAL-01 — Governed Multi-Umbrella REAL execution hardening

## Objective
Execute real governance hardening and validation across four umbrellas by enforcing BRF/decision fail-closed behavior in runtime code, validating hierarchy progression boundaries, and producing governed artifact/review/delivery outputs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| `spectrum_systems/modules/prompt_queue/batch_decision_artifact.py` | MODIFY | Harden fail-closed checks for review and validation artifact references and decision support evidence. |
| `spectrum_systems/modules/prompt_queue/queue_state_machine.py` | MODIFY | Emit runtime batch-decision evidence in queue loop output path for BRF traceability. |
| `tests/test_prompt_queue_execution_loop.py` | MODIFY | Add fail-closed + BRF evidence tests for runtime emission and strict artifact refs. |
| `tests/test_execution_hierarchy.py` | MODIFY | Add hierarchy enforcement edge-case tests for umbrella and batch minimum cardinality semantics. |
| `artifacts/rdx_runs/BATCH-RDX-EXEC-REAL-01-artifact-trace.json` | CREATE | Record real umbrella/batch/slice execution and BRF evidence trail. |
| `docs/reviews/RVW-RDX-EXEC-REAL-01.md` | CREATE | Mandatory end-of-run review with safety questions and verdict. |
| `docs/reviews/BATCH-RDX-EXEC-REAL-01-DELIVERY-REPORT.md` | CREATE | Mandatory delivery report with executed work and recommendation. |

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_execution_loop.py tests/test_execution_hierarchy.py`
2. `python scripts/run_contract_preflight.py`
3. `python scripts/run_review_artifact_validation.py --allow-full-pytest`

## Scope exclusions
- No role ownership redefinition outside canonical registry.
- No unrelated refactors outside prompt-queue/runtime governance seams.
- No closure authority changes (CDE remains sole closure authority).
