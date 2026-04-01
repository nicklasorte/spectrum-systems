# Strategy Control Document

## Role in Spectrum Systems

This document is the governing control surface for:
- roadmap generation
- architectural alignment
- drift detection and correction

It is authoritative over:
- roadmap prompts
- architecture decisions
- implementation sequencing

All roadmap steps must be validated against this document before execution.

## Purpose
Define the governing control rules for roadmap generation, execution ordering, and architecture drift prevention so Spectrum Systems remains fail-closed, source-grounded, and control-loop-complete.

## North Star
Deliver a true MVP closed-loop control system where failures materially and measurably change future decisions, enforcement, and promotion outcomes through governed artifacts.

## Strategy Thesis
Spectrum Systems should expand only after trust closure is proven:
1. stabilize one dominant trusted sequential path,
2. hard-bind learning into policy/control authority,
3. then scale grouped execution and later AI execution boundaries under certification and replay discipline.

## Non-Negotiable Invariants
- artifact-first
- schema-first
- eval-mandatory
- control authority externalized
- replayable
- fail-closed
- certification-gated

## Stable Layers vs Replaceable Layers
### Stable (must not drift)
- Contract/artifact spine (`contracts/schemas/`, standards manifest)
- Control decisions and enforcement semantics
- Certification/promotion gates
- Replay and audit lineage obligations
- Roadmap authority bridge (`docs/roadmaps/roadmap_authority.md`)

### Replaceable (bounded evolution allowed)
- Model/provider adapters
- Retrieval implementation internals
- Prompt templates and strategy of execution
- Queue/routing heuristics that do not violate stable contracts

## Control Loop Definition
- **Observe:** collect governed artifacts from execution, outcomes, and observability.
- **Interpret:** evaluate quality/risk with deterministic eval outputs.
- **Decide:** issue explicit control decisions from policy-governed artifacts.
- **Enforce:** execute allow/warn/freeze/block/remediate actions with traceable artifacts.

## Authoritative Input Stack for Roadmap Generation (Canonical Order)
1. `docs/architecture/strategy-control.md`
2. `docs/architecture/foundation_pqx_eval_control.md`
3. `docs/architecture/ai_operating_substrate_and_artifact_intelligence.md`
4. current repository state
5. `docs/roadmaps/system_roadmap.md`
6. source design documents / architecture artifacts

This order is mandatory across strategy, roadmap prompts, roadmap authority notes, and roadmap generation outputs.

## Control Loop Closure Gate
Pre-expansion gate requirements:

### CL-01 Failure Binding
- **What:** mandatory `failure -> eval case -> policy linkage`.
- **Why now:** avoids advisory-only learning.
- **Risk reduced:** repeated known failures.
- **Loop stage:** Learn -> Decide.
- **Proof artifacts:** failure classification + linked eval additions + policy updates/references.
- **Blocks until passed:** grouped expansion and promotion-hardening confidence claims.

### CL-02 Error Budget Engine
- **What:** burn-rate/budget signals drive warn/freeze/block transitions.
- **Why now:** logging-only budgets cannot enforce trust boundaries.
- **Risk reduced:** uncontrolled degradation.
- **Loop stage:** Interpret -> Enforce.
- **Proof artifacts:** budget status + escalation record + enforcement action/outcome.
- **Blocks until passed:** multi-slice trust and promotion safety.

### CL-03 Recurrence Prevention Enforcement
- **What:** critical failure classes require regression fixtures and/or policy tightening.
- **Why now:** closure without prevention is incomplete.
- **Risk reduced:** recurrence at larger scale.
- **Loop stage:** Validation -> Prevention.
- **Proof artifacts:** remediation closure linked to prevention assets.
- **Blocks until passed:** grouped autonomous repair trust.

### CL-04 Judgment Authority Activation
- **What:** judgment/policy artifacts must directly influence transition and enforcement decisions.
- **Why now:** side-channel judgment records provide no control power.
- **Risk reduced:** policy bypass and inconsistent decisions.
- **Loop stage:** Decide -> Enforce.
- **Proof artifacts:** judgment application/lifecycle evidence consumed by control decisions.
- **Blocks until passed:** judgment-driven scale-up.

### CL-05 Longitudinal Calibration Loop
- **What:** delayed truth/audit outcomes feed calibration and freeze/revoke controls.
- **Why now:** immediate evals alone cannot detect long-horizon drift.
- **Risk reduced:** stale or degraded policy operation.
- **Loop stage:** Observe -> Learn -> Decide.
- **Proof artifacts:** outcome labels + calibration artifacts + freeze/revoke records.
- **Blocks until passed:** confidence-grade N-slice and canary expansion.

## Strategy-to-Roadmap Operating Loop (Mandatory)
Roadmap generation MUST, in every generation cycle:
1. inspect repository state,
2. inspect roadmap state,
3. inspect strategy control,
4. inspect `foundation_pqx_eval_control.md`,
5. inspect `ai_operating_substrate_and_artifact_intelligence.md`,
6. detect gaps between repository reality and the required foundation + substrate chain,
7. classify each foundation/substrate layer (`present_and_governed`, `present_but_partial`, `present_but_bypassable`, `missing`, `ambiguous`),
8. prioritize foundation and must-add substrate hardening before expansion,
9. block expansion when required foundation or must-add substrate layers are missing, partial, bypassable, or ambiguous,
10. report whether the golden path and minimum viable artifact-intelligence slice are currently buildable.

## Hard Foundation-First and Substrate-First Gate Rule
No roadmap may advance broader capability if required foundation layers or must-add substrate layers are missing, partial, ambiguous, or bypassable.

Expansion of agent behavior, workflows, model breadth, artifact-family breadth, or autonomy is non-compliant until foundation and must-add substrate hardening close those gaps and both chains are non-bypassable.

## Roadmap Generation Rules
1. Resolve authority via `docs/roadmaps/roadmap_authority.md`.
2. Enforce canonical input stack order (strategy, foundation, substrate, repo, roadmap, source artifacts).
3. Compare repository state against `docs/architecture/foundation_pqx_eval_control.md` before proposing steps.
4. Compare repository state against `docs/architecture/ai_operating_substrate_and_artifact_intelligence.md` before proposing steps.
5. Update `docs/roadmaps/system_roadmap.md` as editorial source.
6. Mirror parse-critical changes in `docs/roadmap/system_roadmap.md` until migration ends.
7. Missing or weak foundation/must-add substrate seams must be prioritized before expansion.
8. Every roadmap row must state trust gain (safer/measurable/trustworthy/replayable/policy/certification/recurrence prevention).

## Drift Detection and Correction
Drift indicators:
- missing strategy/source linkage in progression artifacts,
- policy/eval/certification bypass,
- duplicate governance seams,
- roadmap authority ambiguity,
- repository state diverges from required chain: `PQX -> output_artifact -> eval_result/eval_summary -> control_decision -> enforcement_action -> replay/trace`,
- missing prompt/task lifecycle governance,
- direct model calls outside adapter contracts,
- missing routing decision artifacts,
- missing context admission artifacts,
- missing eval registry or stale eval-slice coverage,
- missing judgment reuse artifacts,
- missing derived artifact intelligence jobs,
- AI expansion without corresponding measurement/governance surface growth.

Correction actions:
- fail closed progression,
- emit remediation artifacts,
- require roadmap + mirror reconciliation in the same change set,
- run changed-scope verification before commit,
- classify and prioritize foundation and substrate hardening gaps before any expansion.

## Review / Prompting Enforcement
- One prompt, one primary type (`PLAN`, `BUILD`, `WIRE`, `VALIDATE`, `REVIEW`).
- Multi-file governance changes require a plan in `docs/review-actions/` before implementation.
- Review findings must feed prioritized fix bundles and recurrence prevention assets.
- Foundation/substrate-vs-roadmap mismatch is recorded as a hardening gap and prioritized for closure; do not rewrite architecture to fit roadmap drift.

## Default Build Priorities
1. Artifact schemas
2. Eval coverage
3. Deterministic control
4. Fail-closed enforcement
5. Replay integrity
6. Trace completeness
7. Control Loop Closure Gate (CL-01..CL-05)
8. Must-add substrate layers from `ai_operating_substrate_and_artifact_intelligence.md`
9. Dominant sequential trust path and grouped PQX path
10. Review/fix recurrence hardening
11. Certification/audit/promotion closure
12. Source authority runtime hardening
13. Later AI execution expansion

Broader AI expansion is blocked when must-add substrate layers remain missing or bypassable.

## Definition of Success
Success means Spectrum Systems can demonstrate, with governed artifacts, that failures are converted into enforced prevention and policy/control updates over time, with replayable certification-grade evidence, foundation-first and substrate-first sequencing compliance, and no authority ambiguity.
