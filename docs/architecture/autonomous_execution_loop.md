# Autonomous Execution Loop (Closed-Loop Slice)

This slice extends the deterministic fail-closed control-plane from foundation seams to live write-back behavior.

## Core boundaries
- Planning artifacts are separate from execution artifacts.
- Review artifacts are evidence, not control decisions.
- PQX is execution-only; control decides next actions.
- GOV-10 done certification is the required final gate.
- Missing required artifact, invalid artifact, or failed handoff blocks progression.

## Implemented components
- `cycle_manifest` contract and example with live handoff/write-back tracking fields.
- `spectrum_systems/orchestration/cycle_runner.py` deterministic state progression with execution + certification write-back.
- `spectrum_systems/orchestration/pqx_handoff_adapter.py` live PQX adapter around `run_pqx_slice`.
- Live seam integrations:
  - PQX execution handoff (`spectrum_systems.modules.runtime.pqx_slice_runner.run_pqx_slice`)
  - GOV-10 done certification handoff (`spectrum_systems.modules.governance.done_certification.run_done_certification`)
- Integration tests covering happy path, blocked paths, and deterministic replay behavior.

## Closed-loop transition behavior
Happy path progression for this slice:
`execution_ready -> execution_complete_unreviewed -> certification_pending -> certified_done`

Blocked terminal behavior:
- missing/invalid PQX request or output artifacts
- invalid execution report contract
- missing/invalid/failing done certification result

`blocked` is terminal until an operator repairs inputs and reruns the cycle.
