# PQX Bundle Execution Orchestrator (B5)

## What it does
`pqx_bundle_orchestrator` executes a declared executable bundle from `docs/roadmaps/execution_bundles.md` as an ordered roadmap-step run.
It is fail-closed and deterministic:
- validates bundle existence and step ordering
- validates roadmap step references and dependency-valid order
- executes one step at a time through existing `execute_sequence_run` seam
- persists `pqx_bundle_state` after each successful completion
- blocks on first failed/invalid step and persists blocked state
- emits a governed `pqx_bundle_execution_record` artifact

## Invocation path
- Python API: `spectrum_systems.modules.runtime.pqx_bundle_orchestrator.execute_bundle_run(...)`
- Sequence-run additive wrapper: `execute_bundle_sequence_run(...)`
- CLI: `python scripts/run_pqx_bundle.py --bundle-id ... --bundle-state-path ... --output-dir ... --run-id ... --sequence-run-id ... --trace-id ...`

## State transitions
- `initialize_bundle_state` (if missing)
- For each legal next step:
  - execute step
  - `mark_step_complete` + `save_bundle_state`
- On first failure:
  - `block_step` + `save_bundle_state`
  - halt run
- On full completion:
  - `mark_bundle_complete`

## Fail-closed rules
Execution blocks immediately when:
- executable bundle table section is missing/ambiguous/malformed
- bundle ID is unknown
- bundle includes duplicate steps
- bundle references unknown roadmap steps
- dependency ordering violates roadmap dependency graph
- resume authority/plan/run lineage mismatches persisted state
- persisted completed-step order diverges from declared bundle order
- duplicate completion or out-of-order advancement is attempted

## Resume semantics
Resume is driven by persisted `pqx_bundle_state`:
- completed steps are skipped
- execution resumes at `resume_position.next_step_id`
- authority/plan/run lineage must match exactly
- mismatched state causes immediate fail-closed block (error)

## Known limits
- Replay mode for intentional re-execution is not implemented.
- Review automation/branching is out-of-scope; only review reference fields are preserved in artifacts.
- Current executable bundle table is intentionally narrow (single core bundle) until later bundle expansion slices.
