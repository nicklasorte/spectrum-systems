# Plan — CON-048 Post-Merge Retest Fix — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-048

## Objective
Restore valid post-merge PQX retest reliability by resetting fixture state inputs, aligning retest expectation semantics between governed CLI execution and commit-range preflight inspection, and fixing narrow fixture-linked runtime trace linkage defects that currently prevent loop evaluation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-048-POSTMERGE-RETEST-FIX-2026-04-02.md | CREATE | Required PLAN artifact for multi-file BUILD scope. |
| tests/fixtures/roadmaps/allow_sequence.json | MODIFY | Point ALLOW fixture at fresh deterministic fixture state/runs paths. |
| tests/fixtures/roadmaps/block_sequence.json | MODIFY | Point BLOCK fixture at fresh deterministic fixture state/runs paths. |
| tests/fixtures/roadmaps/review_sequence.json | MODIFY | Point REQUIRE_REVIEW fixture at fresh deterministic fixture state/runs paths. |
| tests/fixtures/pqx_sequence_state/allow_state.json | CREATE | Fresh baseline state fixture for ALLOW retest path. |
| tests/fixtures/pqx_sequence_state/block_state.json | CREATE | Fresh baseline state fixture for BLOCK retest path. |
| tests/fixtures/pqx_sequence_state/review_state.json | CREATE | Fresh baseline state fixture for REQUIRE_REVIEW retest path. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Narrow runtime fixture artifact consistency fix for replay trace linkage so loop can evaluate control outcomes. |
| tests/test_pqx_slice_runner.py | MODIFY | Add regression coverage for replay embedded trace/lineage consistency emitted by runner. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/run_pqx_sequence.py --roadmap tests/fixtures/roadmaps/allow_sequence.json --output outputs/retest_trace_allow.json --run-id retest-allow-001`
2. `python scripts/run_pqx_sequence.py --roadmap tests/fixtures/roadmaps/block_sequence.json --output outputs/retest_trace_block.json --run-id retest-block-001`
3. `python scripts/run_pqx_sequence.py --roadmap tests/fixtures/roadmaps/review_sequence.json --output outputs/retest_trace_review.json --run-id retest-review-001`
4. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/retest_contract_preflight`
5. `pytest -q tests/test_run_pqx_sequence_cli.py tests/test_pqx_sequential_loop.py tests/test_pqx_execution_trace.py tests/test_contract_preflight.py tests/test_contracts.py tests/test_contract_enforcement.py tests/test_pqx_slice_runner.py`

## Scope exclusions
- Do not redesign PQX CLI/wrapper/loop architecture.
- Do not modify control decision logic.
- Do not weaken fail-closed semantics.
- Do not alter preflight semantics beyond mode-appropriate expectation alignment.

## Dependencies
- None.
