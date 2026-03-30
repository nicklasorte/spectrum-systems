# Cycle Runner Runbook

## Purpose
Run deterministic next-action resolution and live handoff/write-back for an autonomous cycle manifest, including review-driven fix-loop re-entry.

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
- Updated `cycle_manifest.json` write-back for live execution/review/fix/certification transitions.

## Typical usage
```python
from spectrum_systems.orchestration import run_cycle
result = run_cycle("runs/cycle-0001/cycle_manifest.json")
print(result)
```

## Integration seams
- PQX seam (live): at `execution_ready`, runner invokes `spectrum_systems.modules.runtime.pqx_slice_runner.run_pqx_slice` through `pqx_handoff_adapter`, validates emitted artifacts, writes `execution_report_artifact`, and advances state.
- Review ingestion seam (live contract validation): at `roadmap_under_review` and `execution_complete_unreviewed`, runner validates roadmap/implementation review artifacts against repo-native contracts and blocks on missing/invalid evidence.
- Fix roadmap seam (live generator): at `implementation_reviews_complete`, runner invokes `spectrum_systems.fix_engine.generate_fix_roadmap.generate_fix_roadmap`, writes JSON + Markdown artifacts, persists `fix_group_refs`, and advances to `fix_roadmap_ready`.
- PQX fix re-entry seam (live): at `fix_roadmap_ready`, runner converts approved fix bundles into deterministic PQX requests, executes through existing `pqx_handoff_adapter`, validates execution reports, writes `fix_execution_report_paths`, and advances to `fixes_in_progress`.
- Certification seam (live): at `certification_pending`, runner invokes `spectrum_systems.modules.governance.done_certification.run_done_certification`, validates output, writes certification record path/summary, and advances or blocks.

## Terminal states
- `certified_done`: certification artifact is present, schema-valid, and passing.
- `blocked`: fail-closed terminal for missing/invalid artifacts, failed handoffs, or failed certification.

## Failure behavior
Any missing required artifact or schema-invalid required artifact in the current state blocks progression; no implicit skip-forward is allowed.

## Review/fix state progression
Review-driven closed-loop sequence:

`execution_complete_unreviewed -> implementation_reviews_complete -> fix_roadmap_ready -> fixes_in_progress -> fixes_complete_unreviewed -> certification_pending`

`blocked` means the cycle cannot advance until required artifacts are repaired and the same manifest is rerun.


## Observability/status reporting
Use `scripts/run_cycle_observability.py` to build deterministic status artifacts without mutating cycle state.

Single-cycle status artifact:
```bash
python scripts/run_cycle_observability.py   --manifest runs/cycle-0001/cycle_manifest.json   --status-output runs/cycle-0001/cycle_status_artifact.json
```

Backlog/queue snapshot over multiple cycles:
```bash
python scripts/run_cycle_observability.py   --manifest runs/cycle-0001/cycle_manifest.json   --manifest runs/cycle-0002/cycle_manifest.json   --backlog-output runs/cycle_backlog_snapshot.json
```

### Deterministic blocked reason categories
- `missing_required_artifact`
- `invalid_artifact_contract`
- `pqx_execution_failure`
- `review_missing`
- `review_invalid`
- `fix_generation_failure`
- `certification_missing`
- `certification_failed`
- `other`

### Fail-closed reporting conditions
- `current_state=blocked` with empty `blocking_issues` is rejected.
- Partial timing fields (`execution_started_at` without `execution_completed_at` or vice versa) are rejected.
- All rollups derive from recorded artifacts only; missing derivation inputs are reported, not guessed.
