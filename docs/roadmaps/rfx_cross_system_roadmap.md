# RFX Cross-System Roadmap (RFX-01)

**Primary Prompt Type:** BUILD  
**Status:** Drafted for governed sequencing  
**Scope:** RFX as a cross-system phase label (`Review → Fix → eXecute`) using existing systems only.  
**Governance note:** This document is a non-owning planning artifact. Implementation sequencing remains in `docs/roadmaps/system_roadmap.md`.

## Intent

RFX is a routed phase label across existing systems, not a new system:

`RIL → FRE → PQX → EVL → TPA → CDE → SEL → GOV`

Required overlays in the same loop:

`REP + LIN + OBS + SLO`

TLC handles routing and AEX remains the admission entry.

## Existing Coverage Snapshot

- RIL already provides review interpretation and normalized failure packets.
- FRE already provides failure diagnosis and repair planning artifacts.
- PQX already provides bounded fix execution records.
- EVL already provides required evaluation coverage and decision mapping inputs.
- TPA already provides trust/policy adjudication outputs.
- CDE already provides closure and promotion-readiness decisions.
- SEL already provides fail-closed enforcement records.
- GOV already provides certification and promotion governance surfaces.
- REP already provides replay integrity records.
- LIN already provides lineage issuance and authenticity outputs.
- OBS already provides metrics/trace/alert artifacts.
- SLO already provides budget/burn posture and freeze signaling.
- TLC already provides top-level route artifacts.

## Dependency-Valid Roadmap

This plan is a control-loop integration roadmap across existing systems and overlays.

| ID | Status | Existing System Owner | What It Builds | Why It Matters | Dependencies | Strategy Alignment | Primary Trust Gain | Red-Team / Fix Requirement | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LOOP-01 | planned | TLC + AEX | Add explicit `phase_label: RFX` in TLC route artifacts with AEX admission linkage. | Prevents implicit loop entry and keeps the path deterministic. | None | Artifact-first route discipline | Admission and route integrity | RT-01 attempts direct PQX invocation without AEX/TLC artifacts; LOOP-02 then LOOP-03 are required follow-ups. | Missing AEX/TLC route artifact stops progression with deterministic failure output. |
| LOOP-02 | planned | TLC | Add fail-closed route completeness check for `PQX/EVL/TPA/CDE/SEL/GOV` presence. | Prevents partial-loop drift and routing gaps. | LOOP-01 | Fail-closed sequencing | Complete handoff chain confidence | Mandatory fix step for RT-01 findings with explicit reason codes. | Incomplete owner chain is rejected with machine-readable diagnostics. |
| LOOP-03 | planned | EVL + TPA | Re-run loop validation with missing eval evidence and conflicting trust signals. | Prevents continuation when evidence is incomplete or policy posture is ambiguous. | LOOP-02 | Certification-first evidence posture | Eval and policy confidence | RT-02 injects missing eval coverage/conflicting trust signals; LOOP-04 is required fix and re-check. | Missing EVL or TPA evidence yields deterministic stop reasons. |
| LOOP-04 | implemented | CDE + SEL | Add explicit CDE-to-SEL decision-bridge checks for absent/invalid closure decisions. | Prevents implicit closeout movement. | LOOP-03 | Decision trace completeness | Decision-to-action consistency | Required fix step for RT-02 with deterministic test coverage. | Absent/invalid CDE decision triggers SEL stop record. |
| LOOP-05 | implemented | LIN + REP | Require lineage and replay integrity bundle before GOV certification review. | Blocks non-reproducible or provenance-broken fixes. | LOOP-04 | Provenance + replay requirements | Reproducibility confidence | RT-03 attempts certification without lineage/replay completeness; LOOP-06 must close gaps and re-check. | Missing lineage or replay evidence blocks certification candidate state. |
| LOOP-06 | implemented | GOV | Add certification hard gate requiring EVL+TPA+CDE+SEL+LIN+REP+OBS+SLO+PRA+POL completeness. | Makes the GOV evidence bundle complete by default; PRA and POL evidence are required inputs alongside EVL, TPA, CDE, and SEL contributions. | LOOP-05 | Promotion requires certification | Certification reliability | Required fix step for RT-03 with denial tests for each missing artifact class including PRA and POL. | GOV certification record is not issued until EVL, TPA, CDE, SEL, LIN, REP, OBS, SLO, PRA, and POL evidence are all present and valid. |
| LOOP-07 | planned | OBS + SLO | Add burst-failure profile where repeated failures plus burn-rate pressure trigger freeze path. | Prevents silent reliability decay. | LOOP-06 | Reliability-preserving loop behavior | Burn-rate visibility | RT-04 chaos run injects burst failures and telemetry gaps; LOOP-08 is required fix and re-check. | Burn-rate breach or telemetry incompleteness yields deterministic stop state. |
| LOOP-08 | planned | OBS + SLO + SEL | Add hard requirement that missing OBS metrics/traces makes SLO result ineligible for pass-through. | Keeps observability mandatory in this loop. | LOOP-07 | Fail-closed telemetry dependency | Hidden-failure reduction | Mandatory fix step for RT-04 with regression tests for missing/invalid telemetry. | Missing or malformed OBS input leads to SLO non-pass and SEL stop record. |
| LOOP-09 | planned | FRE + EVL + PQX | Add Fix Integrity Proof checks showing no weakening of schema, test, eval, replay, lineage, or certification guarantees. | Prevents regression-inducing fixes from moving forward. | LOOP-08 | No hidden behavior during fix stage | Repair safety assurance | RT-05 attempts schema weakening/test removal/eval bypass; LOOP-10 must close all vectors and re-check. | Every fix yields a proof artifact covering protected guarantees. |
| LOOP-10 | planned | PQX + CDE + GOV | Add hard gate that requires Fix Integrity Proof before closure readiness and certification review. | Binds fix outcomes to closeout and promotion gating. | LOOP-09 | Hard-gate cohesion across systems | Promotion-path integrity | Required fix step for RT-05 with deterministic denial behavior checks. | Without proof artifact, closure readiness and promotion path remain blocked. |
| LOOP-11 | planned | REP + OBS + GOV | Add trend-to-roadmap feedback artifact for recurring failure signatures. | Converts repeated failure patterns into future hardening work. | LOOP-10 | Learning loop with governed artifacts | Anti-recurrence signal quality | RT-06 attempts suppression of recurrence trend output; LOOP-12 must add safeguards and re-check. | Recurrence threshold deterministically yields a roadmap-feedback artifact with lineage/replay refs. |
| LOOP-12 | planned | TLC + GOV | Add completion rule requiring red-team → fix → re-validation triplets for all checkpoints. | Prevents skipped adversarial follow-through. | LOOP-11 | Fail-closed completion discipline | Closeout confidence | Final red-team campaign tests skipped-fix and skipped-revalidation paths. | Missing follow-up step blocks loop completion and promotion path. |

## Red-Team Campaign (Integrated)

1. RT-01 routing bypass: direct PQX invocation without TLC route or AEX admission.
2. RT-02 control-evidence erosion: missing EVL coverage + conflicting TPA signals.
3. RT-03 certification-without-integrity: missing LIN/REP inputs before GOV review.
4. RT-04 chaos + observability loss: burst failures while traces/metrics are removed.
5. RT-05 fix-regression attack: schema weakening, test removal, eval bypass, control bypass.
6. RT-06 trend suppression: repeated failures masked to avoid hardening output.
7. Final campaign: loop marked complete with missing fix or missing re-validation.

Each red-team stage requires:
- a bounded fix stage,
- a re-validation stage rerunning the same adversarial case,
- proof that schema, replay, lineage, eval, control, enforcement, and certification guarantees were preserved.

## Chaos / Fail-Closed Proof Requirements

- Chaos steps include partial artifact loss, stale replay input, and conflicting system outputs.
- Missing eval, missing lineage, missing replay, missing control decision, missing certification evidence, or missing observability telemetry must stop progression.
- Stop outcomes must include machine-readable reason codes and trace refs.

## Promotion / Certification Hard Gates

Loop completion does not imply promotion. Promotion path requires:

1. EVL required coverage pass,
2. TPA trust-policy output present and unambiguous,
3. CDE readiness/promotion decision present,
4. SEL result consistent with CDE/TPA outputs,
5. LIN lineage completeness + authenticity pass,
6. REP replay integrity pass,
7. OBS telemetry completeness pass,
8. SLO posture acceptable for progression,
9. GOV certification evidence package present and valid — all required evidence contributions from CDE, PRA, POL, and LIN are present,
10. PRA promotion-readiness artifact present and valid as required input to CDE closure and GOV certification packaging — absent PRA artifact blocks both,
11. POL policy registry/rollout/canary posture present and valid when policy state affects the RFX path — absent or ambiguous POL evidence blocks promotion,
12. Completed red-team → fix → re-validation triplets.

Any missing element blocks progression deterministically.

## Gaps Identified

- No explicit repo-wide `phase_label: RFX` route contract in TLC artifacts.
- No single integrated pre-promotion completeness gate across all required systems.
- No standardized Fix Integrity Proof artifact covering schema/test/eval/control/replay/lineage/certification safeguards.
- No deterministic trend-to-roadmap artifact path for recurring failure signatures.
- GOV hard gate previously omitted PRA and POL: the canonical registry defines GOV upstream dependencies as CDE, PRA, POL, and LIN; PRA promotion-readiness artifact is a required input to the CDE closure and GOV certification flow. Without PRA and POL inputs, the CDE closure and GOV certification packaging are incomplete — a governance gap. Patched in LOOP-06 update.

## Red-Team Bypass Analysis

The following bypass vectors were red-teamed against the RFX path. Each has an explicit expected fail-closed result. No bypass is permitted to pass silently.

| Bypass Attempt | Description | Expected Fail-Closed Result |
| --- | --- | --- |
| GOV without PRA | GOV certification attempted without a passing PRA promotion-readiness record present | `rfx_missing_pra_evidence`: progression blocked; GOV certification withheld; reason code emitted |
| GOV without POL | GOV certification attempted without POL policy-registry/rollout/canary posture when policy state affects the RFX path | `rfx_missing_pol_evidence`: progression blocked; GOV certification withheld; reason code emitted |
| Direct PQX without AEX/TLC | PQX invoked for repo-mutating RFX work without a valid AEX admission record and TLC-mediated route lineage | `rfx_pqx_direct_invocation_blocked`: PQX execution rejected; deterministic stop reason emitted |
| CDE/SEL without EVL/TPA | CDE or SEL progression attempted with missing EVL evaluation evidence or missing/blocked TPA adjudication output | `rfx_missing_evl_evidence` or `rfx_missing_tpa_evidence`: CDE/SEL gate blocked; machine-readable reason codes emitted |

All four bypass vectors are covered by deterministic guard logic in `spectrum_systems/modules/runtime/rfx_route_guard.py` and verified by tests in `tests/test_rfx_route_guard.py`.

LOOP-04, LOOP-05, and LOOP-06 are enforced by the following guard modules and verified in `tests/test_rfx_loop_04_06_gates.py`:

- `spectrum_systems/modules/runtime/rfx_decision_bridge_guard.py` — `assert_rfx_cde_sel_decision_bridge` (LOOP-04: CDE -> SEL bridge).
- `spectrum_systems/modules/runtime/rfx_integrity_bundle.py` — `assert_rfx_integrity_bundle` (LOOP-05: LIN + REP).
- `spectrum_systems/modules/runtime/rfx_certification_gate.py` — `assert_rfx_certification_ready` (LOOP-06: GOV completeness incl. PRA + POL).

RFX execution order (no path reaches GOV without passing all three guards):

`RIL → FRE → PQX → EVL → TPA → CDE → assert_rfx_cde_sel_decision_bridge → assert_rfx_integrity_bundle → assert_rfx_certification_ready → SEL enforcement → GOV certification record`.

Canonical contribution roles, sourced from the system registry and not redefined here: the closure-decision contributor supplies the readiness decision artifact, the trust-policy contributor supplies trust/policy evidence, the enforcement contributor supplies enforcement evidence linked to the readiness decision artifact, the certification packager packages and certifies evidence completeness, the promotion-readiness contributor supplies the PRA input, the policy-posture contributor supplies the POL input, the lineage contributor supplies lineage evidence, and the replay contributor supplies replay evidence. The RFX guards verify the package without reassigning canonical contributions. RFX remains a phase label.

## Recommended Next Build Prompt

**Prompt Type:** BUILD

> Implement LOOP-01 through LOOP-03 only. Keep RFX as a phase label in TLC routing with AEX admission linkage. Add fail-closed tests proving direct PQX invocation without AEX/TLC artifacts is blocked, and prove missing EVL/TPA evidence stops downstream CDE/SEL progression. Do not add a new system.
