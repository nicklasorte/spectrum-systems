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
| LOOP-07 | implemented | OBS + SLO | Add burst-failure profile where repeated failures plus burn-rate pressure trigger freeze path. | Prevents silent reliability decay. | LOOP-06 | Reliability-preserving loop behavior | Burn-rate visibility | RT-04 chaos run injects burst failures and telemetry gaps; LOOP-08 is required fix and re-check. | Burn-rate breach, replay drift, instability, recurring/burst failure, or unknown reliability state yields deterministic freeze with `rfx_freeze_record` propagation. |
| LOOP-08 | implemented | OBS + SLO + SEL | Add hard requirement that missing OBS metrics/traces makes SLO result ineligible for pass-through. | Keeps observability mandatory in this loop. | LOOP-07 | Fail-closed telemetry dependency | Hidden-failure reduction | Mandatory fix step for RT-04 with regression tests for missing/invalid telemetry. | Missing or malformed OBS input or SLO computed independently of OBS yields `rfx_obs_incomplete` / `rfx_slo_inconsistent_with_obs` and SEL stop record. |
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

LOOP-04 → LOOP-06 are implemented in:

- `spectrum_systems/modules/runtime/rfx_decision_bridge_guard.py` (LOOP-04 — CDE → SEL bridge)
- `spectrum_systems/modules/runtime/rfx_integrity_bundle.py` (LOOP-05 — LIN + REP integrity bundle)
- `spectrum_systems/modules/runtime/rfx_certification_gate.py` (LOOP-06 — GOV certification hard gate, including PRA + POL)
- `spectrum_systems/modules/runtime/rfx_flow_integration.py` (composes LOOP-01..LOOP-08 in order)

LOOP-07 → LOOP-08 (reliability freeze + telemetry-enforced SLO) are implemented in:

- `spectrum_systems/modules/runtime/rfx_failure_profile.py` (failure profile model + `rfx_reliability_trend_record`)
- `spectrum_systems/modules/runtime/rfx_freeze_propagation.py` (`rfx_freeze_record` emitter, PQX/CDE/GOV/SEL propagation)
- `spectrum_systems/modules/runtime/rfx_reliability_freeze.py` (LOOP-07 reliability-freeze guard)
- `spectrum_systems/modules/runtime/rfx_telemetry_slo_gate.py` (LOOP-08 telemetry-enforced SLO gate)
- `spectrum_systems/modules/runtime/rfx_observability_replay_consistency.py` (OBS + REP cross-check)
- `spectrum_systems/modules/runtime/rfx_adversarial_reliability_guard.py` (anti-gaming guard)

Verified by tests:

- `tests/test_rfx_decision_bridge_guard.py`
- `tests/test_rfx_integrity_bundle.py`
- `tests/test_rfx_certification_gate.py`
- `tests/test_rfx_loop_04_06_red_team.py` (RT-01 .. RT-06)
- `tests/test_rfx_flow_integration.py` (full RFX flow ordering, LOOP-01..LOOP-06)
- `tests/test_rfx_failure_profile.py`
- `tests/test_rfx_freeze_propagation.py`
- `tests/test_rfx_reliability_freeze.py`
- `tests/test_rfx_telemetry_slo_gate.py`
- `tests/test_rfx_observability_replay_consistency.py`
- `tests/test_rfx_adversarial_reliability_guard.py`
- `tests/test_rfx_loop_07_08_chaos.py` (LOOP-07/08 chaos red-team coverage)

Canonical roles remain unchanged and are recorded in `docs/architecture/system_registry.md`. RFX itself remains a non-owning phase label across existing systems.

## RFX-05 → RFX-16 — Self-Improvement Loop (RFX-SUPER-01)

The remaining roadmap completes the RFX self-improvement loop:

`failure → eval → fix → proof → trend → roadmap → build recommendation`

Each slice below is a non-owning phase-label support helper. Canonical
authority for AEX/TLC/PQX/EVL/TPA/CDE/SEL/GOV/REP/LIN/OBS/SLO/PRA/POL/JDX/JSX/FRE/RIL
remains with the systems recorded in `docs/architecture/system_registry.md`.

| ID | Status | Existing System Owner | What It Builds | Why It Matters | Dependencies | Strategy Alignment | Primary Trust Gain | Red-Team / Fix Requirement | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RFX-05 | implemented | FRE + EVL + PQX + SEL | Fix Integrity Proof verifying schema, test, eval, replay, lineage, OBS/SLO, certification path, and registry-recorded boundaries are not weakened by a fix. | Prevents regression-inducing fixes from moving forward. | LOOP-08 | No hidden behavior during fix stage | Repair safety assurance | RT-13 attempts schema weakening / test removal / eval bypass; fix-follow-up restores guarantees and revalidation re-runs the same vector. | Every fix yields a proof artifact covering protected guarantees. |
| RFX-06 | implemented | FRE + EVL | Failure → eval auto-generation. Failure artifacts produce EVL-compatible regression eval candidates with deterministic case ids and lineage refs. | Closes the failure-to-eval gap so recurring failures cannot escape coverage. | RFX-05 | Learning loop with governed artifacts | Anti-recurrence eval coverage | RT-14 attempts to generate eval without trace/lineage; deterministic `rfx_failure_missing_trace` blocks. | Failures convert to deduped EVL handoff candidates while EVL retains canonical eval-coverage scope. |
| RFX-07 | implemented | FRE + OBS + REP | Trend detection + hotspot mapping over failures, repairs, replay drift, eval gaps, OBS gaps, freeze recurrence, and registry-shape findings. | Surfaces systemic weak points across the loop. | RFX-06 | Reliability-preserving loop behavior | Hotspot visibility | RT-15 splits a recurring reason code into variants; clustering still detects recurrence. | Trend artifact produced with deterministic hotspot ids. |
| RFX-08 | implemented | FRE + GOV | Trend → roadmap recommendation generator producing advisory `rfx_roadmap_recommendation` artifacts with red-team / fix / revalidation triad. | Converts trend signals into governed recommendations without mutating the canonical roadmap. | RFX-07 | Governed adoption | Recommendation quality | RT-16 attempts roadmap item without owner / dependency / red-team triad — blocked. | Recommendation includes source refs, owners, deps, and triad. |
| RFX-09 | implemented | OBS + SLO + SEL | Chaos campaign engine that continuously asserts fail-closed behavior across the full chaos scenario set. | Detects fail-open regressions across the RFX path. | RFX-08 | Fail-closed completion discipline | Chaos resilience | RT-17 injects a known-bad case that passes — campaign fails with `rfx_chaos_case_failed_open`. | Every required chaos scenario blocks deterministically with a recognized reason code. |
| RFX-10 | implemented | CDE + GOV + REP + POL | Cross-run consistency detector for equivalent inputs. | Catches decision/certification volatility and replay mismatch across runs. | RFX-09 | Decision trace completeness | Determinism confidence | RT-18 hides inconsistency by changing only non-material metadata — still detected. | Equivalent runs produce a consistency record; divergence yields `rfx_cross_run_inconsistency`. |
| RFX-11 | implemented | JDX + JSX | Judgment extraction from repeated decision/fix patterns into JDX-compatible candidates. | Converts repeat patterns into JDX candidates without mutating active judgment state. | RFX-10 | Governed adoption | Judgment evidence quality | RT-19 attempts judgment from a single isolated failure — blocked as insufficient. | Candidate produced only with sufficient evidence; JDX/JSX retain canonical roles. |
| RFX-12 | implemented | POL | Policy compilation: validated judgment candidates become POL-compatible candidate handoffs. | Routes hardened judgments toward POL governance without activating policy. | RFX-11 | Governed adoption | Policy candidate quality | RT-20 attempts to compile directly into active policy — blocked. | Handoff includes eval, rollout / canary requirements, and POL handoff target. |
| RFX-13 | implemented | EVL + GOV | Calibration + confidence control for fixes, evals, judgments, and recommendations. | Detects miscalibrated confidence before downstream consumption. | RFX-12 | Evidence honesty | Calibration confidence | RT-21 attempts a high-confidence claim without evidence refs — blocked. | Calibrated samples produce a calibration record; overconfidence/no-evidence cases block. |
| RFX-14 | implemented | SLO | Error-budget governance expansion: ties new-capability eligibility to SLO posture. | Prevents new capability work when reliability budget is exhausted. | RFX-13 | Reliability-preserving loop behavior | Budget discipline | RT-22 misclassifies feature work as reliability without evidence — blocked. | Exhausted budget freezes new capability; reliability work allowed only with evidence refs. |
| RFX-15 | implemented | OBS + REP | Institutional-memory layer indexing failures, fixes, evals, trends, judgments, policies, calibration records, and recommendations. | Enables retrieval-grounded learning across the loop without free-form mutable memory. | RFX-14 | Provenance + replay requirements | Retrieval discipline | RT-23 attempts to index unsupported memory without source refs — blocked. | Index entries carry artifact id, type, lineage refs, and reason codes. |
| RFX-16 | implemented | OBS + SLO + GOV | System-intelligence layer composing existing RFX artifacts into an advisory loop report. | Closes the self-improvement loop with composition only — no new ownership claim. | RFX-15 | Artifact-first route discipline | Advisory clarity | RT-24 attempts to claim authorization for execution / promotion via the report — blocked. | Report composes existing artifacts only; missing stages or unsupported next-build refs block. |

RFX-05 → RFX-16 are implemented in:

- `spectrum_systems/modules/runtime/rfx_fix_integrity_proof.py` (RFX-05)
- `spectrum_systems/modules/runtime/rfx_failure_to_eval.py` (RFX-06)
- `spectrum_systems/modules/runtime/rfx_trend_analysis.py` (RFX-07)
- `spectrum_systems/modules/runtime/rfx_roadmap_generator.py` (RFX-08)
- `spectrum_systems/modules/runtime/rfx_chaos_campaign.py` (RFX-09)
- `spectrum_systems/modules/runtime/rfx_cross_run_consistency.py` (RFX-10)
- `spectrum_systems/modules/runtime/rfx_judgment_extraction.py` (RFX-11)
- `spectrum_systems/modules/runtime/rfx_policy_compilation.py` (RFX-12)
- `spectrum_systems/modules/runtime/rfx_calibration.py` (RFX-13)
- `spectrum_systems/modules/runtime/rfx_error_budget_governance.py` (RFX-14)
- `spectrum_systems/modules/runtime/rfx_memory_index.py` (RFX-15)
- `spectrum_systems/modules/runtime/rfx_system_intelligence.py` (RFX-16)

Verified by tests:

- `tests/test_rfx_fix_integrity_proof.py` (RT-13)
- `tests/test_rfx_failure_to_eval.py` (RT-14)
- `tests/test_rfx_trend_analysis.py` (RT-15)
- `tests/test_rfx_roadmap_generator.py` (RT-16)
- `tests/test_rfx_chaos_campaign.py` (RT-17)
- `tests/test_rfx_cross_run_consistency.py` (RT-18)
- `tests/test_rfx_judgment_extraction.py` (RT-19)
- `tests/test_rfx_policy_compilation.py` (RT-20)
- `tests/test_rfx_calibration.py` (RT-21)
- `tests/test_rfx_error_budget_governance.py` (RT-22)
- `tests/test_rfx_memory_index.py` (RT-23)
- `tests/test_rfx_system_intelligence.py` (RT-24)

Each red-team campaign (RT-13 → RT-24) is followed by a fix step and a
revalidation test inside the same test module so the triad cannot be
skipped silently.

## Recommended Next Build Prompt

**Prompt Type:** BUILD

> Implement LOOP-01 through LOOP-03 only. Keep RFX as a phase label in TLC routing with AEX admission linkage. Add fail-closed tests proving direct PQX invocation without AEX/TLC artifacts is blocked, and prove missing EVL/TPA evidence stops downstream CDE/SEL progression. Do not add a new system.


## RFX-HARDEN-ALL (RFX-H01 → RFX-H19)

Status: implemented.

RFX-H01 through RFX-H19 are implemented as non-owning support helpers with deterministic reason codes, focused tests, and red-team/fix/revalidation coverage. RFX remains a phase label and supplies evidence, verification, and recommendations only.

| ID | Status | Module / Surface |
| --- | --- | --- |
| RFX-H01 | implemented | `rfx_health_contract.py` |
| RFX-H02 | implemented | `rfx_reason_code_registry.py` |
| RFX-H03 | implemented | `rfx_debug_bundle.py` |
| RFX-H04 | implemented | `rfx_output_envelope.py` |
| RFX-H05 | implemented | `rfx_golden_loop.py` |
| RFX-H06 | implemented | `rfx_dependency_map.py` |
| RFX-H07 | implemented | `rfx_bloat_budget.py` |
| RFX-H08 | implemented | `rfx_trend_clustering_hardening.py` |
| RFX-H09 | implemented | `rfx_calibration_policy_handoff.py` |
| RFX-H10 | implemented | `rfx_memory_persistence_handoff.py` |
| RFX-H11 | implemented | `rfx_authority_pattern_corpus.py` |
| RFX-H12 | implemented | `rfx_module_elimination.py` |
| RFX-H13 | implemented | `rfx_operator_runbook.py` |
| RFX-H14 | implemented | `rfx_golden_failure_corpus.py` |
| RFX-H15 | implemented | `scripts/run_rfx_super_check.py` |
| RFX-H16 | implemented | `rfx_architecture_drift_audit.py` |
| RFX-H17 | implemented | `rfx_contract_snapshot.py` |
| RFX-H18 | implemented | `rfx_unknown_state_campaign.py` |
| RFX-H19 | implemented | `rfx_authority_vocabulary_sweep.py` |

## RFX-OPS-01 Operational Maturity Layer (N09–N21)

Delivered 2026-04-29 via branch `claude/rfx-ops-maturity-QGgNh`.

All items are non-owning phase-label support helpers. No item claims
decision, approval, certification, enforcement, promotion, or adjudication
authority. Canonical ownership remains with systems declared in
`docs/architecture/system_registry.md`.

| ID | Status | Module | Failure Prevented | Signal Improved |
| --- | --- | --- | --- | --- |
| RFX-N09 | implemented | `rfx_golden_failure_corpus_v2.py` | Regression to known historical failures when corpus drift goes undetected | Regression coverage density; historical failure traceability (10 categories) |
| RFX-N10 | implemented | `rfx_authority_fixture_safety.py` | Static forbidden authority phrases persisting in fixture source | Fixture hygiene; authority-shape false-negative rate |
| RFX-N11 | implemented | `rfx_operator_surface_contract.py` | Operators receiving raw artifact walls instead of compact summaries | Operator surface clarity; artifact-wall detection rate |
| RFX-N12 | implemented | `rfx_simplification_review.py` | Unjustified helpers surviving without failure-prevention claim | Helper justification coverage; consolidation candidate count |
| RFX-N13 | implemented | `rfx_failure_replay_packet.py` | Failures that cannot be reproduced due to missing reproduction inputs | Replay reproducibility rate; packet completeness |
| RFX-N14 | implemented | `rfx_incident_to_eval_bridge.py` | Incidents closing without regression eval coverage | Incident-to-eval conversion rate; eval candidate coverage |
| RFX-N15 | implemented | `rfx_evidence_freshness_gate.py` | Stale proof inputs silently passing verification | Evidence freshness compliance rate |
| RFX-N16 | implemented | `rfx_cl_proof_alignment.py` | RFX proof diverging from CL proof shape causing silent misalignment | RFX↔CL proof alignment rate; field-presence coverage |
| RFX-N17 | implemented | `rfx_pr_failure_ingestion.py` | PR log data entering RFX without structured failure extraction | PR-failure-to-RFX conversion rate |
| RFX-N18 | implemented | `rfx_repair_prompt_generator.py` | Repair prompts lacking root cause, owner context, validation commands, or guards | Repair-prompt completeness rate; guard-constraint coverage |
| RFX-N19 | implemented | `rfx_merge_readiness_gate.py` | Merges proceeding with missing proof artifacts, guards, or test evidence | Merge-readiness confidence; proof/guard/test coverage rate |
| RFX-N20 | implemented | `rfx_operator_handbook.py` | Operators encountering reason codes with no plain-language action | Operator handbook coverage; plain-language action completeness |
| RFX-N21 | implemented | `rfx_bloat_burndown.py` | Duplicate or unjustified helpers surviving without governance oversight | Consolidation candidate identification rate |
