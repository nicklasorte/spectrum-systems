This file is subordinate to docs/roadmap/system_roadmap.md

# Spectrum Systems — PQX Protocol Hardening Roadmap

## System Goal
Evolve Spectrum Systems from a roadmap-driven execution engine into a **self-governing execution system** by baking execution rules, validation gates, and failure constraints into repo-native protocol layers so PQX slices rely minimally on prompt text and maximally on enforced system behavior.

## Architectural Invariants

- All PQX slices must be governed by repo-native protocols, not prompt repetition
- No slice executes without passing pre-flight validation
- All outputs must be artifact-first, schema-valid, and trace-linked
- Fail-closed behavior is enforced at every boundary
- Determinism is mandatory across execution, decisions, and replay
- No hidden state, side-channel logic, or implicit coupling allowed
- Backward compatibility must be preserved unless explicitly retired via governance

## Execution Rules (PQX)

- Each row = one protocol-hardening slice
- Prefer MODIFY EXISTING enforcement layers over adding new parallel systems
- Protocol logic must be centralized, not duplicated across modules
- All protocol rules must be testable and enforceable (not advisory)
- Protocol enforcement must run automatically with each PQX slice
- No slice may bypass protocol validation

## Relationship to PQX Queue Roadmap

The PQX Queue Roadmap defines the queue execution system itself. This PQX Protocol Hardening Roadmap defines the governance and enforcement layers that reduce reliance on repeated prompt text. Queue rows build system capability, while protocol rows bake repeated execution rules into repo-native enforcement. This protocol roadmap hardens and governs queue execution; it does not replace the queue roadmap. Future work may map protocol rows to queue rows explicitly, but this file remains a protocol-layer roadmap.

## Roadmap Table

| Step ID | Step Name | What It Builds | Why It Matters | Source Basis | Existing Repo Seams | Implementation Mode | Contracts / Schemas | Artifact Outputs | Integration Points | Control Loop Coverage | Dependencies | Definition of Done | Prompt Class | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [ROW: PQX-PROT-01] | Pre-flight validation gate | Enforces roadmap row existence, dependency validity, scope declaration before execution | Prevents invalid or out-of-order slices from running | SOURCE GAP | existing plan + scope verification scripts | MODIFY EXISTING | `pqx_preflight_validation.schema.json` | preflight validation artifact | all PQX slice entrypoints | O | — | Slice cannot run without passing preflight checks | governance | PLANNED |
| [ROW: PQX-PROT-02] | Artifact completeness gate | Validates required artifacts per slice before marking success | Prevents “tests passed but no artifacts” failures | SOURCE GAP | contract enforcement + artifact IO | MODIFY EXISTING | extend existing schemas | completeness validation artifact | post-slice validation | I | PQX-PROT-01 | All required artifacts exist and validate | governance | PLANNED |
| [ROW: PQX-PROT-03] | Decision trace enforcement | Requires reason codes + lineage for all decisions | Enables explainability and auditability | SOURCE + REPO | decision artifacts | MODIFY EXISTING | extend decision schemas | enriched decision artifacts | control layer | D | PQX-PROT-02 | All decisions include trace + reasons | governance | PLANNED |
| [ROW: PQX-PROT-04] | No-orphan artifact rule | Ensures all artifacts link to trace + upstream artifacts | Prevents disconnected outputs | SOURCE GAP | artifact envelope + lineage | MODIFY EXISTING | extend lineage schema | validated lineage graph | artifact system | L | PQX-PROT-02 | All artifacts connected via lineage | governance | PLANNED |
| [ROW: PQX-PROT-05] | State-machine integrity enforcement | Enforces valid queue state transitions | Prevents state corruption | SOURCE + REPO | queue_state_machine | MODIFY EXISTING | extend state schema | state validation artifacts | queue loop | D / E | QUEUE-05 | Illegal transitions fail closed | governance | PLANNED |
| [ROW: PQX-PROT-06] | Idempotency enforcement | Guarantees same input → same output | Enables safe replay and retries | SOURCE GAP | execution + artifact layers | ADD NEW | `pqx_idempotency_record.schema.json` | idempotency validation artifact | execution loop | O / L | PQX-PROT-02 | Duplicate runs produce identical artifacts | governance | PLANNED |
| [ROW: PQX-PROT-07] | Replay parity enforcement | Ensures replay produces identical decisions | Required for trust and debugging | SOURCE + REPO | replay_engine | MODIFY EXISTING | extend replay schema | replay parity report | replay + control | L | PQX-PROT-06 | Replay matches original execution | governance | PLANNED |
| [ROW: PQX-PROT-08] | Drift detection (lightweight) | Detects unexpected changes vs baseline | Prevents silent behavior drift | SOURCE GAP | observability + replay | ADD NEW | `pqx_drift_report.schema.json` | drift report artifact | observability | O / L | PQX-PROT-07 | Drift detected and flagged | governance | PLANNED |
| [ROW: PQX-PROT-09] | Policy version pinning | Ties decisions to explicit policy versions | Prevents hidden policy drift | SOURCE + REPO | policy_registry | MODIFY EXISTING | extend policy schema | policy version artifacts | control layer | D | PQX-PROT-03 | All decisions reference policy version | governance | PLANNED |
| [ROW: PQX-PROT-10] | Standard error taxonomy | Normalizes error types across system | Improves debugging + observability | SOURCE GAP | error handling seams | ADD NEW | `pqx_error_record.schema.json` | error artifacts | all layers | O / D | PQX-PROT-02 | All errors classified and bounded | governance | PLANNED |
| [ROW: PQX-PROT-11] | Queue run envelope | Aggregates all artifacts per run | Enables audit and replay | SOURCE GAP | artifact system | ADD NEW | `pqx_run_envelope.schema.json` | run envelope artifact | queue + audit | L | QUEUE-07 | Complete run bundle exists | governance | PLANNED |
| [ROW: PQX-PROT-12] | Step budget guardrails | Limits retries, children, steps | Prevents runaway execution | SOURCE GAP | queue + retry system | MODIFY EXISTING | extend policy schema | budget enforcement artifacts | queue loop | D / E | QUEUE-06 | Limits enforced fail-closed | governance | PLANNED |
| [ROW: PQX-PROT-13] | System boundary enforcement | Prevents cross-layer logic leakage | Maintains architecture integrity | SOURCE + REPO | module boundaries | MODIFY EXISTING | boundary validation rules | boundary validation artifact | all modules | O | — | Violations fail closed | governance | PLANNED |
| [ROW: PQX-PROT-14] | Golden path enforcement | Ensures all slices follow canonical flow | Prevents fragmentation | SOURCE + REPO | control chain | MODIFY EXISTING | extend control schemas | golden path validation | control loop | O / I / D | — | All slices follow canonical flow | governance | PLANNED |
| [ROW: PQX-PROT-15] | Canonical naming enforcement | Enforces consistent naming across artifacts | Prevents entropy | SOURCE GAP | artifact IO | MODIFY EXISTING | naming rules | validated artifact names | artifact layer | O | — | All artifacts follow naming rules | governance | PLANNED |
| [ROW: PQX-PROT-16] | No hidden coupling rule | Ensures all dependencies are explicit | Prevents fragile systems | SOURCE GAP | execution + state | MODIFY EXISTING | dependency validation | dependency graph artifact | execution | O / L | — | No implicit dependencies exist | governance | PLANNED |
| [ROW: PQX-PROT-17] | Promotion gating enforcement | Ensures no premature completion | Maintains trust boundaries | SOURCE + REPO | certification gate | MODIFY EXISTING | extend certification schema | promotion decision artifact | governance layer | D / E | GOV-10 | Nothing completes without certification | governance | PLANNED |
| [ROW: PQX-PROT-18] | Operator override governance | Controlled manual override system | Enables safe human intervention | SOURCE GAP | control + governance | ADD NEW | `pqx_override_record.schema.json` | override artifact | control loop | D | — | Overrides explicit, logged, bounded | governance | PLANNED |
