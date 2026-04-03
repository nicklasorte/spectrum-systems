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
Roadmap Generation
  ↓
PQX Batch Execution
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
PQX Execution
  - slice execution: PQX-QUEUE-01, PQX-QUEUE-02, PQX-QUEUE-03
  - per-slice enforcement: enabled
  ↓
Artifacts
  - execution record
  - eval summary
  - control decision
  ↓
Replay + Determinism Check

## Current Weak Points
- eval signal present: repo_redundancy_density_high
- high redundancy across inspected files

## Derived Roadmap Steps
- hardening::MAP-003-review-gate-enforcement
- consolidation::control-loop-review-gating-path-consolidation
- defer::new-module-expansion-outside-map-scope
