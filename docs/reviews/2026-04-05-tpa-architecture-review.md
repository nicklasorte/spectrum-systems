# TPA Architecture Review — 2026-04-05

## Review Metadata
- **Review date:** 2026-04-05
- **Repository / Name:** nicklasorte/spectrum-systems — TPA (Plan→Build→Simplify→Gate) architecture
- **Commit / Document version:** branch `claude/store-architecture-review-hqGSr` @ 4d38ce9
- **Reviewer / Agent id:** Claude (reasoning/design agent)
- **Inputs consulted:**
  - `docs/reviews/2026-04-04-tpa-completion-hardening.md`
  - `docs/review-actions/2026-04-04-tpa-completion-hardening-actions.md`
  - `docs/review-actions/PLAN-TPA-001-2026-04-03.md`
  - `docs/review-actions/PLAN-BATCH-TPA-02..06-2026-04-04.md`
  - `contracts/schemas/tpa_slice_artifact.schema.json`
  - `contracts/schemas/tpa_observability_summary.schema.json`
  - `docs/design-review-standard.md`
  - `docs/review-to-action-standard.md`

## Scope
- **In-bounds:** Architectural shape of the TPA slice pattern inside the PQX sequence runner, TPA scope/bypass policy, complexity measurement and simplify gate controls, TPA observability summary, integration with roadmap / control-loop / policy feedback surfaces, governance separation between TPA artifacts and authoritative PQX control authorities.
- **Out-of-bounds:** Implementation-level code correctness inside `spectrum_systems/modules/runtime/pqx_sequence_runner.py`, individual test coverage correctness, downstream engine repo code, rollout scheduling, CI runner configuration.
- **Rationale:** Governance repo responsibility is architecture and contract design, not implementation validation. Implementation review belongs in downstream repos per `CLAUDE.md`.

## Executive Summary
- TPA has matured quickly from a minimal Plan→Build→Simplify→Gate slice pattern into a fail-closed governance sub-system with contract schemas, complexity budgets, scope policy, and observability summary artifacts.
- The architecture correctly keeps TPA as a governed sub-pattern *inside* PQX rather than introducing a parallel execution engine, preserving PQX's authoritative control/eval/enforcement boundaries.
- Risk concentration has shifted from "missing contracts" to "policy surface sprawl": multiple TPA-adjacent policies (scope, complexity, review, cleanup-only) need an explicit composition contract to avoid ambiguous precedence.
- Complexity signal and simplify delete-pass evidence are correctly required at build/simplify/gate — but the governance drift surface (complexity-regression, simplicity-review outcomes) is not yet anchored to the strategy-enforcement layer.
- Observability summary exists as an artifact class, but there is no documented consumer contract connecting its effectiveness metrics back to roadmap prioritization or control-loop learning signals.
- Cleanup-only mode is a high-leverage addition; its fail-closed requirements (bounded scope, equivalence, replay) are well-specified, but lack a canonical certification trail shared with promotion/done gates.
- Bypass-detection and default-routing policies are a net positive, but bypass drift signals need explicit wiring into the control-loop readiness observability plane before TPA can be considered strategy-aligned.

## Maturity Assessment
- **Current level:** 11 / 20 (contract-backed, fail-closed, partially integrated with strategy/control surfaces)
- **Evidence summary:**
  - Contracts exist: `tpa_slice_artifact`, `tpa_observability_summary`, `tpa_scope_policy`.
  - Fail-closed checks: missing complexity signals, missing selection inputs, missing equivalence/replay references all block gate completion.
  - Scoped enforcement lands at promotion and done certification gates.
  - Default routing + bypass drift emission implemented.
- **Unmet criteria for next level:**
  - No canonical composition contract resolving precedence between TPA scope, complexity, review, and cleanup-only policies.
  - Observability summary has no declared downstream consumer contract.
  - Bypass drift signals not yet routed into strategy-enforcement / control-loop readiness.
  - No certification-layer evidence binding TPA outcomes to roadmap prioritization feedback.
- **Next-level blockers:** Policy composition contract, observability consumer contract, bypass-drift→control-loop wiring, certification cohesion.

## Strengths
- TPA is embedded in PQX, not a parallel runtime — preserves authority boundaries and avoids duplicate governance surfaces.
- Contract-first delivery: every new artifact class landed with a schema and golden example before runtime changes were accepted.
- Fail-closed posture is consistent across build/simplify/gate: missing evidence blocks rather than warns.
- Delete-pass evidence requirement gives simplify a concrete, auditable output rather than a vague intent signal.
- Scoped enforcement (promotion + done gates) avoids blanket application and reduces operator friction.
- Cleanup-only mode formalizes "pure simplification" as a distinct, bounded path with equivalence + replay proof — a rare discipline in similar refactor pipelines.

## Structural Gaps
- **Policy composition contract missing:** No single artifact declares how `tpa_scope_policy`, complexity budgets, simplicity review outcomes, and cleanup-only requirements compose when multiple apply simultaneously. Precedence is implicit in runner code.
- **Observability consumer contract missing:** `tpa_observability_summary` is produced but no schema-declared consumer (roadmap prioritizer, control-loop learning, certification) exists. Effectiveness metrics risk becoming write-only.
- **Certification cohesion gap:** Cleanup-only mode produces equivalence + replay references but these are not unified into a single TPA certification envelope consumed by promotion/done gates.
- **Source grounding check:** Source authorities cited — PLAN-TPA-001, PLAN-BATCH-TPA-02..06, tpa_slice_artifact schema, tpa_observability_summary schema. Missing grounding: no explicit link from TPA scope policy to the source-authority layer (`PLAN-SOURCE-AUTHORITY-LAYER-2026-03-28`). Strategy drift risk if scope policy is edited without source-authority refresh.

## Risk Areas
- **Architectural — policy surface sprawl (High severity, High likelihood):** Multiple TPA-adjacent policies without composition contract → ambiguous precedence → strategy drift and reviewer confusion.
- **Architectural — observability orphan (Medium, High):** Summary artifact with no declared consumer → unused instrumentation → erosion of trust in metrics.
- **Governance — bypass-drift signal dead-end (High, Medium):** Bypass drift emitted but not wired into control-loop readiness observability → control bypass risk unmitigated.
- **Governance — certification bypass risk (High, Medium):** Cleanup-only equivalence/replay evidence not certified through a single TPA certification surface → done-gate can admit cleanup slices without unified certification evidence.
- **Operational — complexity budget calibration drift (Medium, Medium):** No documented recalibration/review cadence for complexity budgets → budgets either become rubber-stamp or chronic blockers.
- **Data — schema bypass risk via lightweight mode (Medium, Low):** Lightweight mode reduces evidence requirements; without explicit schema-backed guardrails, future extensions could erode fail-closed posture.
- **Strategy Compliance Check:**
  - Invariant adherence: **FAIL** — TPA scope policy not anchored to source-authority layer; bypass-drift signals not wired to strategy-enforcement.
  - Control-loop role separation: **PASS** — TPA remains a sub-pattern of PQX; execution/eval/control authorities preserved.

## Recommendations
- **R1:** Define a `tpa_policy_composition` contract that declares precedence and merge rules across scope, complexity, review, and cleanup-only policies. Store under `contracts/schemas/` with golden example. *Expected outcome:* Deterministic policy resolution, reviewer-visible precedence. *Addresses:* Gap "policy composition contract missing"; Risk "policy surface sprawl".
- **R2:** Declare a consumer contract for `tpa_observability_summary` binding its effectiveness metrics to at least one of: roadmap prioritizer, control-loop learning signals, or certification. *Expected outcome:* Closed feedback loop, no orphan artifacts. *Addresses:* Gap "observability consumer contract"; Risk "observability orphan".
- **R3:** Wire TPA bypass drift signals into control-loop readiness observability (`PLAN-CTRL-LOOP-04-READINESS-OBSERVABILITY`). *Expected outcome:* Bypass drift visible in readiness plane; control-bypass risk mitigated. *Addresses:* Risk "bypass-drift dead-end"; Strategy invariant FAIL.
- **R4:** Introduce a unified TPA certification envelope that merges equivalence + replay + observability references for cleanup-only slices and is consumed by promotion and done gates. *Expected outcome:* Single certification surface at done gate. *Addresses:* Gap "certification cohesion"; Risk "certification bypass".
- **R5:** Anchor `tpa_scope_policy` to the source-authority layer with a documented refresh trigger. *Expected outcome:* Scope policy edits require source-authority refresh; strategy drift prevented. *Addresses:* Source grounding check; Strategy invariant FAIL.
- **R6:** Document a complexity-budget recalibration cadence + review trigger (e.g., each control-loop cycle or N slices). *Expected outcome:* Budgets remain meaningful over time. *Addresses:* Risk "complexity budget calibration drift".
- **R7:** Add schema-backed guardrails to lightweight mode so it cannot drop evidence fields outside an explicit allowlist. *Expected outcome:* Lightweight mode remains fail-closed. *Addresses:* Risk "schema bypass via lightweight mode".

## Priority Classification
- **Critical:** R3 (bypass-drift wiring), R5 (source-authority anchoring) — required to close strategy invariant FAIL.
- **High:** R1 (policy composition contract), R4 (certification envelope) — required to prevent governance drift and certification bypass.
- **Medium:** R2 (observability consumer), R6 (complexity budget cadence), R7 (lightweight-mode guardrails).
- **Low:** None at this time.

## Extracted Action Items
1. **Wire TPA bypass drift into control-loop readiness observability** — Owner: Control-loop governance. Artifact: updated readiness observability contract + TPA drift signal binding. Acceptance: Bypass drift events surface in readiness plane with schema-backed shape. (Ref: R3)
2. **Anchor `tpa_scope_policy` to source-authority layer** — Owner: Strategy governance. Artifact: updated scope policy doc + source-authority refresh trigger. Acceptance: Scope policy edits fail-closed without source-authority refresh evidence. (Ref: R5)
3. **Create `tpa_policy_composition` contract** — Owner: Governance contracts. Artifact: schema + golden example + composition rules doc. Acceptance: Runner resolves policy precedence from contract, not code. (Ref: R1)
4. **Define TPA certification envelope** — Owner: Certification / promotion-gate owners. Artifact: certification envelope schema + promotion/done gate consumer wiring. Acceptance: Cleanup-only slices must present envelope; done gate consumes it. (Ref: R4)
5. **Declare `tpa_observability_summary` consumer contract** — Owner: Roadmap / control-loop learning. Artifact: consumer contract doc + binding schema. Acceptance: At least one declared consumer with contract-backed read path. (Ref: R2)
6. **Document complexity-budget recalibration cadence** — Owner: TPA governance. Artifact: cadence doc + review trigger entry. Acceptance: Cadence documented, trigger registered in review registry. (Ref: R6)
7. **Add schema-backed allowlist for lightweight mode evidence drop** — Owner: Governance contracts. Artifact: schema update + test. Acceptance: Lightweight mode cannot drop non-allowlisted evidence. (Ref: R7)

## Blocking Items
- **B1 (Strategy invariant):** Until R3 and R5 land, TPA cannot be declared strategy-aligned. Progression of any TPA maturity-level advancement is blocked.
- **Governance Drift Check:**
  - Schema bypass: no open bypass identified; R7 closes latent surface.
  - Control bypass: **OPEN** — bypass drift not yet wired to control-loop readiness (R3).
  - Missing eval/trace/certification: **PARTIAL** — certification envelope absent (R4).
  - Duplicate governance surface: not observed; TPA remains inside PQX.

## Deferred Items
- **D1:** Downstream roadmap prioritizer consumption of TPA observability — deferred until R2 declares the consumer contract; trigger = R2 complete.
- **D2:** Cross-repo TPA pattern propagation to implementation repos — deferred until policy composition contract (R1) stabilizes; trigger = R1 merged + one full control-loop cycle.

## Mandatory Operational Checks
- strategy alignment: **no** (blocked on R3, R5)
- source grounding: **partial** (source authorities cited; R5 required to anchor scope policy)
- eval evidence present: **yes** (complexity signals, selection inputs, delete-pass evidence)
- traceability evidence present: **yes** (replay references in cleanup-only mode)
- certification evidence present when required: **partial** (R4 required for cleanup-only unified envelope)
- control decision/enforcement separation preserved: **yes**
