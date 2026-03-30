# Autonomous Execution Loop (Closed-Loop Slice)

This slice extends the deterministic fail-closed control-plane from foundation seams to live write-back behavior, including review ingestion and fix-loop re-entry.

## Core boundaries
- Planning artifacts are separate from execution artifacts.
- Review artifacts are evidence, not control decisions.
- PQX is execution-only; control decides next actions.
- GOV-10 done certification is the required final gate.
- Missing required artifact, invalid artifact, or failed handoff blocks progression.

## Implemented components
- `cycle_manifest` contract and example with live handoff/write-back tracking fields.
- `spectrum_systems/orchestration/cycle_runner.py` deterministic state progression with execution + certification write-back.
- `spectrum_systems/orchestration/cycle_runner.py` deterministic review ingestion, fix-roadmap auto-generation, PQX re-entry, and certification state progression.
- `spectrum_systems/orchestration/pqx_handoff_adapter.py` live PQX adapter around `run_pqx_slice`.
- `spectrum_systems/fix_engine/generate_fix_roadmap.py` deterministic grouping and output of machine-readable + markdown fix roadmaps.
- Live seam integrations:
  - PQX execution handoff (`spectrum_systems.modules.runtime.pqx_slice_runner.run_pqx_slice`)
  - implementation review ingestion (`implementation_review_artifact` validation)
  - fix-roadmap generation (`fix_roadmap_artifact` write-back)
  - PQX fix re-entry handoff (`spectrum_systems.orchestration.pqx_handoff_adapter.handoff_to_pqx`)
  - GOV-10 done certification handoff (`spectrum_systems.modules.governance.done_certification.run_done_certification`)
- Integration tests covering happy path, blocked paths, and deterministic replay behavior.

## Closed-loop transition behavior
Happy path progression for this slice:
`execution_ready -> execution_complete_unreviewed -> implementation_reviews_complete -> fix_roadmap_ready -> fixes_in_progress -> fixes_complete_unreviewed -> certification_pending -> certified_done`

Blocked terminal behavior:
- missing/invalid PQX request or output artifacts
- missing/invalid roadmap or implementation review artifacts
- fix-roadmap generation failure or invalid fix-roadmap artifact
- missing/invalid fix execution report write-back from PQX re-entry
- invalid execution report contract
- missing/invalid/failing done certification result

`blocked` is terminal until an operator repairs inputs and reruns the cycle.


## Cycle observability/status extension (grouped PQX slice)
- Added deterministic read-only status builder: `spectrum_systems/orchestration/cycle_observability.py`.
- Added contract-backed observability artifacts:
  - `cycle_status_artifact` (single-cycle machine-readable status + markdown summary)
  - `cycle_backlog_snapshot` (multi-cycle queue/backlog rollup + deterministic metrics)
- Status surfaces include: `cycle_id`, `current_state`, `next_action`, blocked reason summary, artifact refs, and `last_updated`.
- Blocked reasons are normalized into stable deterministic categories: `missing_required_artifact`, `invalid_artifact_contract`, `pqx_execution_failure`, `review_missing`, `review_invalid`, `fix_generation_failure`, `certification_missing`, `certification_failed`, `other`.
- Queue/backlog views are derived from manifests only and include active/blocked/certification-pending/awaiting-review/awaiting-PQX cohorts.
- Metrics are artifact-derived only (no hidden state/cache): count by state, blocked-by-reason, average execution seconds when timestamps are complete, critical/blocker finding counts from review artifacts, and certification pass/fail counts.
- Fail-closed behavior is preserved: blocked manifests without details and incomplete phase timing metadata raise deterministic errors instead of producing healthy-looking status.

## Judgment + precedent layer (artifact-first extension)

This grouped slice adds a deterministic judgment seam for `artifact_release_readiness` without collapsing role boundaries.

### New judgment artifacts
- `judgment_policy`: versioned policy artifact with deterministic selection keys (`judgment_type`, `scope`, `environment`) and status (`draft/canary/active/deprecated`).
- `judgment_record`: rationale-bearing judgment result with claims, evidence refs, rule application, alternatives, uncertainties, conditions for decision change, and precedent trace.
- `judgment_application_record`: captures policy matching set, selected policy, conflict signals, deviation notes, and final outcome.
- `judgment_eval_result`: minimum viable deterministic consistency report for policy selection and precedent retrieval behavior.

### Policy registry behavior
- Registry input is explicit `judgment_policy_paths` in `cycle_manifest`.
- Policies are loaded from repo artifacts only (no hidden state/cache).
- Selection is deterministic:
  1. filter by `judgment_type + scope + environment`
  2. keep `active/canary`
  3. order by status (`active` before `canary`), semantic version descending, `artifact_id` ascending.

### Precedent retrieval behavior
- Retrieval method: deterministic `exact-field-overlap`.
- Inputs are bounded by policy-declared `query_fields`; missing required retrieval inputs fail closed.
- Record includes `method_id`, `method_version`, `threshold`, `top_k`, `similarity_basis`, and scored precedent refs.
- Sorting is deterministic by score (desc) then record ref (asc).

### Control gating behavior
- `roadmap_approved -> execution_ready` can require `artifact_release_readiness` judgment.
- If required judgment artifacts are missing or invalid: cycle blocks.
- If judgment outcome is `block`: cycle blocks.
- If outcome is `revise`: cycle blocks pending explicit remediation (no silent promotion).
- Only `approve` allows normal progression when other hard gates are satisfied.

### Deferred for later calibration/drift phases
- Policy canary rollout analytics and runtime drift calibration.
- Multi-judgment composition across additional judgment types.
- Richer precedent scoring features beyond deterministic overlap.
