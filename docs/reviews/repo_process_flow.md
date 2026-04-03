# Repo Process Flow

## Basic flow
Program Direction (PRG)
  ↓
Review Triggering + Artifacts (RVW/RPT)
  ↓
Review → Eval → Control
  ↓
Context Selection / Ranking / Injection (CTX)
  ↓
TPA Plan → Build → Simplify → Gate
  ↓
Roadmap Selection + Authorization (MAP/RDX)
  ↓
Bounded Batch Execution + Progress
  ↓
Certification + Stop Conditions
  ↓
Replay + Determinism Proof

## Expanded flow
Program Direction Layer (program_artifact)
  - constraint propagation to roadmap execution targets
  - no override of control freeze/block authority
  ↓
Review Triggering + Artifact Layer (review_artifact / review_control_signal)
  - review produces evidence + findings only
  - review cannot directly authorize execution
  ↓
Review → Eval Bridge (review_eval_bridge)
  - deterministic translation of review signal to eval_result
  ↓
Control Layer
  - allow / warn / freeze / block => warn
  - hard-stop control outcomes remain authoritative
  ↓
Context Layer (context_bundle_v2)
  - deterministic selection + ranking
  - context remains advisory (cannot alter control authority)
  ↓
TPA Layer (plan/build/simplify/gate)
  - constrained by context + review/eval risk references
  - gate does not replace control; gate only verifies local build discipline
  ↓
Roadmap Generation + Selection (MAP)
  - deterministic next-batch proposal only
  - program constraints applied before selection output is finalized
  ↓
Roadmap Execution (RDX + PQX)
  - bounded batch execution under control authorization
  - single-batch loop validation + multi-batch stop-reason enforcement
  ↓
Progress + Certification
  - roadmap_progress_update + control_loop_certification_pack
  ↓
Stop-or-Continue Decision
  - stop immediately on freeze/block/failure/missing-signal/replay/hard-gate/max-limit conditions
  - no silent continuation beyond bounded execution policy
  ↓
Replay + Determinism
  - replay chain complete only with program/review/context/tpa/roadmap/control/cert refs

### Compatibility details (current run snapshot)
Review Snapshot (repo_review_snapshot)
  ↓
Eval Runner (repo_health_eval)
  - redundancy density: 0.9333333333333333
  - drift risk: 0.0
  - readiness score: 0.9333333333333333
  ↓
Eval Summary
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
