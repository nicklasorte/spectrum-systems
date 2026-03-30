# Autonomous Execution Loop (Foundation Slice)

This slice adds a deterministic, fail-closed control-plane loop that is artifact-first.

## Core boundaries
- Planning artifacts are separate from execution artifacts.
- Review artifacts are evidence, not control decisions.
- PQX is execution-only; control decides next actions.
- Done certification is the required final gate.
- Missing required artifact blocks progression.

## Implemented components
- `cycle_manifest` contract and example.
- `spectrum_systems/orchestration/cycle_runner.py` deterministic state progression.
- Review artifact contracts/templates for roadmap and implementation reviews.
- `spectrum_systems/fix_engine/generate_fix_roadmap.py` for dedupe/classify/group output.
- Integration seams:
  - PQX execution handoff (`pqx_slice_runner` seam, stub-only)
  - GOV-10 done certification handoff (`run_done_certification` seam)

## Fail-closed meaning in this loop
If a state requires an artifact and that artifact is missing or invalid, the runner emits `status=blocked` and `next_state=blocked` with explicit blocking reasons.

## Remaining for next phase
- Replace PQX stub handoff with live execution adapter invocation and receipt persistence.
- Add post-fix dual review loop artifacts distinct from pre-fix implementation reviews.
- Add certification artifact write-back and manifest mutation workflow wrappers.
