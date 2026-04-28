# MET-43 Owner Handoff Authority Fixes

## Prompt type
REVIEW

## must_fix closure

### finding
Owner-read rows missing explicit next recommended input in some states.

### fix
Added explicit `next_recommended_input` for every owner read item and materialization observation row in MET-34 and MET-35 artifacts.

### files changed
- `artifacts/dashboard_metrics/owner_read_observation_ledger_record.json`
- `artifacts/dashboard_metrics/materialization_observation_mapper_record.json`

### tests added
- `tests/metrics/test_met_34_47_contract_selection.py` checks owner-read and materialization invariants.

### residual risk
Owner artifact refs remain sparse; observation state stays unknown/none_observed until comparable owner artifacts are retrieved.

No must_fix items remain open.
