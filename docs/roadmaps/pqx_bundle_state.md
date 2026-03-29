# PQX Bundle State Contract and Advancement Rules (B4)

## Purpose
`pqx_bundle_state` is the first machine-enforced bundle advancement substrate for PQX.
It is intentionally narrow: it governs deterministic persisted state, ordered advancement checks, and fail-closed review/fix attachment semantics.

This slice does **not** implement the full autonomous multi-bundle executor.

## Contract Surface
- Schema: `contracts/schemas/pqx_bundle_state.schema.json`
- Example: `contracts/examples/pqx_bundle_state.json`
- Publication registry: `contracts/standards-manifest.json`

Required persisted fields include:
- authority + plan references (`roadmap_authority_ref`, `execution_plan_ref`)
- run identity (`run_id`, `sequence_run_id`)
- advancement state (`active_bundle_id`, `completed_bundle_ids`, `completed_step_ids`, `blocked_step_ids`)
- controlled insertion/review state (`pending_fix_ids`, `review_artifact_refs`)
- replay linkage (`artifact_index`, `resume_position`)
- provenance timestamps (`created_at`, `updated_at`)

## Runtime Helpers
` spectrum_systems/modules/runtime/pqx_bundle_state.py ` exposes deterministic helpers:
- `initialize_bundle_state`
- `load_bundle_state`
- `save_bundle_state`
- `validate_bundle_state`
- `assert_valid_advancement`
- `mark_step_complete`
- `mark_bundle_complete`
- `block_step`
- `attach_review_artifact`
- `add_pending_fix`
- `derive_resume_position`

## Fail-Closed Advancement Rules
1. Step completion is blocked if:
   - step is missing from bundle plan,
   - prior steps in the active bundle are incomplete,
   - target step belongs to a non-active bundle,
   - active bundle dependencies are incomplete,
   - step is already completed or blocked.
2. Bundle completion is blocked if:
   - target bundle is not active,
   - required steps are incomplete,
   - dependency bundles are incomplete,
   - bundle was already completed.
3. Malformed review/fix entries are blocked by schema and runtime shape validation.
4. `roadmap_authority_ref` is strict and fail-closed (`docs/roadmaps/system_roadmap.md`).
5. Persist/reload parity is enforced exactly.

## Current Seam Integration
`pqx_sequence_runner.execute_sequence_run` now supports optional wiring:
- `bundle_state_path`
- `bundle_plan` / `bundle_id`
- `roadmap_authority_ref`
- `execution_plan_ref`

When configured, sequence execution persists and advances `pqx_bundle_state` in lockstep with `prompt_queue_sequence_run`.

## Out of Scope for B4
- No broad autonomous multi-bundle scheduler.
- No redesign of roadmap parser/authority bridge.
- No review/fix auto-execution loop yet (representation only).
