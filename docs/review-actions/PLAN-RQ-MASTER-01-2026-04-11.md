# PLAN — RQ-MASTER-01

- **Prompt Type:** BUILD
- **Batch:** RQ-MASTER-01
- **Umbrella:** OPERATOR_TRUTH_AND_DECISION_QUALITY
- **Date:** 2026-04-11

## Intent
Execute a repo-native serial sequence with hard checkpoints to close dashboard operator truth, validate recommendation correctness, calibrate confidence, detect stuck loops, and finish with a governed bounded-expansion gate.

## Scope and Steps
1. Add `scripts/run_rq_master_01.py` to emit governed artifacts for all five phases (RQ-01 through RQ-24), run per-phase checkpoint validation, and fail closed on missing or invalid artifacts.
2. Add `scripts/validate_dashboard_public_artifacts.py` to enforce dashboard publication truth: required public artifact set, freshness guard, explicit fallback visibility, and recommendation quality degradation when key artifacts are missing.
3. Add tests covering serial checkpoint behavior, stop-on-failure semantics, artifact completeness, and dashboard truth validation.
4. Add a dashboard deploy CI gate workflow that runs refresh/build and enforces dashboard public artifact truth validation before completion.

## Constraints
- No architecture redesign and no new backend APIs.
- No live polling, execution controls, or charting additions.
- No recommendation artifact without provenance.
- No confidence claim without evidence.
- No fallback state represented as live state.

## Validation
- `pytest tests/test_rq_master_01.py tests/test_validate_dashboard_public_artifacts.py`
- `python scripts/run_rq_master_01.py`
- `python scripts/validate_dashboard_public_artifacts.py`
- `./scripts/refresh_dashboard.sh`
- Dashboard `npm run lint` and `npm run build`

## Out of Scope
- Runtime redesign or ownership reassignment.
- Unrelated refactors.
