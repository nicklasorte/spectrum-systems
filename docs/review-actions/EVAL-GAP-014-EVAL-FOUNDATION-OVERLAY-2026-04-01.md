# EVAL-GAP-014 — Eval & Foundation Gap Overlay on Current Roadmap (2026-04-01)

## Prompt type
REVIEW

## Scope guard
This is an overlay on the active system + roadmap, not a replacement roadmap.

## Authority stack used (in order)
1. `docs/architecture/strategy-control.md` (Strategy Control Document).
2. Current repository implementation/contracts/scripts.
3. `docs/roadmaps/system_roadmap.md` and `docs/review-actions/G-RESUME-008-CONTROLLED-REENTRY-2026-04-01.md`.
4. Structured source design artifacts and source indexes.

## Repo-grounded findings summary
- The roadmap explicitly identifies the dominant bottleneck as insufficient enforced learning authority (failures not yet strongly forcing future policy/progression behavior).
- Controlled re-entry shows G1/G2 done, G3/G4 partial-unverified, G5 done-but-needing adaptation, and G6–G8 blocked/uninstantiated under active authority.
- Judgment learning surfaces exist, but architecture docs still mark longitudinal calibration/drift capabilities as scaffolded/deferred in places.
- Control-loop certification artifacts/scripts currently certify chaos/tests/review-validation integrity, but are not yet explicitly aligned to the roadmap’s CL hard-gate pass conditions (severity-qualified failure binding, deterministic enforcement uptake, and demonstrated policy-caused block/freeze/correct behavior).
- Source obligation inventory remains shallow: many obligations are ingestion/governance placeholders due missing raw source depth.

## Eval & Foundation Gap Steps (Overlay)

| ID | Gap Description | Where It Maps in CL/G Roadmap | What It Builds | Why It Matters | Strategy Alignment | Primary Trust Gain | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EFG-01 | **Hard-gate proof mismatch:** current `control_loop_certification_pack` scope validates chaos/tests/review artifacts but does not encode all roadmap CL certification gate pass conditions as first-class required fields/checks. | CL gate + CL-01..CL-05; immediate dependency for NX-01..NX-03 and G3/G4 trust-depth resume | Extends certification contract + runner to require: (a) severity-qualified failure→eval/policy linkage evidence, (b) deterministic transition consumption evidence, (c) at least one policy-caused block/freeze/correct event, (d) recurrence-prevention linkage evidence. | Prevents false-positive “certified” status that is test-heavy but loop-closure-light. | Fail-closed + certification-gated + hardening-before-expansion. | certification rigor | High |
| EFG-02 | **Failure-binding closure is still not non-bypassable across progression surfaces:** roadmap and strategy both call out insufficiency in enforced learning authority. | CL-01, CL-03; G3/G4 and NX trust spine | Unified failure-class artifact linkage requirement consumed by transition policy and PQX next-step policy (no progression when missing linkage). | Converts postmortem output from advisory to decision-authoritative. | Learn→Decide closure and recurrence prevention. | policy authority | High |
| EFG-03 | **Longitudinal calibration is partially scaffolded/deferred in architecture guidance, risking shallow learning depth across time.** | CL-05; G5 adaptation and post-G2 lifecycle work | Mandatory rolling-window calibration pack + freeze/revoke trigger evidence emitted per cycle and bound to lifecycle rollout decisions. | Without longitudinal depth, stale/overconfident policy can remain active while passing short-horizon checks. | Observe→Learn→Decide closure. | judgment quality | High |
| EFG-04 | **G3/G4 closure evidence gap:** controlled re-entry marks G3/G4 as partial/unverified due missing execution-summary closure artifact. | Immediate next G slice execution (G3/G4 B19–B26) | Required execution-summary + certification/audit closure evidence under active strategy/gate stack before claiming readiness. | Sequence trust cannot be claimed from plan presence alone. | Artifact-first + replayable + certification-gated. | observability completeness | High |
| EFG-05 | **Pre-execution gate signals are strengthened (G13/G14), but preflight→PQX admission mapping remains an explicit in-flight hardening seam.** | Immediate precondition for resumed multi-slice execution (PRECHECK-STATE-007 then G3/G4) | Deterministic mapping artifact showing how contract/execution impact outcomes drive PQX admission (`allow/warn/freeze/block`) with no downgrade path. | Closes admission drift between gate decision and runtime action. | control authority externalized + fail-closed. | promotion safety | High |
| EFG-06 | **Learning-loop depth in source-obligation layer remains shallow due placeholder ingestion obligations.** | CL + NX-19..NX-21 source authority hardening; post-G2 unless blocking a specific runtime gate | Source-obligation depth upgrade pack: source-specific runtime obligations linked to concrete eval/policy checks instead of ingestion-only placeholders. | Reduces strategy-vs-runtime drift and increases auditability of “why this policy exists.” | Source-authority bridge + drift correction. | drift resistance | Medium |
| EFG-07 | **G5 breadth capabilities are marked done but require adaptation to strict upstream strategy/pre-exec gating and CL gate supremacy.** | G5 adaptation; dependent on CL and G3/G4 closure | Explicit binding tests showing scheduler/canary/judgment paths are subordinate to strategy compliance + G13/G14 + CL closure gate status. | Prevents breadth features from becoming bypass channels around hardening gates. | hardening-before-expansion. | promotion safety | Medium |
| EFG-08 | **Legacy G6–G8 labels are blocked/uninstantiated, but not yet systematically translated into active CL/NX + gate semantics for execution surfaces.** | G6–G8 controlled re-entry mapping; largely post-G2 planning hygiene | Deterministic label-mapping table + execution guardrails that reject legacy-label execution without CL/NX equivalence and gate prerequisites. | Removes legacy naming ambiguity that can create accidental expansion pressure. | authority clarity + fail-closed progression. | policy authority | Medium |

## Critical Eval Gaps Blocking Gate

The following gaps are **hard blockers** for Control Loop Closure Certification Gate confidence:

1. **EFG-01 (hard-gate proof mismatch)** — certification artifact and checks are not yet aligned to full roadmap pass-condition semantics.
2. **EFG-02 (non-bypassable failure-binding closure)** — failures must deterministically alter future control decisions, not only generate artifacts.
3. **EFG-03 (longitudinal calibration enforcement depth)** — longitudinal learning must feed freeze/revoke and lifecycle controls with bounded-window evidence.

If these remain incomplete, certification may pass procedural checks while still missing true loop closure behavior required by strategy and roadmap gate definitions.

## Gap impact by execution horizon

### Blocks HARD GATE certification
- EFG-01, EFG-02, EFG-03.

### Affects immediate next G slice execution
- EFG-04 (G3/G4 closure evidence), EFG-05 (preflight→PQX admission hard binding), EFG-07 (G5 adaptation under stricter gates).

### Can wait until post-G2 (unless a local dependency forces earlier)
- EFG-06 (source-obligation depth expansion), EFG-08 (legacy G6–G8 semantic remap hardening).

## Recommended Next 3 Steps

1. **Gate-proof contract alignment sprint (EFG-01 + EFG-02):**
   - Extend `control_loop_certification_pack` contract + `run_control_loop_certification.py` checks to require explicit CL pass-condition fields and evidence refs.
   - Add fail-closed validation that rejects certification if policy-caused block/freeze/correct evidence is absent.

2. **Resume-safe trust-depth closure (EFG-04 + EFG-05):**
   - Complete preflight→PQX admission mapping seam.
   - Produce governed G3/G4 closure evidence artifacts under current strategy/G13/G14 controls before any breadth-forward claims.

3. **Longitudinal learning hard-bind (EFG-03, then EFG-07):**
   - Promote longitudinal calibration from scaffold/deferred posture to required cycle artifact with explicit lifecycle enforcement consequences.
   - Re-validate G5 scheduler/canary/judgment behavior as downstream of those controls.

## Why this is an overlay (not a rewrite)
- Keeps CL-first and trust-spine-first ordering intact.
- Uses existing contracts, gates, and roadmap semantics; it tightens evidence and enforcement seams.
- Focuses on missing eval/control-learning depth and proof quality rather than introducing a new architecture.
