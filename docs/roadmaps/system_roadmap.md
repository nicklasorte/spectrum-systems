# Spectrum Systems — System Roadmap

**Authority status:** ACTIVE ROADMAP AUTHORITY (March 31, 2026 revision)

## March 31, 2026 Authority Revision (Supersession / Extension)
This revision supersedes the prior B1/B2 roadmap state by preserving valid completed governance foundations and extending forward execution with a stricter pre-expansion gate.

- **Active editorial authority remains:** `docs/roadmaps/system_roadmap.md`
- Compatibility transition rule: `docs/roadmap/system_roadmap.md` is a required parseable operational mirror for legacy PQX consumers until migration completes.
- **New mandatory rule:** broader grouped expansion and later AI execution expansion are subordinate to passing the **Control Loop Closure Gate**.
- **RE-05 tightening (approved with corrections):** post-CL execution narrows to one dominant trust spine (`NX-01..NX-03`) and requires proof-before-scale certification gating before `NX-04+`.
- **Current posture:** Spectrum Systems is near a governed pipeline MVP, but **not yet** at a true MVP closed-loop control system.

## Intent
Converge existing strong governance seams into one dominant trusted sequential path and then a bounded grouped path, while hard-binding failure learning into future decisions before any wider execution expansion.

## System Goal
Operate Spectrum Systems as a governed, fail-closed, artifact-first execution surface with replayable evidence where failures materially and measurably change future control decisions.

## Architectural Invariants
- artifact-first
- schema-first
- eval-mandatory
- control authority externalized
- replayable
- fail-closed
- certification-gated

## Current Repo State Summary
### What is strong
- Broad contract/governance seams across runtime, replay, observability, judgment, and certification.
- Active roadmap authority and execution inventory already exist.
- Autonomous cycle runner, PQX handoff, and review/fix re-entry seams are present.

### What is partial
- No confidence-grade dominant 3+ slice sequential trust path.
- Grouped PQX execution exists in pieces, not one canonical bundle path.
- Review trigger/routing/rack-and-stack are fragmented.
- Long-sequence certification and audit closure remain below confidence-grade.

### Critical current gap
The roadmap foundation is strong, but authoritative learning-loop closure is still insufficient: failures are not yet bound strongly enough to automatically alter future policy and progression behavior.

## RE-05 Reconciliation Guardrails (March 31, 2026)
- The roadmap remains valid in broad direction; this update narrows execution sequencing without replacing structure.
- Post-CL execution is constrained to **one dominant trust spine**: `NX-01..NX-03` only until proof passes.
- No grouped execution expansion before trust-spine proof.
- No certification/promotion expansion before trust-spine proof.
- No AI execution expansion before longitudinal calibration and recurrence-prevention efficacy are evidenced over a bounded run window.
- Spectrum Systems remains near governed pipeline MVP and **not yet** true closed-loop control MVP.

## Control Loop Closure Gate
**Gate position:** Mandatory pre-expansion hard gate before broader grouped scale-out or AI execution expansion.

### CL-01 — Failure Binding
- **What it does:** makes `failure -> eval case -> policy linkage` mandatory.
- **Why now:** prevents learning from being advisory-only.
- **Risk reduced:** repeat failures due to non-binding postmortems.
- **Loop stage closed:** Learn -> Decide.
- **Proof artifacts:** failure classification artifacts linked to required eval additions and policy references.
- **Dependencies unlocked:** grouped review/fix scaling, promotion hardening, and later AI boundary expansion.

### CL-02 — Error Budget Engine
- **What it does:** converts burn-rate/budget status into governed warn/freeze/block transitions.
- **Why now:** status-only budgets do not change behavior.
- **Risk reduced:** silent quality drift during continued execution.
- **Loop stage closed:** Interpret -> Enforce.
- **Proof artifacts:** deterministic error budget status + control escalation + enforcement action records.
- **Dependencies unlocked:** long-sequence promotion trust and operational drift containment.

### CL-03 — Recurrence Prevention Enforcement
- **What it does:** requires discovered failure classes to tighten future behavior through regression fixtures, policy updates, or equivalent governed prevention assets.
- **Why now:** incident closure without recurrence hardening is not loop closure.
- **Risk reduced:** same defect class reappears at higher scale.
- **Loop stage closed:** Validation -> Prevention.
- **Proof artifacts:** remediation closure linked to generated/required replay+eval prevention assets.
- **Dependencies unlocked:** grouped PQX confidence, certification durability.

### CL-04 — Judgment Authority Activation
- **What it does:** ensures judgment and policy artifacts directly influence progression and enforcement outcomes.
- **Why now:** artifacts existing as side-records does not provide control.
- **Risk reduced:** policy bypass or informational-only judgment.
- **Loop stage closed:** Decide -> Enforce.
- **Proof artifacts:** judgment application records and policy lifecycle controls consumed in transition decisions.
- **Dependencies unlocked:** safe judgment-driven scaling and policy lifecycle governance.

### CL-05 — Longitudinal Calibration Loop
- **What it does:** feeds delayed truth/audit outcomes into calibration, confidence governance, and freeze/revoke decisions over time.
- **Why now:** immediate-only evals miss long-horizon failure patterns.
- **Risk reduced:** stale or degraded policies staying active.
- **Loop stage closed:** Observe -> Learn -> Decide.
- **Proof artifacts:** outcome labels, calibration artifacts, drift/budget-triggered freeze or revoke records.
- **Dependencies unlocked:** confidence-grade N-slice trust claims and canary/promotion safety at scale.

## Control Loop Closure Certification Gate (Proof-Before-Scale Blocker)
**Gate position:** Required transition-policy blocker between `NX-01..NX-03` and any `NX-04+` execution.

**Required artifact:** `control_loop_closure_certification_gate` (or equivalent governed evidence bundle artifact consumed by transition policy).

**Pass conditions (all required):**
1. Governed 3-slice sequential run evidence proves every severity-qualified failure generated a bound eval/policy update.
2. Transition policy evidence proves those updates were enforced deterministically in subsequent progression decisions.
3. At least one subsequent slice was blocked/frozen or corrected by the new policy without manual override.
4. Replay + recurrence-prevention evidence is linked to the same failure classes.

**Fail-closed rule:** if any condition is missing, malformed, or non-deterministic, progression remains restricted to CL closure and trust-spine work.


## March 31, 2026 Governance Refresh Snapshot (Roadmap Generation Run)
### Source authority inputs consumed
- `docs/source_structured/*.json` (all governed structured source artifacts).
- `docs/source_indexes/source_inventory.json`, `docs/source_indexes/obligation_index.json`, `docs/source_indexes/component_source_map.json` (machine planning surface).
- `docs/roadmaps/execution_state_inventory.md` and `docs/architecture/strategy_control_document.md` for strategy-control alignment.

### Gap scan summary (obligation coverage)
- **Covered obligations:** inventory/index discipline exists and remains machine-usable for all registered source IDs.
- **Partial obligations:** source obligations are still predominantly ingest/place-holder obligations due missing raw source files, limiting depth for runtime-ready obligation derivation.
- **Missing obligations:** no source-specific deep obligations yet for certification-grade runtime behavior beyond ingestion/governance stubs.
- **Drift indicators:** source authority and runtime readiness still require explicit bridge hardening to prevent strategic-vs-machine execution drift.

### Next bottleneck confirmation
The immediate bottleneck remains **trust-depth closure** (Control Loop Closure Gate completion), not breadth expansion.

## Ordered Roadmap (Post-Revision)

| Step ID | Step Name | What It Builds | Why It Matters | Control Loop Stage | Learning Loop Stage | Dependency | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RM-01 | Roadmap authority consolidation | Active authority + mirror bridge discipline | Removes contradictory roadmap execution signals | Decide / Enforce | Prevention | done | stronger policy authority |
| RM-02 | Execution-state inventory | Repo-grounded maturity map | Prevents false readiness claims | Observe / Interpret | Detection | RM-01 | more measurable |
| CL-01 | Failure Binding | Mandatory failure→eval→policy linkage | Converts incidents into binding governance inputs | Learn / Decide | Detection / Root Cause | RM-02 | stronger recurrence prevention |
| CL-02 | Error Budget Engine | Burn-rate enforcement transitions | Ensures quality budgets control progression | Interpret / Enforce | Validation | CL-01 | safer |
| CL-03 | Recurrence Prevention Enforcement | Required regression/policy tightening on serious failures | Makes recurrence measurably harder | Learn / Enforce | Prevention | CL-02 | stronger recurrence prevention |
| CL-04 | Judgment Authority Activation | Judgment/policy artifacts become decision-active | Prevents informational-only judgment surfaces | Decide / Enforce | Classification | CL-03 | more trustworthy decisions |
| CL-05 | Longitudinal Calibration Loop | Delayed-truth calibration + freeze/revoke hooks | Closes long-horizon learning loop | Observe / Learn / Decide | Validation / Prevention | CL-04 | safer + more measurable |
| NX-01..NX-03 | Dominant sequential trust spine (exclusive post-CL path) | Contract hardening + transition policy + chaos/replay pack | Proves 3-slice confidence-grade path before any expansion | Observe/Interpret/Decide/Enforce | Validation | CL-05 | more replayable |
| NX-04..NX-06 | Canonical grouped PQX bundle path | Bundle contracts + orchestrator wiring + blocked-path certification | Enables bounded grouped execution only after trust-spine proof | Decide / Enforce | Validation / Prevention | Control Loop Closure Certification Gate pass (NX-01..NX-03 proof accepted) | safer |
| NX-07..NX-12 | Review/fix/recurrence hardening | Trigger policy + routing + rack-and-stack + fix closure + prevention assets | Converges review-to-prevention loop after proof-gated grouped entry | Interpret / Decide / Enforce / Learn | Root Cause / Fix / Prevention | NX-06 | stronger recurrence prevention |
| NX-13..NX-15 | Certification + audit + promotion closure | Grouped/sequence cert extension + audit bundle + promotion gate | Moves trust claims to system-level proof | Decide / Enforce | Validation | NX-12 | stronger certification |
| NX-16..NX-18 | Judgment learning operationalization | Outcome labeling + calibration budgets + drift freeze/revoke | Makes learning influence policy lifecycle | Observe / Interpret / Decide / Enforce / Learn | Detection / Validation / Prevention | NX-15 | more trustworthy decisions |
| NX-19..NX-21 | Source authority hardening | Source package ingestion + runtime strategy compliance + obligation coverage | Prevents source/strategy drift | Observe / Decide / Enforce / Learn | Classification / Prevention | NX-18 | stronger policy authority |
| NX-22..NX-24 | AI execution expansion under governance (explicitly last) | Retrieval replacement + adapter convergence + eval-backed canary | Enables later AI improvement only after longitudinal calibration + recurrence-prevention efficacy evidence | Observe / Interpret / Decide / Enforce / Learn | Fix / Validation / Prevention | NX-21 + Control Loop Closure Certification Gate pass + bounded-window calibration/prevention efficacy evidence | safer + more measurable |

## Execution Bundles (Rack-and-Stack)
1. **Control-loop closure work (hard gate first):** CL-01 → CL-02 → CL-03 → CL-04 → CL-05.
2. **Phase B (dominant trust spine only):** NX-01..NX-03 and no concurrent non-spine advancement.
3. **Hard proof review blocker:** Control Loop Closure Certification Gate pass is required before any `NX-04+`.
4. **Phase C (conditional grouped expansion):** NX-04..NX-12 only after trust-spine proof acceptance.
5. **Phase D (system proof + lifecycle + source authority):** NX-13..NX-21.
6. **Phase E (AI execution expansion last):** NX-22..NX-24 only after bounded-window longitudinal calibration + recurrence-prevention efficacy evidence.

## Prioritization Rationale
- The next bottleneck is convergence and trust closure, not breadth.
- Source-index evidence confirms obligations are machine-usable but still shallow; trust-loop hardening must precede broader autonomy.
- One dominant trusted sequential path is more valuable than parallel partial paths.
- Expansion without binding failure learning increases recurrence and certification risk.

## Next Hard Gate
**Proceed only when governed 3-slice evidence proves deterministic failure-to-policy binding, enforced transition-policy consumption, and recurrence-prevention effect without manual override. Until then, progression is restricted to CL-01..CL-05 and NX-01..NX-03.**
