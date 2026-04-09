# BATCH-SYS-ENF-03A — Contract Preflight Repair Note (2026-04-09)

## What broke
ENF-03 correctly collapsed authority but introduced contract-preflight `BLOCK` due to compatibility fallout:
1. `contracts/examples/next_step_decision_artifact.json` remained a multi-case container, while the schema validates a single artifact object.
2. Downstream consumers and smoke tests still expected legacy `next_action` / `allowed_actions` fields.
3. Promotion smoke tests in `tests/test_cycle_runner.py` lacked newly required CDE closure + RIL artifact refs, causing earlier fail-closed blocks than expected.

## How compatibility was repaired
- Added a compatibility bridge in `next_step_decision_artifact` producer + schema:
  - canonical non-authoritative fields remain `recommendation_action` and `recommendation_candidates`
  - legacy `next_action` and `allowed_actions` are emitted as derived aliases only
  - legacy `fix_plan_artifact_path` is emitted as derived alias from `fre_fix_plan_artifact_ref`
- Normalized `contracts/examples/next_step_decision_artifact.json` to a single schema-valid artifact payload.
- Updated affected consumer tests to consume canonical recommendation fields while allowing legacy alias checks.
- Updated cycle-runner tests to provide closure/RIL evidence and assert against CDE closure gating behavior.

## Why architectural correction is preserved
- Promotion authority remains CDE-only through required `closure_decision_artifact` checks.
- TLC and orchestration modules still emit non-authoritative signals/recommendations.
- Compatibility fields are aliases only and do not restore decision authority.
