# Plan — SS-HARD-02.1 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
SS-HARD-02.1

## Objective
Clear contract preflight BLOCK by repairing only the downstream deterministic consumer tests that still assert pre-SS-HARD-02 execution-result semantics, without weakening live/simulated truth or authority controls.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SS-HARD-02.1-2026-04-08.md | CREATE | Required plan-first artifact for multi-file repair. |
| tests/test_prompt_queue_post_execution.py | MODIFY | Align execution-result fixture with updated schema semantics for failure status (null output/error pairing expectations). |
| tests/test_prompt_queue_step_decision.py | MODIFY | Align decision expectations with updated findings normalization + schema-valid ambiguous failure artifact shape. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_step_decision.py`
2. `python scripts/run_contract_preflight.py --base-ref "2ce517222baf0310775a599970d1668b5157525b" --head-ref "89f109880c15b94c83aef01ad5e4241a7ff448b2" --output-dir outputs/contract_preflight`
3. `pytest tests/test_prompt_queue_execution_runner.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_audit_bundle.py`

## Scope exclusions
- Do not change execution runner logic for mode routing/live materialization.
- Do not weaken schema constraints added for execution truth.
- Do not modify authority enforcement, SEL/PQX checks, or permission provenance behavior.
- Do not broaden into unrelated preflight surfaces.

## Dependencies
- SS-HARD-02 must remain intact as baseline behavior.
