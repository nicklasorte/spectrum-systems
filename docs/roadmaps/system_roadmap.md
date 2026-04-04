# Spectrum Systems — System Roadmap

**Authority status:** ACTIVE ROADMAP AUTHORITY (March 31, 2026 revision)

## Governed Artifact Activation (BATCH-ROADMAP-ACTIVATE)

- Human-readable roadmap source (this file): `docs/roadmaps/system_roadmap.md`
- System source of truth (machine-readable): `contracts/examples/system_roadmap.json`
- Contract authority: `contracts/schemas/system_roadmap.schema.json`

### Active governed batch list (deterministic order by `batch_id`)

| batch_id | title | status | dependencies | priority |
| --- | --- | --- | --- | --- |
| BATCH-CL-01 | Control Loop Failure Binding | completed | — | 1 |
| BATCH-CL-02 | Error Budget Engine | not_started | BATCH-CL-01 | 2 |
| BATCH-CL-03 | Recurrence Prevention Enforcement | not_started | BATCH-CL-02 | 3 |

Execution automation must select from the JSON artifact and fail closed when schema, dependency, alignment, or continuation checks fail.

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

### Critical current gap (dominant bottleneck)
The roadmap foundation is strong, but **enforced learning authority / recurrence-prevention authority** is still insufficient: severity-qualified failures are not yet bound strongly enough to automatically alter future policy and progression behavior in one non-bypassable progression spine.

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

**Required artifact:** `control_loop_closure_certification_gate` (or equivalent governed evidence bundle artifact consumed by transition policy and promotion admission logic).

**Pass conditions (all required):**
1. Governed 3-slice sequential run evidence proves every severity-qualified failure generated a bound eval/policy update.
2. Transition policy evidence proves those updates were enforced deterministically in subsequent progression decisions.
3. At least one subsequent slice was blocked/frozen or corrected by the new policy without manual override.
4. Replay + recurrence-prevention evidence is linked to the same failure classes.

**Fail-closed rule:** if any condition is missing, malformed, or non-deterministic, progression remains restricted to CL closure and trust-spine work.

**Transition and promotion blocking behavior (mandatory):**
- `NX-04+` roadmap rows are not admissible for execution while the gate is failing or absent.
- Grouped execution admission, certification/promotion expansion, and lifecycle advancement claims must fail closed when the gate artifact is missing or not passed.
- Any attempted transition that bypasses certified trust-spine evidence is invalid and must be blocked until corrective evidence is produced.


## March 31, 2026 Governance Refresh Snapshot (Roadmap Generation Run)
### Source authority inputs consumed
- `docs/source_structured/*.json` (all governed structured source artifacts).
- `docs/source_indexes/source_inventory.json`, `docs/source_indexes/obligation_index.json`, `docs/source_indexes/component_source_map.json` (machine planning surface).
- `docs/roadmaps/execution_state_inventory.md` and `docs/architecture/strategy-control.md` for strategy-control alignment.

### Gap scan summary (obligation coverage)
- **Covered obligations:** inventory/index discipline exists and remains machine-usable for all registered source IDs.
- **Partial obligations:** source obligations are still predominantly ingest/place-holder obligations due missing raw source files, limiting depth for runtime-ready obligation derivation.
- **Missing obligations:** no source-specific deep obligations yet for certification-grade runtime behavior beyond ingestion/governance stubs.
- **Drift indicators:** source authority and runtime readiness still require explicit bridge hardening to prevent strategic-vs-machine execution drift.

### Next bottleneck confirmation
The immediate bottleneck remains **trust-depth closure** (Control Loop Closure Gate completion), not breadth expansion.

## Ordered Roadmap (Post-Revision)

| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- |
| RM-01 | Roadmap authority consolidation | done | Enforces active-authority + compatibility-mirror bridge metadata and traceable authority resolution path. | Removes contradictory roadmap execution signals and preserves deterministic execution trace of authority source selection. | Roadmap Generation Rules 1–3 + drift correction (fail-closed progression, mirror reconciliation, changed-scope verification). | policy authority |
| RM-02 | Execution-state inventory | done | Maintains repo-grounded maturity inventory with artifact-linked evidence and trace IDs for readiness claims. | Prevents false readiness claims by requiring auditable state evidence before advancement. | artifact/schema-first invariants + roadmap rule on trust gain declaration + observability/durability invariants. | observability completeness |
| CL-01 | Failure Binding | planned | Makes failure→eval→policy linkage mandatory with replay-linked failure artifacts and traceable policy references. | Converts incidents into binding governance inputs and makes recurrence classes reconstructable in replay and trace views. | eval-mandatory + control authority externalized + replayable + fail-closed invariants; Control Loop Closure Gate CL-01. | eval coverage |
| CL-02 | Error Budget Engine | planned | Converts burn-rate/budget signals into warn/freeze/block decisions with deterministic control-decision traces. | Ensures quality budgets materially control progression instead of remaining advisory telemetry. | Control Loop Definition (Interpret→Enforce) + fail-closed + certification-gated invariants. | promotion safety |
| CL-03 | Recurrence Prevention Enforcement | planned | Requires serious failure classes to add regression/prevention assets tied to replay fixtures and trace-linked remediation closure. | Makes recurrence measurably harder and preserves artifact lineage showing prevention actually changed future decisions. | recurrence-prevention gate + replay/audit lineage obligations + drift correction rules. | drift resistance |
| CL-04 | Judgment Authority Activation | planned | Makes judgment/policy artifacts decision-active and trace-coupled to enforcement actions. | Prevents informational-only judgment surfaces and closes policy-bypass seams. | control authority externalized + fail-closed + certification gate CL-04 requirements. | policy authority |
| CL-05 | Longitudinal Calibration Loop | planned | Feeds delayed-truth outcomes into calibration and freeze/revoke decisions with replay-safe evidence and trace completeness. | Closes long-horizon learning loop and blocks stale policy operation through governed control actions. | Observe→Learn→Decide loop closure + replayable + certification-gated invariants. | judgment quality |
| NX-01..NX-03 | Dominant sequential trust spine (exclusive post-CL path) | gated | Builds contract hardening, transition-policy binding, and chaos/replay pack with deterministic trace reconstruction for each decision path. | Proves confidence-grade 3-slice path before any expansion and demonstrates non-bypassable replay/trace auditability. | Control Loop Closure Certification Gate pass conditions 1–4 + roadmap rule 4 (pre-expansion dependency). | replay determinism |
| NX-04..NX-06 | Canonical grouped PQX bundle path | gated | Adds grouped-bundle contracts and orchestrator wiring that preserve trace-linked blocked-path certification behavior. | Enables bounded grouped execution only after trust-spine proof and keeps bypass attempts fail-closed. | fail-closed + certification-gated invariants; roadmap rule 4; drift correction fail-closed progression. | certification rigor |
| NX-07..NX-12 | Review/fix/recurrence hardening | gated | Hardens review trigger/routing/fix closure with replay-linked prevention assets and traceable remediation state transitions. | Converges review-to-prevention loop so discovered defects deterministically change future behavior. | eval-mandatory + recurrence-prevention + control-loop closure discipline + drift correction rules. | drift resistance |
| NX-13..NX-15 | Certification + audit + promotion closure | gated | Extends sequence/group certification and audit bundles with trace-complete promotion gate evidence. | Moves trust claims from narrative to governed proof artifacts required for promotion admission. | certification-gated + replay/audit lineage stable-layer obligations. | certification rigor |
| NX-16..NX-18 | Judgment learning operationalization | gated | Operationalizes outcome labels and calibration budgets into lifecycle decisions with explicit replay references and trace IDs. | Makes learning signals enforce policy lifecycle outcomes rather than remain passive analytics. | Observe/Interpret/Decide/Enforce/Learn control-loop completeness + policy authority invariants. | judgment quality |
| NX-19..NX-21 | Source authority hardening | gated | Integrates source package ingestion and runtime strategy checks with traceable obligation-coverage decisions. | Prevents strategy/source drift and preserves reconstructable rationale for authority and obligation enforcement decisions. | roadmap generation rules + drift detection/correction + source authority bridge obligations. | drift resistance |
| NX-22..NX-24 | AI execution expansion under governance (explicitly last) | blocked until prerequisites pass | Enables retrieval replacement and adapter convergence only with eval-backed canary, replay evidence, and trace-complete promotion controls. | Keeps AI expansion subordinate to proven longitudinal calibration and recurrence-prevention efficacy. | foundation-before-expansion rules + CL certification gate + fail-closed/certification invariants. | promotion safety |

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

## April 1, 2026 Roadmap Strengthening Overlay (EVAL-FOUNDATION)

This is a controlled strengthening pass on the current roadmap using `EVAL-GAP-014-EVAL-FOUNDATION-OVERLAY-2026-04-01.md` and `G-RESUME-008-CONTROLLED-REENTRY-2026-04-01.md`.
It preserves the CL → G1 → HARD GATE → G2–G8 execution shape and tightens hardening-before-expansion sequencing.

### Strengthened CL → G1 → HARD GATE → G2–G8 table

| ID | Prompt | Status | What It Does | Why It Matters | Strategy Alignment | Primary Trust Gain |
| --- | --- | --- | --- | --- | --- | --- |
| CL | Control Loop Closure implementation (CL-01..CL-05) with EFG overlays | in_progress (must complete first) | Executes CL-01..CL-05 with explicit EFG hard blockers: EFG-01 certification pass-condition encoding, EFG-02 non-bypassable failure-binding enforcement, EFG-03 longitudinal calibration enforcement. | Prevents procedural pass artifacts from being treated as closed-loop proof when control-learning authority is still incomplete. | `strategy-control.md` non-negotiables (`eval-mandatory`, `fail-closed`, `certification-gated`) and Control Loop Closure Gate requirements. | policy authority |
| G1 | Dominant single-slice canonical path (B11–B14) | done (retained) | Keeps one canonical fail-closed execution spine (`run_pqx_slice`) and governed artifact emission discipline. | Preserves deterministic base path while CL hardening is completed. | Strategy thesis step 1 (stabilize one dominant trusted path). | replay determinism |
| HARD GATE | Control Loop Closure Certification Gate (proof-before-scale) | blocked until EFG-01/02/03 close | Requires governed evidence for severity-qualified failure→eval/policy binding, deterministic transition-policy consumption, policy-caused block/freeze/correct behavior, and recurrence-prevention linkage. | This is the non-bypassable admission barrier between trust-depth hardening and broader execution. | Pre-expansion gate in active roadmap + fail-closed progression rule. | certification rigor |
| G2 | Two-slice continuation governance (B15–B18) | done (retained) | Enforces N→N+1 continuation contracts and replay parity checks. | Maintains continuity correctness but does not supersede CL hard gate. | Artifact-first continuation trust under fail-closed governance. | replay determinism |
| G3 | 3-slice transition/readiness governance (B19–B22) | partial/unverified (next build target) | Completes transition policy, review checkpoints, and sequence budget evidence under active gates. | First sequence-depth trust layer needed before bundle-scale claims. | Hardening-before-expansion; CL-first sequencing. | certification rigor |
| G4 | Bundle-level certification and audit synthesis (B23–B26) | partial/unverified (next build target) | Produces closure-grade bundle certification/audit artifacts under strategy + G13/G14 + CL constraints. | Turns plan-level intent into inspectable trust proof. | Certification-gated + replay/audit lineage obligations. | observability completeness |
| G5 | Queue-aware scheduling/canary/judgment/N-slice proof (B27–B30) | done_with_required_adaptation | Keeps breadth features but explicitly subordinates them to CL gate status and pre-execution admission outcomes. | Prevents scheduler/canary/judgment paths from becoming expansion bypass channels. | Hardening-before-expansion and control authority externalization. | promotion safety |
| G6 | Legacy resume-hardening bridge | blocked | Remains non-executable unless remapped to active CL/NX semantics with gate prerequisites. | Avoids legacy-label drift causing uncontrolled expansion. | Authority clarity + fail-closed execution control. | drift resistance |
| G7 | Legacy resume-hardening bridge | blocked | Same as G6: no execution admission without CL/NX-equivalent artifacts and gate proof. | Prevents policy authority ambiguity in resumed execution. | Roadmap authority discipline and drift correction. | policy authority |
| G8 | Legacy resume-hardening bridge | blocked | Same as G6/G7: blocked until explicit active-authority mapping and prerequisites are met. | Prevents speculative expansion claims without trust-depth evidence. | Certification-gated expansion discipline. | certification rigor |

### EFG-01 / EFG-02 / EFG-03 hard-gate sequencing impact (explicit)

1. **EFG-01 is now a gate-definition dependency, not a quality enhancement.**
   - The HARD GATE cannot pass unless certification artifacts/runners encode all CL pass-condition semantics as required fields/checks.
2. **EFG-02 is now a progression-admission dependency.**
   - Transition/policy surfaces must fail closed when failure-class linkage to eval/policy updates is missing.
3. **EFG-03 is now a lifecycle-enforcement dependency.**
   - Longitudinal calibration evidence must influence freeze/revoke/lifecycle decisions before broader scaling is admissible.

### Immediate pre-scaling slices (must happen before broader G2/G3/G4 scaling claims)

The following slices are now ordered as immediate next build work before any broader scaling claims:
1. **EFG-01 + EFG-02 alignment sprint:** update control-loop certification contract/runner and progression policy checks to be fail-closed on missing binding evidence.
2. **EFG-05 + EFG-04 resume-safe closure:** complete preflight→PQX admission mapping and then produce closure-grade G3/G4 execution evidence.
3. **EFG-03 + EFG-07 enforcement/adaptation:** make longitudinal calibration lifecycle-active, then re-validate G5 breadth behaviors as subordinate to these controls.

### Current Gate Risks

- **Certification false-positive risk:** gate artifact can appear complete without full CL pass-condition semantics (EFG-01).
- **Advisory-only learning risk:** failures can still be recorded without deterministically constraining next-step progression (EFG-02).
- **Short-horizon trust risk:** deferred/scaffolded longitudinal calibration permits stale policy operation under apparent local health (EFG-03).
- **Resume evidence gap risk:** G3/G4 readiness remains partial until closure-grade execution summary artifacts are emitted (EFG-04).
- **Admission drift risk:** incomplete preflight→PQX mapping allows gate-result-to-runtime-action mismatch (EFG-05).

### Recommended Next Hard Gate

**Control Loop Closure Certification Gate pass under strengthened criteria (EFG-01/02/03 complete), then and only then admit broader post-G1/G2 scaling.**

### Recommended Next 3 Build Steps

1. **Build Step 1 — Gate-proof hardening:** implement EFG-01 + EFG-02 fail-closed certification/progression bindings.
2. **Build Step 2 — Resume-safe trust-depth closure:** implement EFG-05 and emit EFG-04 closure evidence for G3/G4.
3. **Build Step 3 — Longitudinal enforcement activation:** implement EFG-03 and re-qualify G5 via EFG-07 adaptation checks.

## Blind Spots

### 1) Decision-signal quality gaps
- **CL and hard-gate evidence still lean heavily toward structure/completeness checks** (artifact presence, linkage shape, process traceability) more than demonstrated decision-quality uplift across hard cases.
- **G3/G4 partial state increases signal risk:** sequence-readiness can be over-inferred from governance scaffolding before decision-quality eval depth is proven under multi-slice stress.
- **G5 “done with adaptation required” indicates breadth controls exist, but correctness-sensitive eval coverage may lag behind compliance coverage.**

### 2) Policy-update enforcement gaps
- **Known gap remains EFG-02:** learning can still terminate in artifacts unless transition/policy surfaces reject progression when failure-binding is missing.
- **Policy-consumption determinism is not yet universally evidenced across all progression surfaces** (preflight, PQX admission, transition policy, lifecycle gate decisions).

### 3) Masking-risk seams
- **Upstream contract/schema invalidation can mask downstream behavioral failures** by preventing execution paths from reaching the failure mode that CL controls are meant to catch.
- **If preflight blocks early without failure-mode simulation parity, downstream policy-caused block/freeze/correct logic may remain under-exercised** despite apparently healthy validation runs.

### 4) Override / bypass surfaces
- **Manual interpretation seams** remain possible wherever gate outcomes are not yet consumed as strict machine-enforced admission inputs.
- **Advisory artifacts risk bypass** when produced but not hard-required by transition policy (core EFG-02 concern).
- **Legacy G6–G8 labels create implicit bypass pressure** if used as shorthand for progression without CL/NX-equivalent gate prerequisites.

### 5) Compliance vs correctness imbalance
- **RM/Roadmap/governance discipline is strong on compliance** (authority, artifact lineage, fail-closed framing).
- **Correctness depth is comparatively weaker where longitudinal and policy-effect evidence is still scaffolded/partial** (EFG-03, G3/G4 closure gap).

### 6) State / decision inconsistency risks
- **Preflight, PQX, strategy gating, and control semantics can diverge** if one surface treats decisions as advisory while another treats them as blocking.
- **Duplicate authority expressions** (roadmap row status, gate artifacts, execution summaries) can disagree without a single deterministic conflict-resolution rule encoded at runtime.

### 7) Longitudinal evidence sufficiency
- **Current state appears insufficient for strong longitudinal calibration/drift-response claims** until rolling-window calibration evidence is required per cycle and bound to freeze/revoke outcomes (EFG-03).
- **Short-horizon pass evidence should be treated as necessary but not sufficient** for lifecycle-confidence assertions.

### 8) Hard-gate falsification criteria (summary pointer)
- The HARD GATE must fail if any strengthened pass-condition evidence is missing, ambiguous, non-deterministic, or not consumed by progression policy as a blocking control.

## Hard-Gate Falsification Criteria

Even if many tests pass, the HARD GATE is **falsified** (must fail closed) when any of the following conditions hold:

1. **Missing severity-qualified binding evidence**
   - No complete evidence chain from failure classification to required eval additions and policy update references.
2. **Non-deterministic policy consumption**
   - Transition decisions do not show deterministic, replayable consumption of updated policy/eval artifacts.
3. **No demonstrated policy-caused behavioral effect**
   - There is no concrete blocked/frozen/corrected subsequent path attributable to the updated policy.
4. **Recurrence-prevention linkage absent**
   - Remediation closure lacks linked regression/prevention assets for the same failure class.
5. **Preflight/PQX semantic mismatch**
   - Gate outcomes (`allow/warn/freeze/block`) are not consistently mapped into runtime admission behavior.
6. **Bypass path detected**
   - Any manual override/advisory path allows progression that should have been blocked under strengthened criteria.
7. **Longitudinal evidence insufficiency**
   - Calibration artifacts are missing, out-of-window, or not connected to freeze/revoke/lifecycle decisions.
8. **Authority inconsistency unresolved**
   - Strategy control, roadmap status, and gate artifacts disagree with no deterministic precedence behavior in execution controls.

## Compliance vs Correctness Balance

### Where compliance/governance is currently stronger
- Authority ordering, roadmap control framing, and fail-closed posture are explicit and consistently documented.
- Artifact-centric traceability and certification language are mature enough to prevent many procedural drift modes.

### Where correctness/learning depth is currently weaker
- Decision-quality eval depth is not yet uniformly demonstrated across multi-slice and longitudinal conditions.
- Policy-update effects are not yet proven non-bypassable across every progression surface.
- Longitudinal calibration and drift response are still emerging as enforceable runtime controls rather than universally binding outcomes.

### Strengthening principle for next execution window
- For each near-term build step, pair **one compliance artifact** with **one correctness-effect artifact**:
  - compliance: contract/check/status evidence,
  - correctness: demonstrated decision/outcome change caused by that evidence.
- Do not count a step as complete unless both artifact types are present and replay-linked.

## April 1, 2026 Post-Gate Reevaluation — ROADMAP-REEVALUATION-018 (Foundation + Proof Aware)

### 1) Current Strategy Risks (Top 5)
1. **Distributed enforcement risk:** core control/eval/enforcement capabilities exist, but multiple legacy/parallel decision paths can still dilute non-bypassable behavior.
2. **Certification false-pass risk:** hard-gate evidence can be assembled from structural completeness without proving behavior-changing policy enforcement in subsequent slices.
3. **Learning-to-prevention gap risk:** failure capture and judgment learning exist, but deterministic recurrence-prevention enforcement is not yet universally required on continuation/admission surfaces.
4. **Promotion authority fragmentation risk:** promotion, rollout, and lineage checks are present across several modules without one canonical runtime authority seam.
5. **Replay/trace reconstruction drift risk:** replay and trace modules are strong, but multi-surface integration leaves residual risk of inconsistent cross-surface decision reconstruction.

### 2) Foundation Gap Classification (Repo vs Foundation Chain)

| Foundation Layer | Classification | Repo-grounded rationale |
| --- | --- | --- |
| canonical artifact schemas | present_and_governed | Broad schema inventory and runtime validation seams are implemented and actively consumed. |
| PQX execution coordination | present_but_partial | Canonical slice and sequence runners exist, but pathway dominance remains split across queue/runtime surfaces. |
| eval case / eval result / eval summary surfaces | present_but_partial | `eval_summary`, failure/eval artifacts, and output-evaluation modules exist; end-to-end mandatory consumption is not singular. |
| deterministic control decision logic | present_but_partial | Control-loop logic is deterministic and schema-validated, but platform-wide single authority is still distributed. |
| enforcement action recording | present_but_bypassable | Canonical enforcement path exists alongside constrained legacy compatibility mapper, leaving managed-but-real bypass surface. |
| replay integrity | present_but_partial | Replay engines/governance and tests are present, but long-sequence confidence-grade closure remains partial. |
| trace completeness | present_but_partial | Trace stores/engines and lineage seams are present; full cross-surface closure remains integration-sensitive. |
| golden path artifact_release_readiness | present_but_partial | Golden-path seams exist, but hard-gate proof criteria for expansion are not yet fully evidenced. |

**Hard blockers for expansion right now:** `present_but_bypassable` and all `present_but_partial` rows above (per foundation hard-gate policy).

### 3) Hard Gate Readiness Assessment

**Control Loop Closure Gate (enhanced): NOT READY**

| Enhanced Gate Check | Assessment | Notes |
| --- | --- | --- |
| 1. failure → eval → policy linkage exists | partial | Implemented seams exist, but mandatory enforcement across every progression surface is incomplete. |
| 2. deterministic policy consumption | partial | Deterministic logic exists in modules, but end-to-end singular consumption authority is not fully closed. |
| 3. policy causes behavior change (block/freeze/correct) | partial | Behavior-changing controls are implemented, but proof of universal non-bypassable operation is incomplete. |
| 4. recurrence-prevention exists | partial | Recurrence-prevention assets exist; mandatory closure enforcement remains uneven. |
| 5. longitudinal calibration exists | partial | Calibration/lifecycle components exist, but hard lifecycle influence is still being tightened. |
| 6. calibration affects lifecycle decisions | partial | Designed and partially wired; insufficient confidence-grade evidence over bounded windows. |
| 7. replay + trace fully reconstruct decisions | partial | Strong foundation present; sequence-wide deterministic reconstruction remains not yet confidence-grade. |
| 8. falsification artifact works and fails correctly | partial | Criteria are defined; strengthened fail-closed falsification behavior still requires full runtime proof. |

**Readiness determination:** Expansion is blocked; further foundation/control hardening is required before broader grouped or AI execution expansion.

### 4) Next 24 Steps (Dependency-Valid, PQX-Executable)

| ID | Prompt (Codex-ready) | Status | What It Does | Why It Matters | Strategy Alignment | Primary Trust Gain | Foundation Relation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RE18-01 | BUILD: Make `evaluation_control_decision` the sole admissible decision input for all enforcement entrypoints and remove runtime callers of legacy budget decision paths. | planned | Eliminates dual decision semantics at enforcement boundary. | Converts enforcement from mixed-mode to canonical fail-closed control authority. | control authority externalized; fail-closed. | policy enforcement | hardens the foundation |
| RE18-02 | VALIDATE: Add exhaustive regression tests proving legacy enforcement path cannot be used by non-allowlisted callers and fails closed under malformed payloads. | planned | Verifies bypass closure is real under adversarial invocation patterns. | Prevents silent reintroduction of bypass behavior. | fail-closed; certification-gated. | safety | hardens the foundation |
| RE18-03 | WIRE: Require PQX slice/sequence runners to consume a single normalized eval summary artifact contract before control decisions are emitted. | planned | Standardizes eval ingestion shape for control loop. | Removes shape drift between eval surfaces and control logic. | artifact-first; eval-mandatory. | measurability | builds the foundation |
| RE18-04 | BUILD: Add deterministic failure-class-to-policy binding registry artifact and enforce lookup on every severity-qualified failure. | planned | Creates explicit, replayable mapping from failures to policy obligations. | Makes CL-01 binding non-optional and inspectable. | CL-01 failure binding. | trustworthiness | hardens the foundation |
| RE18-05 | WIRE: Integrate failure-binding registry checks into preflight, transition, and promotion admission surfaces with fail-closed behavior on missing linkage. | planned | Extends CL-01 enforcement across all progression checkpoints. | Prevents advisory-only learning and admission drift. | hard gate rule; fail-closed progression. | policy enforcement | hardens the foundation |
| RE18-06 | BUILD: Encode hard-gate pass-condition schema fields for all CL checks (1–8) in the certification gate artifact contract and validators. | planned | Makes certification criteria machine-checkable and complete. | Reduces false-positive gate pass risk. | certification-gated; no false completion. | certification rigor | builds the foundation |
| RE18-07 | VALIDATE: Add falsification tests that intentionally omit each CL pass condition and assert hard-gate failure for every omission. | planned | Proves certification gate fails correctly for missing evidence. | Ensures proof-before-scale blocker is enforceable. | fail-closed; CL certification gate. | safety | hardens the foundation |
| RE18-08 | BUILD: Consolidate control decision precedence rules into one runtime authority module consumed by preflight, PQX, queue, and promotion decisions. | planned | Unifies decision precedence and conflict resolution. | Eliminates cross-surface inconsistency risks. | deterministic control authority. | replayability | hardens the foundation |
| RE18-09 | VALIDATE: Add cross-surface consistency suite asserting same inputs yield same decision across preflight, PQX, control, and promotion layers. | planned | Tests deterministic agreement across control surfaces. | Detects policy-consumption drift before release. | fail-closed; replayable. | measurability | hardens the foundation |
| RE18-10 | BUILD: Implement mandatory recurrence-prevention closure artifact linking failure class, remediation asset, regression fixture, and policy update IDs. | planned | Converts recurrence prevention into a governed first-class artifact. | Closes CL-03 with explicit prevention lineage. | recurrence prevention enforcement. | drift resistance | builds the foundation |
| RE18-11 | WIRE: Block continuation/promotion when recurrence-prevention closure artifact is missing for qualifying failures. | planned | Enforces prevention closure at admission boundaries. | Prevents repeated failure classes from progressing. | CL-03; fail-closed. | safety | hardens the foundation |
| RE18-12 | BUILD: Activate longitudinal calibration runner that consumes delayed truth labels and produces calibration action artifacts with deterministic thresholds. | planned | Operationalizes CL-05 calibration into governed artifacts. | Enables long-horizon drift governance. | observe→learn→decide loop closure. | judgment quality | builds the foundation |
| RE18-13 | WIRE: Bind calibration artifacts to lifecycle actions (freeze/revoke/reinstate) in judgment policy lifecycle module with mandatory control references. | planned | Makes calibration materially affect lifecycle state. | Prevents stale policies from remaining active. | CL-05; fail-closed lifecycle control. | policy enforcement | hardens the foundation |
| RE18-14 | VALIDATE: Add bounded-window longitudinal simulations proving calibration thresholds trigger expected freeze/revoke outcomes. | planned | Produces proof that calibration influences decisions. | Converts lifecycle claims from design intent to evidence. | no false completion; certification-gated. | trustworthiness | hardens the foundation |
| RE18-15 | BUILD: Create canonical `control_loop_closure_evidence_bundle` assembler that captures eval, control, enforcement, replay, and prevention links for each slice. | planned | Establishes one artifact spine for CL proof. | Supports deterministic audit and gate evaluation. | artifact-first; replayable. | replayability | builds the foundation |
| RE18-16 | VALIDATE: Run governed 3-slice dominant-path fixture and emit evidence bundles proving policy-caused block/freeze/correct behavior without manual override. | planned | Produces direct hard-gate proof artifact set. | Required before any NX-04+ scale claims. | strategy thesis; proof-before-scale. | certification rigor | depends on the foundation |
| RE18-17 | BUILD: Harden replay engine to assert full decision reconstruction (failure→eval→control→enforcement→promotion) from bundle evidence only. | planned | Makes replay integrity executable and testable end-to-end. | Closes decision lineage reconstruction gaps. | replay integrity; trace completeness. | replayability | hardens the foundation |
| RE18-18 | VALIDATE: Add replay parity tests comparing live-run decisions to replayed decisions across 3-slice runs with strict equality checks. | planned | Verifies deterministic reproducibility of decisions. | Prevents non-deterministic progression behavior. | replayable; certification-gated. | measurability | hardens the foundation |
| RE18-19 | BUILD: Introduce trace completeness auditor that fails when required lineage IDs are missing across eval/control/enforcement/certification artifacts. | planned | Enforces cross-artifact trace contracts. | Prevents partial lineage from passing governance gates. | trace completeness; fail-closed. | observability completeness | hardens the foundation |
| RE18-20 | VALIDATE: Wire golden-path `artifact_release_readiness` gate to require successful trace completeness + replay parity + CL evidence bundle checks. | planned | Upgrades golden path from nominal success to trust-grade readiness. | Converts release readiness into hard proof-based admission. | golden-path first validation; certification-gated. | promotion safety | hardens the foundation |
| RE18-21 | REVIEW: Produce checkpoint Claude review pack focused on CL closure, falsification results, and remaining bypass surfaces. | planned | Prepares independent architectural scrutiny at hardening checkpoint. | Required governance quality control before advancement. | checkpoint and review expectations. | trustworthiness | depends on the foundation |
| RE18-22 | BUILD: Close promotion authority fragmentation by routing all promotion admissions through one canonical promotion gate facade with strict policy/eval/lineage prerequisites. | planned | Unifies promotion decision semantics. | Prevents inconsistent promotion behavior across modules. | certification-gated; control authority. | policy enforcement | depends on the foundation |
| RE18-23 | VALIDATE: Execute changed-scope and gate-readiness verification scripts; persist signed run outputs as promotion-blocker evidence. | planned | Enforces execution discipline and evidence capture. | Detects drift/unplanned scope before certification claims. | drift correction; fail-closed progression. | safety | depends on the foundation |
| RE18-24 | WIRE: Only after RE18-01..RE18-23 pass, enable NX-04 admission flag for limited grouped PQX canary with automatic rollback on gate regressions. | blocked by foundation gaps | Defines strictly bounded expansion trigger and rollback control. | Allows minimal expansion only after proven closure. | harden-before-expand; foundation-before-breadth. | promotion safety | blocked by foundation gaps |

### 5) Recommended Next Move
**Foundation Alignment Bundle**

Reason: the current repo shows strong components but still partial/bypassable foundation layers; advancing to broader execution now would violate strategy hard-gate and no-false-completion rules.

### 6) Recommended Next Hard Gate
**Control Loop Closure Certification Gate (strengthened criteria) with mandatory pass on RE18-06, RE18-07, RE18-16, RE18-18, and RE18-20 evidence.**

### 7) Hard-Gate Falsification Risks
1. Gate artifact passes while one or more CL conditions are represented as optional or informational fields.
2. Policy linkage exists in artifacts but is not consumed as a blocking input by progression decisions.
3. Enforcement actions are emitted but do not alter continuation/promotion behavior.
4. Recurrence-prevention artifacts exist without mandatory admission coupling.
5. Replay reproduces artifact presence but not identical control outcomes.
6. Trace IDs are locally valid but do not chain end-to-end across artifact classes.
7. Calibration evidence is generated but lifecycle state transitions are not policy-bound.
8. Golden-path readiness passes despite missing falsification coverage for malformed or absent evidence.
