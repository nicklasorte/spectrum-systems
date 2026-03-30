# Cycle Runner Runbook

## Purpose
Run deterministic next-action resolution for an autonomous cycle manifest.

## Input
- `runs/<cycle_id>/cycle_manifest.json` (must validate against `cycle_manifest` contract)

## Output
- Structured decision object with:
  - `current_state`
  - `next_state`
  - `next_action`
  - `status`
  - `blocking_issues`
  - optional integration handoff payload

## Typical usage
```python
from spectrum_systems.orchestration import run_cycle
result = run_cycle("runs/cycle-0001/cycle_manifest.json")
print(result)
```

## Integration seams
- PQX seam: emitted at `execution_ready` as `invoke_pqx_execution_stub`.
- Certification seam: emitted at `fixes_complete_unreviewed`/`certification_pending` to call `spectrum_systems.modules.governance.done_certification.run_done_certification`.

## Failure behavior
Any missing required artifact in the current state blocks progression; no implicit skip-forward is allowed.
