# 3LS Measurement + Loop Observability Layer (SMA-01 v2)

A measurement and observability layer over the canonical 3-letter systems
(3LS). It produces versioned, schema-bound artifacts that observe and report
on system behavior across nine measurement dimensions.

This layer is observation only. It does not grant authority, replace
canonical control inputs, or block work. Canonical responsibility for every
3-letter system remains in `docs/architecture/system_registry.md`.

## What this layer is

A non-owning observation surface that:

- measures per-system execution evidence
- measures canonical loop completion and handoff integrity
- measures surface-to-test coverage mapping
- measures failure recurrence patterns
- measures trust gap closure over time
- measures replayability and determinism
- measures change scope and blast radius
- measures operator debuggability

## What this layer is NOT

- This layer does not produce `allow / warn / freeze / block` control
  outcomes.
- This layer does not orchestrate.
- This layer does not execute.
- This layer does not perform fail-closed actions.
- This layer does not route.

Canonical ownership for control, orchestration, execution, fail-closed
actions, and routing is declared in
`docs/architecture/system_registry.md` and is unchanged by this layer.
See that registry for the authoritative ownership mapping.

Every measurement artifact carries `authority_scope = "observation_only"`.
Schema validation rejects any other value.

## Artifacts

| Artifact                                | Dimension measured                                |
|-----------------------------------------|---------------------------------------------------|
| `3ls_system_measurement_record`         | per-system execution evidence and coverage        |
| `3ls_loop_run_record`                   | canonical loop completion (AEX→PQX→EVL→TPA→CDE→SEL) |
| `3ls_handoff_record`                    | system-to-system handoff integrity                |
| `3ls_surface_coverage_record`           | changed-surface to test-target mapping            |
| `3ls_failure_recurrence_record`         | repeated CI/system failure patterns               |
| `3ls_trust_gap_closure_record`          | per-system trust gap delta over time              |
| `3ls_replayability_record`              | replay availability and determinism               |
| `3ls_scope_risk_record`                 | change scope and blast radius                     |
| `3ls_operator_debuggability_record`     | failure understandability without raw logs        |

Schemas live in `contracts/schemas/3ls_*.schema.json`. Canonical examples live
in `contracts/examples/3ls_*.example.json`. Manifest registration is in
`contracts/standards-manifest.json` (artifact_class `coordination`,
introduced_in `SMA-01-V2`).

## Fail-closed behavior

Every measurement schema is fail-closed. Missing structure halts measurement
rather than producing partial records that could be misread as evidence:

- `3ls_system_measurement_record`: `coverage_status = covered` requires
  non-empty `evidence_refs`; `uncovered` requires non-empty `gaps`.
- `3ls_loop_run_record`: `loop_status = complete` requires every downstream
  ref (`execution_ref`, `eval_ref`, `policy_ref`, `decision_input_ref`,
  `enforcement_signal_ref`); any non-complete loop_status requires a
  `first_failure_system` AND at least one downstream ref absent or null.
- `3ls_handoff_record`: `handoff_status = complete` requires
  `downstream_artifact_ref`; `blocked` and `failed` require non-empty
  `reason_codes`.
- `3ls_surface_coverage_record`: when `governed_surfaces` is non-empty,
  `mapped_test_targets` must also be non-empty (catches the
  `pytest_selection_missing` failure class early).
- `3ls_failure_recurrence_record`: `recurrence_count` must be ≥ 1; the
  fingerprint must be `sha256:` formatted; `affected_systems` must be
  non-empty; `failure_class` must align with the repo failure taxonomy.
- `3ls_replayability_record`: `replay_available = true` requires non-empty
  `replay_refs`; `false` requires a non-empty `replay_gap_reason` AND
  empty `replay_refs` (a record cannot simultaneously declare replay
  unavailable and attach replay evidence).
- `3ls_trust_gap_closure_record`: `status` must agree with the sign of
  `delta` (improving when delta < 0, unchanged when delta == 0,
  regressing when delta > 0). The arithmetic identity
  `delta == current_gap_count - previous_gap_count` is checked by the
  producing test suite; JSON Schema cannot express the cross-field
  arithmetic.
- `3ls_scope_risk_record`: changes touching workflows AND schemas AND
  scripts must classify as `high` or `critical`.
- `3ls_operator_debuggability_record`: `single_artifact_debuggable = true`
  requires non-empty `required_artifact_refs`.

## Where the records flow

These artifacts feed downstream observation/lineage/reporting/SLO surfaces:

- **OBS** consumes them as observability inputs.
- **LIN** consumes them as lineage signal.
- **REP** consumes them as reporting inputs.
- **SLO** consumes them as budget/health signal.

They do not flow into CDE as control inputs and do not flow into SEL as
fail-closed action inputs. Any consumption by control or fail-closed
authorities must go through the canonical authority artifacts owned by
those systems — not through these measurement records.

## Authority-safe wording rules

- These records reference canonical authority artifacts via `*_ref` fields.
  They never reproduce a control input or fail-closed signal inline.
- The `authority_scope` field is pinned to `observation_only` by schema
  `const`. Mutating it fails validation.
- The provenance `source_system` is typically a non-owning support system
  such as `OBS`, `LIN`, `REP`, or `SLO`. Records produced by canonical
  authority owners should remain in their canonical artifact families —
  not duplicated here.

## Failure modes now detectable

The measurement layer surfaces (without authorizing or blocking) the
following recurring failure modes:

- silent loop dropouts (loop_status partial without first_failure_system —
  invalid by schema)
- non-complete loops with all downstream refs populated (rejected by
  schema; contradicts the fail-closed contract)
- incomplete handoffs declared as complete (rejected by schema)
- changed governed surfaces with no test mapping (the
  `pytest_selection_missing` class)
- failures recurring across runs without a stable fingerprint (rejected by
  schema)
- replay claims without backing refs and replay gaps without a stated
  reason (rejected by schema)
- high blast-radius changes mis-classified as low (rejected by schema)

## Hard rules this layer preserves

- All 3-letter system responsibility remains in
  `docs/architecture/system_registry.md`.
- Every measurement artifact is `observation_only`.
- No measurement artifact may serve as substitute evidence for a canonical
  control input or fail-closed action.
- No measurement artifact extends or shadows ownership.
- Measurement records are versioned, schema-bound artifacts; non-determinism
  in inputs must be marked via the provenance `simulated` boolean.
