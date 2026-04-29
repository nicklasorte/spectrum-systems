# SMA-01 v2 — 3LS System Measurement + Loop Observability Layer Delivery Report

## Summary

SMA-01 v2 extends the initial 3LS system measurement work into a full,
artifact-first measurement and observability layer over the 3-letter systems
and the canonical execution loop.

This is a measurement layer only. It does NOT change authority, control, or
fail-closed behavior. Every artifact is fail-closed and carries
`authority_scope = "observation_only"` as a schema-pinned constant.

## Branch

`claude/3ls-measurement-layer-cquZL`

## Artifacts added

Schemas and canonical examples (registered in
`contracts/standards-manifest.json` under `introduced_in: SMA-01-V2`,
`artifact_class: coordination`):

| Artifact                                | Schema                                                                | Example                                                                  |
|-----------------------------------------|-----------------------------------------------------------------------|--------------------------------------------------------------------------|
| `3ls_system_measurement_record`         | `contracts/schemas/3ls_system_measurement_record.schema.json`         | `contracts/examples/3ls_system_measurement_record.example.json`         |
| `3ls_loop_run_record`                   | `contracts/schemas/3ls_loop_run_record.schema.json`                   | `contracts/examples/3ls_loop_run_record.example.json`                   |
| `3ls_handoff_record`                    | `contracts/schemas/3ls_handoff_record.schema.json`                    | `contracts/examples/3ls_handoff_record.example.json`                    |
| `3ls_surface_coverage_record`           | `contracts/schemas/3ls_surface_coverage_record.schema.json`           | `contracts/examples/3ls_surface_coverage_record.example.json`           |
| `3ls_failure_recurrence_record`         | `contracts/schemas/3ls_failure_recurrence_record.schema.json`         | `contracts/examples/3ls_failure_recurrence_record.example.json`         |
| `3ls_trust_gap_closure_record`          | `contracts/schemas/3ls_trust_gap_closure_record.schema.json`          | `contracts/examples/3ls_trust_gap_closure_record.example.json`          |
| `3ls_replayability_record`              | `contracts/schemas/3ls_replayability_record.schema.json`              | `contracts/examples/3ls_replayability_record.example.json`              |
| `3ls_scope_risk_record`                 | `contracts/schemas/3ls_scope_risk_record.schema.json`                 | `contracts/examples/3ls_scope_risk_record.example.json`                 |
| `3ls_operator_debuggability_record`     | `contracts/schemas/3ls_operator_debuggability_record.schema.json`     | `contracts/examples/3ls_operator_debuggability_record.example.json`     |

Tests:

- `tests/test_3ls_measurement_layer.py` — 123 tests covering positive and
  negative validation for every artifact, plus manifest-registration
  assertions and authority-leakage prevention checks.

Architecture docs:

- `docs/architecture/3ls_measurement_layer.md` — describes scope, fail-closed
  rules, downstream consumers (OBS / LIN / REP / SLO), and authority-safe
  wording rules.
- `docs/architecture/system_registry.md` — added a non-authority pointer
  section to the measurement layer.

Manifest:

- `contracts/standards-manifest.json` — added 9 new contract entries.

## Systems covered

The systems explicitly retained from SMA-01 are:

`AEX, PQX, EVL, TPA, CDE, SEL, RIL, FRE, RFX, OBS, LIN, REP, SLO, GOV, REL`

All measurement schemas (system_measurement, handoff, scope-risk,
trust-gap, replayability, etc.) accept any canonical 3LS acronym matching
`^[A-Z0-9]{2,8}$`, aligning with the shape used in
`docs/architecture/system_registry.md`. This avoids a hardcoded enum that
would block measurement records for other registered systems (CTX, TLC,
RAX, JDX, MNT, …) and keeps the schemas resilient to registry growth.

## Measurement dimensions added

| Dimension                  | Captured by                                |
|----------------------------|--------------------------------------------|
| execution_evidence         | `3ls_system_measurement_record`            |
| loop_completion            | `3ls_loop_run_record`                      |
| handoff_integrity          | `3ls_handoff_record`                       |
| surface_coverage           | `3ls_surface_coverage_record`              |
| failure_recurrence         | `3ls_failure_recurrence_record`            |
| trust_gap                  | `3ls_trust_gap_closure_record`             |
| replayability              | `3ls_replayability_record`                 |
| scope_risk                 | `3ls_scope_risk_record`                    |
| operator_debuggability     | `3ls_operator_debuggability_record`        |

## Failure modes now detectable

The fail-closed schema rules turn the following recurring failure shapes
into immediate validation errors instead of silent partial records:

- A loop is reported `complete` but is missing one of execution / eval /
  policy / decision_input / enforcement_signal refs.
- A loop is reported non-complete (partial / blocked / failed) without
  declaring `first_failure_system`.
- A loop is reported non-complete (partial / blocked / failed) but every
  downstream ref is populated — schema rejects this contradiction.
- A handoff is reported `complete` but `downstream_artifact_ref` is null.
- A handoff is `blocked` or `failed` but `reason_codes` is empty.
- A change touches governed surfaces but produces zero
  `mapped_test_targets` (the `pytest_selection_missing` class).
- A failure is recorded with `recurrence_count = 0` or with a malformed
  fingerprint, hiding repeat patterns.
- A replay is claimed available but no `replay_refs` are attached.
- A replay is unavailable but no `replay_gap_reason` is recorded.
- A change touches workflows AND schemas AND scripts but is classified as
  low/medium scope.
- A failure is declared single-artifact debuggable but no
  `required_artifact_refs` are listed.
- Any of the above with `authority_scope` not set to `observation_only`
  (authority leakage prevention).

## Authority-safety guarantees

- Every measurement schema pins `authority_scope` to the const string
  `observation_only`. Validation rejects all other values.
- The architecture doc explicitly states: this layer does not grant
  authority, replace canonical control inputs, or trigger fail-closed
  actions.
- Records reference canonical authority artifacts via `*_ref` fields rather
  than reproducing canonical control or fail-closed payloads inline.
- Authority leak guard (`scripts/run_authority_leak_guard.py`) was run
  against every new file with explicit `--changed-files`; result: pass,
  zero violations.
- Contract compliance gate (`scripts/run_contract_enforcement.py`) was run
  post-registration; result: failures=0, warnings=0.

## Test results

- `tests/test_3ls_measurement_layer.py`: 123 passed.
- `tests/test_contracts.py` + `tests/test_contract_enforcement.py`: 136
  passed (no regressions).
- `pytest tests/ -k "3ls or measurement or contract"`: 1267 passed (no
  regressions).
- `scripts/run_contract_enforcement.py`: failures=0, warnings=0,
  not_yet_enforceable=0.
- `scripts/run_authority_leak_guard.py` (with explicit changed files):
  status=pass, zero violations.

## Gaps remaining

- **Producers not wired.** This delivery defines the measurement contracts
  and validates examples. Wiring code (which OBS/LIN producer emits each
  record, on which trigger) is intentionally out of scope and should be
  proposed as a follow-up under TLC routing rules.
- **Coverage_ratio computation.** `3ls_surface_coverage_record` carries the
  ratio as a number; the canonical computation function is not yet
  centralized. A small helper in `spectrum_systems/modules/...` is the
  natural next step.
- **TLS integration for trust-gap closure.** The schema points at
  `artifacts/tls/*` via `tls_refs` but does not yet declare the canonical
  joiner; that join belongs in a follow-up TLS report transformer.
- **Recurrence fingerprinting.** Schema enforces sha256 shape, but the
  canonical fingerprint algorithm (which fields go in, which order) is not
  yet specified. Fingerprint specification belongs to the producing system,
  not the measurement schema.
- **No producer SLA/SLO yet.** SLO consumption requires emit-frequency
  contracts; those are deferred to a separate SLO budget proposal.

## Recommended next step

Propose **SMA-01 v3 — Measurement Producer Wiring**:

1. Declare the OBS/LIN producer responsible for each artifact type.
2. Define the deterministic emit triggers (loop completion, CI run end,
   PR open, nightly).
3. Add a single canonical helper for `coverage_ratio` and
   `recurrence_fingerprint` so producers cannot drift.
4. Register the producers in `contracts/governance/authority_registry.json`
   as non-owning support entries with `authority_scope =
   observation_only`, mirroring the schema constant.
5. Wire OBS / LIN / REP / SLO consumers to read these artifacts as inputs
   only — never as substitute control evidence.

That follow-up keeps the canonical loop, control, and fail-closed
authorities untouched while finishing the observation surface.
