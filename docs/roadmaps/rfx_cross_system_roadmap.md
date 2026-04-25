# RFX Cross-System Roadmap (RFX-01)

**Primary Prompt Type:** BUILD  
**Status:** Drafted for governed sequencing  
**Scope:** RFX as a cross-system phase label (`Review → Fix → eXecute`) using existing authorities only.  
**Authority posture:** This document is a non-authoritative execution-planning artifact. Implementation sequencing authority remains `docs/roadmaps/system_roadmap.md`.

## Intent

RFX is implemented as a routed phase label across existing systems, not as a new active authority:

`RIL → FRE → PQX → EVL → TPA → CDE → SEL → GOV`

Overlay authorities required throughout the same loop:

`REP + LIN + OBS + SLO`

Orchestration remains owned by **TLC**; admission remains owned by **AEX**.

## Existing Coverage Snapshot (What Already Exists)

- **Review interpretation:** RIL deterministic interpretation and failure-packet normalization exists.
- **Failure diagnosis + repair planning:** FRE bounded non-authoritative repair planning exists.
- **Fix execution:** PQX bounded execution and authority proof issuance exists.
- **Eval validation:** EVL required-eval coverage and evaluation-control mapping exists.
- **Control decisioning:** CDE closure/promotion decisioning exists.
- **Enforcement:** SEL fail-closed enforcement records and blocking controls exist.
- **Certification/promotion governance:** GOV surfaces exist and consume CDE/EVL outputs.
- **Replay integrity:** REP replay and replay-decision artifacts exist.
- **Lineage completeness:** LIN issuance/authenticity surfaces exist.
- **Observability:** OBS metrics/trace/alerts surfaces exist.
- **SLO freeze/error-budget response:** SLO control + enforcement surfaces exist.
- **Orchestration/routing path:** TLC top-level routing exists and should host RFX orchestration.

## Dependency-Valid Roadmap

| ID | Status | Existing System Owner | What It Builds | Why It Matters | Dependencies | Strategy Alignment | Primary Trust Gain | Red-Team / Fix Requirement | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RFX-01 | planned | TLC + AEX | Add explicit `phase_label: RFX` routing contract in TLC handoff artifacts with AEX admission binding. | Prevents implicit loop entry and ensures every RFX run starts from governed admission + routed orchestration. | None | Artifact-first control-loop routing discipline | Admission + orchestration integrity | RT-01 must attempt direct PQX invocation without AEX/TLC artifact; follow with RFX-02 fix and RFX-03 re-validation. | TLC emits route artifact containing `phase_label=RFX`; missing AEX/TLC route fails closed. |
| RFX-02 | planned | TLC | Implement fail-closed route guard that blocks RFX handoff when any required downstream owner is omitted (`PQX/EVL/TPA/CDE/SEL/GOV`). | Prevents partial loop execution and authority bypass by malformed orchestration plans. | RFX-01 | Fail-closed control-loop completeness | Route determinism under failure | Mandatory fix step for RT-01 findings; patch must include explicit missing-owner failure codes. | Route guard rejects incomplete owner chains and emits deterministic block artifact. |
| RFX-03 | planned | EVL + TPA | Re-validate full control loop chain under RFX label: missing eval evidence or ambiguous trust decision forces `block/freeze`. | Guarantees no promotion/closure advances with weak eval or policy posture. | RFX-02 | Promotion requires certification + trust adjudication | Eval and trust confidence | RT-02 injects missing `required_eval_coverage` and conflicting trust signals; RFX-04 must fix any bypass and re-run RT-02. | Any missing EVL or TPA evidence yields fail-closed decision and traceable reason codes. |
| RFX-04 | planned | CDE + SEL | Add explicit RFX closure-decision and enforcement bridge checks: no CDE decision => SEL hard block. | Ensures control decisions are explicit and enforceable, never implicit. | RFX-03 | Deterministic control-loop decision-to-enforcement binding | Enforcement integrity | Fix step for RT-02; add deterministic tests for CDE-absent and CDE-invalid paths, then re-validate. | SEL emits block record whenever CDE decision is absent/invalid; no unsafe continuation. |
| RFX-05 | planned | LIN + REP | Bind RFX runs to mandatory lineage+replay integrity bundle before GOV certification review. | Prevents irreproducible or provenance-broken fixes from reaching certification. | RFX-04 | Artifact-first provenance and replay guarantees | Reproducibility confidence | RT-03 attempts certification with missing lineage or replay mismatch; RFX-06 must remediate and re-run RT-03. | Missing lineage or replay integrity automatically blocks certification candidate state. |
| RFX-06 | planned | GOV | Add RFX promotion hard gate policy: certification denied without EVL+TPA+CDE+SEL+LIN+REP completeness. | Converts RFX from best-effort into certifiable gated loop with explicit deny states. | RFX-05 | Promotion requires certification | Certification decision reliability | Required fix for RT-03; add policy tests proving denial for each missing authority artifact class. | GOV only issues promotion-ready outcome when all required artifacts are present and valid. |
| RFX-07 | planned | OBS + SLO | Add RFX observability/SLO freeze profile: repeated failure bursts trigger SLO freeze and SEL enforcement. | Prevents silent reliability degradation and enforces pause-under-burn conditions. | RFX-06 | Control-loop reliability protection | Reliability burn-rate visibility | RT-04 chaos test injects burst failures + telemetry gaps; RFX-08 must fix telemetry blind spots and rerun. | Burn-rate breach or telemetry incompleteness causes deterministic freeze/block path. |
| RFX-08 | planned | OBS + SLO + SEL | Harden fail-closed telemetry requirements: missing OBS traces/metrics invalidates SLO decision and enforces block. | Ensures observability is a hard dependency, not optional reporting. | RFX-07 | Fail-closed observability dependency in control loop | Hidden-failure prevention | Mandatory fix for RT-04; include regression test for missing trace, missing metric, and malformed metric cases. | Missing/invalid OBS input prevents SLO pass and produces enforced block record. |
| RFX-09 | planned | FRE + EVL + PQX | Add “Fix Integrity Proof” checks proving repair execution did not weaken schemas/tests/evals/control constraints. | Prevents regression-introducing repairs from advancing under RFX. | RFX-08 | No hidden behavior + guarded fix loop | Repair safety assurance | RT-05 attempts schema relaxation/test deletion/eval bypass; RFX-10 must close all vectors and rerun RT-05. | Every fix produces integrity proof artifact covering schema, tests, evals, control, lineage, replay, certification invariants. |
| RFX-10 | planned | PQX + CDE + GOV | Enforce certification hard gate requiring Fix Integrity Proof before closure or promotion readiness. | Couples execution outputs to governance gates and closes post-fix authority leakage. | RFX-09 | Certification hard-gate reinforcement | Promotion integrity | Required fix for RT-05 with re-validation; denial behavior must be deterministic per missing-proof type. | Without Fix Integrity Proof, CDE readiness is blocked and GOV promotion is denied. |
| RFX-11 | planned | REP + OBS + GOV | Implement trend-to-roadmap feedback artifact: recurring failure signatures auto-create hardening candidates for system roadmap intake. | Converts repeated failures into governed future work instead of local/manual memory. | RFX-10 | Learning-loop to roadmap governance | Anti-recurrence hardening signal | RT-06 tries to suppress recurring-failure trend creation; RFX-12 must enforce immutable trend emission and rerun RT-06. | Repeated failure pattern threshold deterministically emits roadmap-feedback artifact with lineage+replay refs. |
| RFX-12 | planned | TLC + GOV | Add closure rule: RFX phase completes only after red-team/fix/re-validation triplets are satisfied for all required checkpoints. | Guarantees adversarial checks are first-class and cannot be skipped for speed. | RFX-11 | Fail-closed completion control-loop governance | Closure discipline | Final red-team campaign verifies skipped-fix and skipped-revalidation paths fail closed. | Any missing red-team follow-up step blocks RFX completion and promotion path. |

## Red-Team Campaign (Integrated)

1. **RT-01 (Routing bypass):** attempt direct PQX execution without TLC route or AEX admission.
2. **RT-02 (Control-evidence erosion):** remove EVL coverage and inject conflicting TPA posture.
3. **RT-03 (Certification-without-integrity):** remove LIN and REP artifacts and force GOV request.
4. **RT-04 (Chaos + observability loss):** inject burst failures while dropping traces/metrics.
5. **RT-05 (Fix regression attack):** attempt schema weakening, test removal, eval bypass, and control bypass during fix.
6. **RT-06 (Trend suppression):** mask repeated failures to avoid hardening roadmap output.
7. **Final campaign:** attempt to mark RFX complete with missing fix or missing re-validation stages.

Each red-team stage must be followed by:
- a bounded **fix** stage,
- a **re-validation** stage rerunning the same adversarial scenario,
- and evidence that no guarantees were weakened (schema, replay, lineage, eval, control, enforcement, certification).

## Chaos / Fail-Closed Proof Requirements

- Chaos tests must include partial artifact loss, stale artifact replay, and conflicting authority outputs.
- The system must fail closed for:
  - missing eval artifacts,
  - missing lineage or replay artifacts,
  - missing control decisions,
  - missing certification evidence,
  - missing observability telemetry needed for SLO control.
- All fail-closed outcomes must emit explicit machine-readable block reasons and trace references.

## Promotion / Certification Hard Gates

RFX completion cannot imply promotion. Promotion requires all of:

1. EVL required coverage pass,
2. TPA trust-policy decision present and non-ambiguous,
3. CDE readiness/promotion decision present,
4. SEL enforcement result consistent with CDE/TPA outcomes,
5. LIN lineage completeness + authenticity pass,
6. REP replay integrity pass,
7. OBS telemetry completeness pass,
8. SLO posture non-violating or explicit approved override path,
9. GOV certification artifact approving promotion readiness,
10. Completed red-team → fix → re-validation triplets.

Any missing element must deterministically block promotion.

## Gaps Identified (to close through roadmap)

- No explicit repo-wide `RFX` phase label contract in TLC routing artifacts.
- No single integrated gate proving all required authorities were present before GOV promotion decision.
- No standardized Fix Integrity Proof artifact spanning schema/test/eval/control/replay/lineage guarantees.
- No guaranteed trend-to-roadmap hardening emission path bound to recurring failure signatures.

## Recommended Next Build Prompt

**Prompt Type:** BUILD

> Implement `RFX-01` through `RFX-03` only. Keep RFX as a phase label in TLC orchestration and admission-bound routing. Add fail-closed tests proving direct PQX invocation without AEX/TLC artifacts is blocked, and prove EVL/TPA missing-evidence paths block downstream CDE/SEL progression. Do not create new system authority. Reuse TLC, AEX, EVL, TPA, and existing overlay authorities as defined in `docs/architecture/system_registry.md`.
