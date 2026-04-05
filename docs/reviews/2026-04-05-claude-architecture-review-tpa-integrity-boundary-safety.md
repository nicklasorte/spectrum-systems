# Architecture Review

## Review Metadata
- **Review date:** 2026-04-05
- **Scope:** TPA-02 through TPA-08B
- **System boundary under review:** TPA as a governed sub-pattern inside PQX control architecture
- **Primary evidence surfaces:**
  - `docs/review-actions/PLAN-BATCH-TPA-02-2026-04-04.md`
  - `docs/review-actions/PLAN-BATCH-TPA-03-2026-04-04.md`
  - `docs/review-actions/PLAN-BATCH-TPA-04-2026-04-04.md`
  - `docs/review-actions/PLAN-BATCH-TPA-05-2026-04-04.md`
  - `docs/review-actions/PLAN-BATCH-TPA-06-2026-04-04.md`
  - `docs/review-actions/PLAN-BATCH-TPA-08A-2026-04-05.md`
  - `docs/review-actions/PLAN-BATCH-TPA-08B-2026-04-05.md`
  - `contracts/schemas/tpa_scope_policy.schema.json`
  - `contracts/schemas/tpa_policy_composition.schema.json`
  - `contracts/schemas/tpa_certification_envelope.schema.json`
  - `contracts/schemas/tpa_observability_summary.schema.json`
  - `contracts/schemas/tpa_observability_consumer_record.schema.json`
  - `contracts/schemas/tpa_policy_candidate.schema.json`
  - `contracts/schemas/complexity_budget_recalibration_record.schema.json`
  - `spectrum_systems/modules/runtime/pqx_sequence_runner.py`
  - `spectrum_systems/modules/runtime/tpa_complexity_governance.py`
  - `spectrum_systems/modules/governance/tpa_policy_composition.py`
  - `spectrum_systems/modules/governance/done_certification.py`
  - `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py`
  - `spectrum_systems/orchestration/cycle_observability.py`
  - `tests/test_tpa_sequence_runner.py`
  - `tests/test_tpa_policy_composition.py`
  - `tests/test_tpa_scope_policy.py`
  - `tests/test_autonomy_guardrails.py`
  - `tests/test_hitl_override_enforcement.py`

---

## 1. Overall Assessment
**Judgment: conditionally sound.**

Bluntly: TPA is still inside the cage, but the cage now has more moving parts than it should.

What is solid:
- TPA is still subordinate to PQX execution instead of becoming a second orchestrator.
- Certification cohesion materially improved with `tpa_certification_envelope` wired into done and promotion gates.
- Policy precedence is now explicit and contract-backed, not entirely hidden in runner control flow.
- Lightweight mode no longer looks like an unbounded escape hatch.

What is not solid enough yet:
- TPA now produces enough internal signals to start steering itself indirectly through roadmap/control surfaces.
- Some control recommendations are still generated from TPA-local metrics with static weights; this is deterministic but strategically brittle.
- Human override is auditable, but not expiry-bounded at the artifact contract level.

Net: this is **not structurally risky today**, but it can become risky if loop amplification is not constrained now.

## 2. Critical Risks (Ranked)

1. **Signal self-coupling risk (highest severity).**  
   TPA-generated observability and complexity artifacts are now feeding recommendation surfaces (`recommended_control_decision`, priority scoring, health mode) that can affect scheduling and hardening emphasis. If those signals drift or are gamed, TPA can ratchet policy pressure using its own outputs. This is not an authority breach yet, but it is the main path to shadow governance behavior.

2. **Override persistence risk (high severity).**  
   HITL override artifacts are scoped and auditable, but the canonical override contract has no expiry/TTL requirement. Without explicit expiration semantics, “allow_once” can become de facto durable in operational practice even if code currently enforces one-shot behavior.

3. **Governance burden growth risk (high severity).**  
   TPA now requires policy composition, scope policy anchoring, complexity budgets/trends/campaigns, observability summary + consumer records, recalibration records, and certification envelope cohesion. This is controlled, but operational drag is approaching the point where teams will start seeking bypasses.

## 3. Structural Weaknesses

- **Static heuristic hard-coding remains in complexity governance.** Deterministic scoring/weights are good for replay, but static constants become stale and can bias control recommendations over time.
- **Consumer surface is singular.** `tpa_observability_consumer_record` is pinned to `control_loop_learning` only; if that consumer degrades or becomes ceremonial, TPA observability weakens again.
- **Promotion readiness can be over-indexed to local gates.** The TPA envelope enforces local gate quality well, but the architecture still depends on external control surfaces to prevent local-optimum promotion decisions.

## 4. Control Loop Integrity

Separation is mostly intact:
- **Execution:** PQX runner and slice execution path remain distinct.
- **Eval:** TPA complexity/simplicity outputs are produced as artifacts.
- **Control:** Policy composition and decision ranking determine control posture.
- **Enforcement:** Done and promotion gates consume certified artifacts and fail closed.
- **Certification:** Unified envelope now acts as canonical TPA certification surface.

No direct evidence that TPA can self-authorize enforcement. Control-loop purity is preserved **with caveats** about recommendation feedback concentration.

## 5. Boundary Safety Assessment

TPA remains bounded and subordinate to PQX/control.

Strong boundary controls present:
- Required-scope checks and missing-lineage decisions can block/freeze.
- Bypass drift is surfaced into readiness observability.
- Promotion/done paths explicitly require certified TPA evidence when scope requires it.

Boundary weakness that still matters:
- TPA’s policy and observability outputs are now rich enough to influence backlog/policy pressure; without cross-surface dampening rules, influence can exceed intended advisory weight.

## 6. Policy Safety Assessment

Policy safety is substantially better than pre-08A/08B.

- `tpa_policy_candidate` is explicitly review-only (`review_required=true`, `auto_apply=false`) — good.
- `tpa_policy_composition` makes precedence explicit and deterministic — good.
- Lightweight evidence omission is now constrained by explicit allowlist contract — good.

Remaining risk:
- Policy remains understandable at contract level, but not yet operator-light; too many policy artifacts means policy intent can still be misunderstood even when formally deterministic.

## 7. Certification and Promotion Assessment

This area improved the most.

- Unified `tpa_certification_envelope` is real and consumed.
- Cleanup-only mode is certified through the same canonical surface with explicit equivalence/replay requirements.
- Promotion path blocks on missing/invalid/un-certified envelope evidence.

Residual concern:
- Certification is coherent, but growing evidence fan-out makes operational failures more likely due to missing references rather than true risk findings.

## 8. Observability / Consumer Assessment

Not orphaned anymore. Observability now has a contract-backed consumer path.

What works:
- Summary metrics include bypass telemetry and simplification outcomes.
- Consumer record proves declared downstream consumption.

What is weak:
- Consumption is still narrow and internally coupled to control-loop learning semantics.
- No explicit anti-ritual test proving observability changed a governance outcome in a bounded, auditable way.

## 9. Determinism / Replay Assessment

Determinism and replay posture are strong.

- Contract validation and fail-closed checks are pervasive.
- Selection logic and policy composition are deterministic for same inputs.
- Tests assert deterministic behavior across repeated runs.

Replay caveat:
- Deterministic does not equal stable governance quality. Static weights and thresholds replay perfectly even when they become strategically wrong.

## 10. Feedback Loop Risks

Loop analyzed: **TPA signals → roadmap/control weighting → PQX execution → new TPA signals → policy candidates → governance**.

Main risks:
- **Amplification:** repeated degradation signals can push hardening-first mode aggressively, starving forward capability work.
- **Oscillation:** cleanup campaigns can alternate with expansion pressure if thresholds are tight and not recalibrated with external context.
- **Circular legitimation:** TPA can generate evidence that justifies tightening TPA constraints, recursively increasing bureaucracy.

Current mitigations exist (review-required policy candidates, recalibration record), but damping logic is still light.

## 11. Recommended Fixes (Rack and Stack)

### Fix now
1. **Add override expiration semantics to canonical HITL override contract.**  
   Require `expires_at` and explicit max validity window; block expired overrides at enforcement boundary.
2. **Add loop-dampening rule to control prioritization.**  
   Require independent non-TPA corroboration before two consecutive hardening escalations driven primarily by TPA-local metrics.
3. **Add anti-ritual observability acceptance check.**  
   Require at least one governance decision trace to cite `tpa_observability_consumer_record` inputs each cycle, or mark observability path degraded.

### Fix next
1. **Introduce strategy-level recalibration guardrails for scoring constants.**  
   Keep deterministic constants, but require periodic reviewed re-baselining with explicit before/after impact artifact.
2. **Define evidence fan-out budget for TPA certification.**  
   Cap mandatory evidence references by mode to prevent procedural overload from becoming bypass pressure.
3. **Broaden observability consumer options without duplicating authority.**  
   Allow additional declared consumers while preserving PQX/control supremacy.

### Monitor only
1. Rate of `lightweight` usage in required scope.
2. Ratio of hardening-priority decisions to net forward roadmap throughput.
3. Frequency of policy-candidate generation by module family (watch for local feedback lock-in).

## 12. What NOT to Change

Do **not** simplify away the parts that are currently keeping this safe:

- Do not remove contract-backed policy composition.
- Do not split certification again after introducing unified TPA certification envelope.
- Do not downgrade cleanup-only equivalence/replay requirements.
- Do not bypass required-scope fail-closed behavior to reduce friction.
- Do not convert review-only policy candidates into auto-apply behavior.
- Do not relax deterministic replay surfaces in favor of adaptive hidden heuristics.

---

## Action Tracker Seed (Directly Mappable)

| Action ID | Priority | Type | Owner Surface | Concrete change | Acceptance signal | Blocker class |
| --- | --- | --- | --- | --- | --- | --- |
| TPA-ACT-08B-AR-01 | P0 | Contract + Enforcement | HITL governance | Add `expires_at` + max validity policy to `hitl_override_decision` and enforce expiry fail-closed. | Expired override artifacts are rejected deterministically in enforcement tests. | Integrity blocker |
| TPA-ACT-08B-AR-02 | P0 | Control damping | Control-loop governance | Add non-TPA corroboration requirement before repeated hardening escalation triggered by TPA-local signals. | Two-step escalation without corroboration fails closed and emits explicit reason code. | Stability blocker |
| TPA-ACT-08B-AR-03 | P1 | Observability efficacy | Observability governance | Add cycle-level proof that observability consumer artifacts influenced at least one governance decision or mark degraded path. | Readiness/status artifacts include observability-impact state each cycle. | Cohesion weakness |
| TPA-ACT-08B-AR-04 | P1 | Recalibration governance | Architecture governance | Add reviewed recalibration mechanism for scoring weights/thresholds with before/after evidence. | Recalibration record includes approved diff and replay-impact summary. | Drift weakness |
| TPA-ACT-08B-AR-05 | P2 | Bureaucracy containment | TPA governance | Define certification evidence fan-out budget by mode (`full`, `lightweight`, `cleanup_only`). | Certification rejects over-budget mandatory evidence growth without policy update artifact. | Throughput risk |

## Blocker Classification
- **Immediate block for trust expansion:** TPA-ACT-08B-AR-01, TPA-ACT-08B-AR-02.
- **Non-blocking but meaningful:** TPA-ACT-08B-AR-03, TPA-ACT-08B-AR-04.
- **Monitor-driven optimization:** TPA-ACT-08B-AR-05.
