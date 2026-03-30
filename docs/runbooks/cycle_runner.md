# Cycle Runner Runbook

## Purpose
Run deterministic next-action resolution and live handoff/write-back for an autonomous cycle manifest.

## Input
- `runs/<cycle_id>/cycle_manifest.json` (must validate against `cycle_manifest` contract)

## Output
- Structured decision object with:
  - `current_state`
  - `next_state`
  - `next_action`
  - `status`
  - `blocking_issues`
  - optional `integration_handoff` payload
- Updated `cycle_manifest.json` write-back for live execution/certification transitions.

## Typical usage
```python
from spectrum_systems.orchestration import run_cycle
result = run_cycle("runs/cycle-0001/cycle_manifest.json")
print(result)
```

## Integration seams
- PQX seam (live): at `execution_ready`, runner invokes `spectrum_systems.modules.runtime.pqx_slice_runner.run_pqx_slice` through `pqx_handoff_adapter`, validates emitted artifacts, writes `execution_report_artifact`, and advances state.
- Certification seam (live): at `certification_pending` (or `fixes_complete_unreviewed`), runner invokes `spectrum_systems.modules.governance.done_certification.run_done_certification`, validates output, writes certification record path/summary, and advances or blocks.

## Terminal states
- `certified_done`: certification artifact is present, schema-valid, and passing.
- `blocked`: fail-closed terminal for missing/invalid artifacts, failed handoffs, or failed certification.

## Failure behavior
Any missing required artifact or schema-invalid required artifact in the current state blocks progression; no implicit skip-forward is allowed.
