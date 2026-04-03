# Repo Process Flow

## Basic flow
Review Snapshot
  ↓
Repo Health Eval
  ↓
Eval Summary
  ↓
Control Decision
  ↓
Roadmap Selection
  ↓
Control Authorization
  ↓
Authorized Batch Execution (PQX)
  ↓
Roadmap Progress Update (roadmap_progress_update)
  ↓
Loop Validation (roadmap_execution_loop_validation)
  ↓
Stop-or-Continue Decision (bounded by max_batches_per_run + hard-stop conditions)
  ↓
Next Candidate Selection (if allowed, within run limit)
  ↓
Artifacts Produced
  ↓
Replay + Determinism

## Expanded flow
Review Snapshot (repo_review_snapshot)
  ↓
Eval Runner (repo_health_eval)
  - redundancy density: 0.9333333333333333
  - drift risk: 0.0
  - readiness score: 0.9333333333333333
  ↓
Eval Summary
  ↓
Control Loop
  - allow / warn / freeze / block => warn
  ↓
Roadmap Generator
  - build targets: MAP-004-roadmap-integration, MAP-DOC-flow-generation
  - hardening targets: MAP-003-review-gate-enforcement
  - sequencing constraints: 2
  ↓
Roadmap Selection (roadmap_selection_result)
  - deterministic next-batch proposal only
  ↓
Control Authorization (roadmap_execution_authorization)
  - control decision allow|warn|freeze|block gates execution
  ↓
Authorized Batch Execution (PQX)
  - slice execution: PQX-QUEUE-01, PQX-QUEUE-02, PQX-QUEUE-03
  - per-slice enforcement: enabled
  ↓
Roadmap Progress Update (roadmap_progress_update)
  - selected batch only state mutation
  - deterministic status transition + trace linkage
  ↓
Loop Validation (roadmap_execution_loop_validation)
  - stage consistency, replay readiness, determinism checks
  - bounded multi-batch continuation under strict stop conditions
  ↓
Stop-or-Continue Decision (bounded by max_batches_per_run + hard-stop conditions)
  - stop immediately on freeze/block/failure/missing-signal/replay/hard-gate/max-limit conditions
  ↓
Next Candidate Selection (if allowed, within run limit)
  ↓
Artifacts
  - execution record
  - eval summary
  - control decision
  ↓
Replay + Determinism Check

## Current Weak Points
- bounded chaining remains deterministic only when evaluated_at/executed_at/validated_at timestamps are fixed by caller
- replay chain fails closed when any required stage ref is missing
- eval signal present: repo_redundancy_density_high
- high redundancy across inspected files

## Derived Roadmap Steps
- hardening::MAP-003-review-gate-enforcement
- consolidation::control-loop-review-gating-path-consolidation
- defer::new-module-expansion-outside-map-scope
