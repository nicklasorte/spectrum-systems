# PQX Triage Planner (B10)

## What this planner does

- Consumes governed `pqx_review_result` and `pqx_fix_gate_record` artifacts.
- Normalizes findings into deterministic triage items with bounded enums.
- Produces a planning-only `pqx_triage_plan_record` artifact.
- Emits machine-readable rack-and-stack recommendations for:
  - `patch_current_bundle`
  - `insert_next_bundle`
  - `defer_to_future_bundle`
  - `roadmap_update_required`
  - `human_decision_required`

## What this planner does **not** do

- It does not execute inserted slices.
- It does not mutate `docs/roadmaps/system_roadmap.md`.
- It does not bypass review checkpoints or fix-gate governance.
- It does not create a parallel orchestration path.

## Deterministic mapping model

Priority/severity mapping is bounded and deterministic:

- `critical -> p0`
- `high -> p1`
- `medium -> p2`
- `low -> p3`

Execution impact mapping:

- blocking `p0/p1` => `block_now`
- blocking `p2/p3` => `run_before_resume`
- non-blocking `p0/p1` => `run_next`
- non-blocking `p2/p3` => `defer` (or `run_next` for fix-gate investigate path)

Required actions are bounded:

- `fix`
- `review`
- `roadmap_patch`
- `doc_only`
- `investigate`

## Why this is safe for sequential PQX execution

The planner is artifact-first and replay-safe: identical review/fix inputs reproduce identical triage outputs (except controlled `triage_plan_id`/timestamps). It only produces recommendations, so N-step sequential PQX execution remains human-controlled and governed without unsafe auto-expansion.

## Operator usage

- During bundle execution: `scripts/run_pqx_bundle.py run --emit-triage-plan ...`
- From existing artifacts: `scripts/run_pqx_bundle.py emit-triage-plan ...`

Non-zero exit behavior for triage CLI:

- Exit `1` when triage contains blocking items.
- Exit `2` on invalid/malformed triage inputs (fail-closed).
