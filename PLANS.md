# PLANS.md

## Purpose
Define when a written execution plan is required and provide the standard template.
Plans prevent scope creep, unintended side effects, and mixed-type prompts.

---

## When a plan is required

A written plan is required before any `BUILD` or `WIRE` prompt that meets **any** of the following criteria:

| Condition | Threshold |
| --- | --- |
| Multi-file change | More than 2 files changed |
| New module | Introducing any new module, package, or directory |
| New contract or schema | Adding or modifying a JSON Schema in `contracts/schemas/` |
| Contract version bump | Incrementing any version in `contracts/standards-manifest.json` |
| Roadmap milestone | Implementing any A, B, or C slice of the H–AJ roadmap |
| Shared truth layer | Touching lifecycle definitions, artifact envelope, or shared provenance |
| Checkpoint bundle | Preparing any major checkpoint (L, P, Q+R, X+Z, AB, AJ) |

If the change is a single-file documentation fix or a trivial test addition, a plan is not required.
When in doubt, write a plan.

---

## How to write a plan

1. Create a file named `PLAN-<ITEM>-<DATE>.md` in `docs/review-actions/`.
   Example: `docs/review-actions/PLAN-M-2026-03-18.md`

2. Fill in the plan template below.

3. Submit the plan as a `PLAN` prompt to Codex or Claude for review before proceeding to `BUILD` or `WIRE`.

4. Reference the plan file in every subsequent `BUILD`, `WIRE`, `VALIDATE`, and `REVIEW` prompt for this item.

---

## Plan template

```markdown
# Plan — <ROADMAP ITEM> — <DATE>

## Prompt type
PLAN

## Roadmap item
<Item label from docs/roadmaps/codex-prompt-roadmap.md, e.g., M-B>

## Objective
<One sentence: what will be true after this plan is executed>

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| path/to/file.py | CREATE | ... |
| path/to/other.md | MODIFY | ... |

## Contracts touched
List any contracts that will be created, modified, or version-bumped.
If none, write "None".

## Tests that must pass after execution
List the specific test commands to run to validate this plan.

1. `pytest tests/test_<foo>.py`
2. `.codex/skills/golden-path-check/run.sh <CONTRACT_NAME>`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.
This prevents accidental expansion.

- Do not modify X
- Do not refactor Y
- Do not touch Z

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- <Item label> must be complete
```

---

## Active plans

| docs/review-actions/PLAN-BATCH-HR-C-FIX-01-2026-04-07.md | BATCH-HR-C-FIX-01 — Ecosystem registry / standards-manifest consumer mismatch repair | Active |
| docs/review-actions/PLAN-BATCH-HR-C-2026-04-07.md | BATCH-HR-C — Pre-PR governance closure + human checkpoint + permission policy consolidation | Active |
| docs/review-actions/PLAN-BATCH-GHA-02-2026-04-06.md | BATCH-GHA-02 — GitHub Closure + Continuation Pipeline (GHA-002) | Active |
| docs/review-actions/PLAN-BATCH-GHA-03-2026-04-06.md | BATCH-GHA-03 — Read-Only PR Feedback Publisher (GHA-003) | Active |
| docs/review-actions/PLAN-BATCH-GHA-07-2026-04-06.md | BATCH-GHA-07 — Roadmap Execution Bridge (Artifact → Execution) | Active |
| docs/review-actions/PLAN-BATCH-RIL-05-2026-04-05.md | BATCH-RIL-05 — Consumer Wiring / Validation Layer (RIL-005 + RIL-ARCH-01 + RIL-ARCH-02) | Active |
| docs/review-actions/PLAN-BATCH-FRE-01-2026-04-05.md | BATCH-FRE-01 — Failure Diagnosis Engine (FRE-001/FRE-002/FRE-003) | Active |
| docs/review-actions/PLAN-BATCH-TPA-09A-INTEGRATION-FIX-2026-04-05.md | BATCH-TPA-09A integration fix — preflight blocker + override test drift alignment | Active |
| docs/review-actions/PLAN-BATCH-TPA-09A-2026-04-05.md | BATCH-TPA-09A — Trust Boundary Hardening (TPA-ACT-08B-AR-01, TPA-ACT-08B-AR-02) | Active |
| docs/review-actions/PLAN-BATCH-TPA-04-2026-04-04.md | BATCH-TPA-04 — TPA Default Routing + Bypass Detection (TPA-014, TPA-017, TPA-018) | Active |
| docs/review-actions/PLAN-BATCH-TPA-02-2026-04-04.md | BATCH-TPA-02 — TPA Completion Hardening (TPA-006..TPA-012) | Active |
| docs/review-actions/PLAN-RUN-01-FIX-2026-04-04.md | RUN-01-FIX — Contract Preflight Block Remediation | Active |
| docs/review-actions/PLAN-BATCH-LTV-B-2026-04-04.md | BATCH-LTV-B — Decision-Quality Control (LT-05 + LT-06 + LT-09) | Active |
| docs/review-actions/PLAN-BATCH-LTV-A-2026-04-04.md | BATCH-LTV-A — Brownfield Trust Core (LT-01 + LT-02 + LT-04) | Active |
| docs/review-actions/PLAN-BATCH-LTV-D-2026-04-04.md | BATCH-LTV-D — Policy Extraction + Compression (LT-03) | Active |
| docs/review-actions/PLAN-BATCH-12-2026-04-04.md | BATCH-12 — Continuous Evaluation + Safety + Observability (ST-10 + ST-14 + ST-17 + ST-18) | Active |
| docs/review-actions/PLAN-BATCH-11-2026-04-04.md | BATCH-11 — Self-Correction + Stability Guarantees (A6 + A9 + A12 + A13) | Active |
| docs/review-actions/PLAN-BATCH-10-2026-04-04.md | BATCH-10 — Strictness + Explicit Decision Enforcement | Active |
| Plan file | Item | Status |
| docs/review-actions/PLAN-BATCH-A2-2026-04-04.md | BATCH-A2 — Capability Readiness + Trust Posture | Active |
| docs/review-actions/PLAN-BATCH-A4-2026-04-04.md | BATCH-A4 — Roadmap Self-Adaptation | Active |
| docs/review-actions/PLAN-RMP-014-FIX-2026-04-04.md | RMP-014-FIX — Strategy Compliance Repair for Governed Roadmap Projection | Active |
| docs/review-actions/PLAN-RMP-014-2026-04-04.md | RMP-014 — Machine-Readable Roadmap Normalization | Active |
| docs/review-actions/PLAN-BATCH-A3-2026-04-04.md | BATCH-A3 — Exception Router | Active |
| docs/review-actions/PLAN-BATCH-A1-2026-04-04.md | BATCH-A1 — Autonomy Guardrails | Active |
| docs/review-actions/PLAN-BATCH-S2-2026-04-04.md | BATCH-S2 — Self-Testing Foundation (ST-02 + ST-03 + ST-05 + ST-21) | Active |
| docs/review-actions/PLAN-BATCH-HANDOFF-MEMORY-2026-04-04.md | BATCH-HANDOFF-MEMORY — Batch Delivery + Handoff Memory | Active |
| docs/review-actions/PLAN-BATCH-S1-2026-04-04.md | BATCH-S1 — Trust Boundary Hardening (REPORT-003 + ST-01) | Active |
| docs/review-actions/PLAN-BATCH-MVP-END-TO-END-2026-04-04.md | BATCH-MVP-END-TO-END — Full Roadmap Execution (Control-Governed) | Active |
| docs/review-actions/PLAN-BATCH-MULTI-CYCLE-FIX-2026-04-04.md | BATCH-MULTI-CYCLE-FIX — Manifest Classification Repair | Active |
| docs/review-actions/PLAN-BATCH-MULTI-CYCLE-2026-04-04.md | BATCH-MULTI-CYCLE — Controlled Multi-Cycle Roadmap Execution Proof | Active |
| docs/review-actions/PLAN-BATCH-ROADMAP-ACTIVATE-2026-04-04.md | BATCH-ROADMAP-ACTIVATE — Governed Roadmap Activation | Active |
| docs/review-actions/PLAN-BATCH-CYCLE-RUNNER-2026-04-04.md | BATCH-CYCLE-RUNNER — Execute Exactly One Governed Next Cycle | Active |
| docs/review-actions/PLAN-BATCH-CYCLE-LOOP-2026-04-04.md | BATCH-CYCLE-LOOP — Bounded Next-Cycle Automation | Active |
| docs/review-actions/PLAN-BATCH-CYCLE-HARDEN-2026-04-04.md | BATCH-CYCLE-HARDEN — Bounded Loop Integrity Hardening | Active |
| docs/review-actions/PLAN-BATCH-RDX-LOOP-2026-04-03.md | BATCH-RDX-LOOP — Batch Continuation and Stop Logic | Active |
| docs/review-actions/PLAN-BATCH-MVP-20-2026-04-04.md | BATCH-MVP-20 — Governed 20-Slice Roadmap Execution Drill | Active |
| docs/review-actions/PLAN-BATCH-X1A-2026-04-03.md | BATCH-X1A — Adaptive Execution Artifact Class Alignment | Active |
| docs/review-actions/PLAN-BATCH-X1-2026-04-03.md | BATCH-X1 — Autonomy Guardrails + Observability | Active |
| docs/review-actions/PLAN-BATCH-W-2026-04-03.md | BATCH-W — Policy Tuning from Adaptive Execution Signals | Active |
| docs/review-actions/PLAN-BATCH-Y1-2026-04-03.md | BATCH-Y1 — Operator Clarity Polish | Active |
| docs/review-actions/PLAN-BATCH-Y-2026-04-03.md | BATCH-Y — Real-Use Shakeout + Friction Harvest | Active |
| docs/review-actions/PLAN-BATCH-PRG-ENFORCE-2026-04-04.md | BATCH-PRG-ENFORCE — Program Constraint and Drift Enforcement | Active |
| docs/review-actions/PLAN-BATCH-PRG-RECONCILE-2026-04-04.md | BATCH-PRG-RECONCILE — Reconcile Program Enforcement with MVP-20 Drill | Active |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PA-2026-04-03.md | BATCH-PA — Narrow Fix: Program Layer Contract Preflight Block Closure | Active |
| docs/review-actions/PLAN-BATCH-RA-2026-04-03.md | BATCH-RA — Narrow Fix: Review Artifact Class Alignment | Active |
| docs/review-actions/PLAN-BATCH-R-2026-04-03.md | BATCH-R — RVW + RPT governed Claude review system | Active |
| docs/review-actions/PLAN-BB-2026-03-19.md | Prompt BB — Failure-First Observability | Active |
| docs/review-actions/PLAN-BB-PLUS-1-2026-03-19.md | Prompt BB+1 — Failure Enforcement & Control Layer | Active |
| docs/review-actions/PLAN-BN.6-2026-03-20.md | BN.6 — Control Signal Consumption Layer | Active |
| docs/review-actions/PLAN-BPA-2026-03-20.md | Prompt BPA — Strategic Knowledge Layer Foundation | Active |
| docs/review-actions/PLAN-BPA-FIX-2026-03-20.md | Prompt BPA — CI/Registry/Contract Hardening Fixes | Active |
| docs/review-actions/PLAN-BPB-2026-03-21.md | Prompt BPB — Strategic Knowledge Validation Gate | Active |
| docs/review-actions/PLAN-BPB-BOUNDARY-FIX-2026-03-21.md | Prompt BPB — Boundary Compliance Fix | Active |
| docs/review-actions/PLAN-BAB-2026-03-21.md | Prompt BAB — Trace Context Injection | Active |
| docs/review-actions/PLAN-GOVERNANCE-CONSUMER-DRIFT-2026-03-21.md | GOV-CONSUMER-DRIFT — Consumer consistency remediation | Active |
| docs/review-actions/PLAN-DEV-ENV-CONTRACT-2026-03-21.md | DEV-ENV-CONTRACT — Dev environment runtime contract hardening | Active |
| docs/review-actions/PLAN-RUN-BUNDLE-VALIDATION-2026-03-21.md | RUN-BUNDLE-VALIDATION — MVP foundation enforcement boundary | Active |
| docs/review-actions/PLAN-CONTROL-LOOP-INTEGRATION-2026-03-21.md | CONTROL LOOP INTEGRATION — MVP Phase 2 | Active |
| docs/review-actions/PLAN-BAF-2026-03-21.md | Prompt BAF — Enforcement Wiring (MVP Phase 3) | Active |
| docs/review-actions/PLAN-BAG-REPLAY-ENGINE-MVP-PHASE-4-2026-03-21.md | BAG — Replay Engine (MVP Phase 4) | Active |
| docs/review-actions/PLAN-BAH-2026-03-21.md | Prompt BAH — Drift Detection System | Active |
| docs/review-actions/PLAN-BAZ-2026-03-21.md | Prompt BAZ — Agent Execution Module | Active |
| docs/review-actions/PLAN-BBA-2026-03-21.md | BBA — Eval → Control Loop Integration | Active |
| docs/review-actions/PLAN-BBB-CONTRACT-COLLISION-FIX-2026-03-22.md | BBB Contract Collision Fix — eval_case → failure_eval_case split | Active |
| docs/review-actions/PLAN-BAS-POLICY-VERSIONING-FIX-2026-03-22.md | BAS Policy Versioning Narrow Fix | Active |
| docs/review-actions/PLAN-BAS-POLICY-VERSIONING-FOLLOWUP-FIX-2026-03-22.md | BAS Policy Versioning Follow-up Fix | Active |
| docs/review-actions/PLAN-BBC-2026-03-22.md | Prompt BBC — Eval Registry + Dataset Governance | Active |
| docs/review-actions/PLAN-BBC-CANONICALIZATION-POLICY-2026-03-22.md | Prompt BBC — Canonicalization policy governance hardening | Active |
| docs/review-actions/PLAN-BAE-2026-03-22.md | Prompt BAE — Control Loop Integration | Active |
| docs/review-actions/PLAN-BAF-2026-03-22.md | Prompt BAF — Enforcement Wiring (single-path evaluation_control_decision enforcement) | Active |
| docs/review-actions/PLAN-BAG-2026-03-22.md | Prompt BAG — Replay Engine (Deterministic Control Replay) | Active |
| docs/review-actions/PLAN-BAH-DRIFT-RESULT-2026-03-22.md | Prompt BAH — Drift Result contract + replay wiring | Active |
| docs/review-actions/PLAN-BBC-REVIEW-2-ADMISSION-FIX-2026-03-22.md | Prompt BBC — Review 2 deterministic/governance admission fixes | Active |
| docs/review-actions/PLAN-BAF-ENFORCEMENT-WIRING-FIX-2026-03-22.md | Prompt BAF — Enforcement Wiring trust-boundary remediation | Active |
| docs/review-actions/PLAN-BAF-CANONICAL-ENFORCEMENT-VOCAB-2026-03-23.md | Prompt BAF — Canonical enforcement vocabulary alignment | Active |
| docs/review-actions/PLAN-BAJ-PROVENANCE-HARDENING-PHASE1-2026-03-22.md | BAJ Provenance Hardening — Phase 1 narrow spine fix | Active |
| docs/review-actions/PLAN-BAJ-CLI-PROVENANCE-COMPLETION-2026-03-23.md | BAJ migration completion — strategic-knowledge CLI provenance/output contract alignment | Active |
| docs/review-actions/PLAN-BAE-HARDENING-2026-03-22.md | BAE hardening patch — observe/enforce fail-closed fixes | Active |
| docs/review-actions/PLAN-BAE-INTERPRET-HARDENING-2026-03-22.md | BAE interpret hardening patch — semantics and provenance integrity | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-MVP-2026-03-22.md | Governed Prompt Queue MVP — orchestration backbone | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-2026-03-22.md | Governed prompt queue review parsing — structured findings extraction | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-PROMPT-2026-03-22.md | Governed prompt queue repair prompt generation — findings→repair artifact | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-CHILD-CREATION-2026-03-22.md | Governed prompt queue repair child creation — repair artifact→child queue item | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-EXECUTION-GATING-2026-03-22.md | Governed prompt queue execution gating — repair-loop control policy | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-CONTROLLED-EXECUTION-2026-03-22.md | Governed Prompt Queue — bounded controlled execution MVP | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-POST-EXECUTION-2026-03-22.md | Governed prompt queue post-execution policy — execution-result decision loop | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-NEXT-STEP-2026-03-22.md | Governed Prompt Queue — Next-step orchestration from post-execution decision artifacts | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LOOP-CONTROL-2026-03-22.md | Governed Prompt Queue — deterministic repair loop control and budget enforcement | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LIVE-REVIEW-INVOCATION-IMPLEMENTATION-2026-03-22.md | Governed Prompt Queue — live review invocation bounded implementation slice | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-HANDOFF-2026-03-22.md | Governed Prompt Queue — invocation output→review parsing handoff integration | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-FINDINGS-REENTRY-2026-03-22.md | Governed Prompt Queue — findings-to-repair reentry wiring | Active |

| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-LOOP-CONTINUATION-POLISH-2026-03-22.md | Governed Prompt Queue — loop continuation child spawn + continuation polish | Active |

| docs/review-actions/PLAN-BAG-LEGACY-REPLAY-CLOSURE-2026-03-23.md | Prompt BAG — legacy replay seam closure (surgical hardening) | Active |

| docs/review-actions/PLAN-SF-07-2026-03-24.md | SF-07 — Coverage + Slice Dashboard for eval visibility | Active |
| docs/review-actions/PLAN-SF-12-2026-03-24.md | SF-12 — Control-Loop Chaos Tests for deterministic controller correctness | Active |

| docs/review-actions/PLAN-AG-01-2026-03-24.md | AG-01 — Agent Runtime Golden Path | Active |
| docs/review-actions/PLAN-AG-02-2026-03-24.md | AG-02 — Agent Failure Artifact Path | Active |
| docs/review-actions/PLAN-AG-03-2026-03-24.md | AG-03 — HITL Review Queue | Active |
| docs/review-actions/PLAN-AG-04-2026-03-24.md | AG-04 — Override Artifact Enforcement | Active |
| docs/review-actions/PLAN-AG-05-2026-03-24.md | AG-05 — Failure → Eval Auto-Generation | Active |
| docs/review-actions/PLAN-HS-01-2026-03-24.md | HS-01 — Prompt Registry + Versioning System | Active |
| docs/review-actions/PLAN-HS-03-2026-03-24.md | HS-03 — Model Adapter Layer | Active |
| docs/review-actions/PLAN-HS-X1-2026-03-24.md | HS-X1 — Structured Decoding + Schema-Constrained Generation | Active |
| docs/review-actions/PLAN-HS-X3-2026-03-24.md | HS-X3 — Prompt Injection Defense Layer | Active |
| docs/review-actions/PLAN-HS-06-2026-03-24.md | HS-06 — Context Bundle v2 (Typed + Trusted) | Active |
| docs/review-actions/PLAN-HS-07-2026-03-24.md | HS-07 — Retrieval + Context Trust Segmentation | Active |
| docs/review-actions/PLAN-HS-18-2026-03-24.md | HS-18 — Glossary Injection + Domain Canonicalization | Active |
| docs/review-actions/PLAN-HS-18-FIX-2026-03-24.md | HS-18 follow-up fix — explicit glossary policy + baseline compatibility restoration | Active |
| docs/review-actions/PLAN-HS-18-FIX2-2026-03-24.md | HS-18 follow-up fix 2 — policy/defaulting + trace-state closure | Active |
| docs/review-actions/PLAN-HS-08-2026-03-24.md | HS-08 — Multi-Pass Artifact Generation Engine | Active |
| docs/review-actions/PLAN-HS-09-2026-03-24.md | HS-09 — Evidence Binding + Citation System | Active |

| docs/review-actions/PLAN-SRE-08-SRE-10-2026-03-24.md | SRE-08 + SRE-10 — SLO Definition + Observability Metrics | Active |
| docs/review-actions/PLAN-SRE-09-SRE-10-INTEGRATION-2026-03-27.md | SRE-09/SRE-10 — Error-budget-aware control-loop integration | Active |
| docs/review-actions/PLAN-SRE-09-SRE-10-TEST-SCAFFOLD-TIGHTENING-2026-03-27.md | SRE-09/SRE-10 — test/fixture alignment with replay budget consistency hardening | Active |

| docs/review-actions/PLAN-PQX-CLT-002-2026-03-27.md | PQX-CLT-002 — Control Loop Trust Hardening | Active |
| docs/review-actions/PLAN-PQX-CLT-003-2026-03-27.md | PQX-CLT-003 — Governed Control-Loop Certification Pack (trust-boundary/runtime) | Active |
| docs/review-actions/PLAN-PQX-CLT-004-2026-03-27.md | PQX-CLT-004 — Control-loop promotion certification gate wiring | Active |

| docs/review-actions/PLAN-TRACE-STORE-ISOLATION-HARDENING-2026-03-26.md | TRACE-STORE-ISOLATION-HARDENING — narrow global trace-state regression hardening | Active |
| docs/review-actions/PLAN-SRE-03-REPLAY-CONTRACT-BOUNDARY-HARDENING-2026-03-26.md | SRE-03 — replay-adjacent governed contract boundary hardening slice | Active |
| docs/review-actions/PLAN-ADV-01-2026-03-28.md | ADV-01 — Policy Backtesting / Scenario Simulation | Active |

| docs/review-actions/PLAN-PQX-QUEUE-01-2026-03-28.md | [ROW: QUEUE-01] Queue Manifest and State Contract Spine | Active |
| docs/review-actions/PLAN-PQX-QUEUE-02-2026-03-28.md | [ROW: QUEUE-02] Step Execution Adapter Normalization | Active |
| docs/review-actions/PLAN-PQX-QUEUE-04-2026-03-28.md | [ROW: QUEUE-04] Unified Transition Policy and Next-Step Decision Spine | Active |
| docs/review-actions/PLAN-PQX-QUEUE-04A-2026-03-28.md | [ROW: QUEUE-04] Repair Slice QUEUE-04A — Export Compatibility Fix | Active |
| docs/review-actions/PLAN-PQX-QUEUE-04B-2026-03-28.md | [ROW: QUEUE-04] Repair Slice QUEUE-04B — Legacy Queue-Integration Semantics Compatibility | Active |
| docs/review-actions/PLAN-PQX-QUEUE-07-2026-03-28.md | [ROW: QUEUE-07] Queue Observability and Health Classification | Active |
| docs/review-actions/PLAN-PQX-QUEUE-11-2026-03-28.md | [ROW: QUEUE-11] Queue Audit Bundle | Active |
| docs/review-actions/PLAN-PQX-QUEUE-RUN-01-2026-03-28.md | PQX-QUEUE-RUN-01 — First Sequential Automatic Queue Run | Active |
| docs/review-actions/PLAN-VAL-11-2026-03-28.md | VAL-11 — Certification Integrity | Active |
| docs/review-actions/PLAN-VAL-11-TRACE-HARDENING-2026-03-28.md | VAL-11 — Trace Linkage Hardening Defect Fix | Active |
| docs/review-actions/PLAN-VAL-04-2026-03-28.md | VAL-04 — Control Decision Consistency | Active |
| docs/review-actions/PLAN-VAL-06-2026-03-28.md | VAL-06 — XRUN Signal Quality | Active |
| docs/review-actions/PLAN-VAL-07-2026-03-28.md | VAL-07 — Eval Auto-Generation Quality | Active |
| docs/review-actions/PLAN-VAL-10-2026-03-28.md | VAL-10 — Policy Enforcement Integrity | Active |

| docs/review-actions/PLAN-CONTRACT-DRIFT-LINEAGE-CERT-2026-03-29.md | Contract drift migration — lineage/certification builder alignment | Active |

| docs/review-actions/PLAN-CONTRACT-DRIFT-MMR-OBSERVABILITY-2026-03-29.md | Contract drift follow-up — meeting minutes + observability metadata fixes | Active |

| docs/review-actions/PLAN-REQUIRED-IDS-SANITIZATION-2026-03-29.md | REQUIRED-IDS-SANITIZATION — deterministic sanitization + required run/trace identity enforcement | Active |

| docs/review-actions/PLAN-PQX-QUEUE-RUN-02-2026-03-29.md | PQX-QUEUE-RUN-02 — governed sequential PQX execution with continuity checks and resumable state | Active |

| docs/review-actions/PLAN-G1-B11-B14-2026-03-29.md | G1 B11–B14 — Dominant Single-Slice Execution Path | Active |

| docs/review-actions/PLAN-G2-B15-B18-2026-03-29.md | G2 B15–B18 — Two-slice continuation governance and replay parity | Active |

| docs/review-actions/PLAN-G3-G4-B19-B26-2026-03-29.md | G3+G4 B19–B26 — Multi-slice governance + bundle execution system | Active |
| docs/review-actions/PLAN-G5-B27-B30-2026-03-29.md | G5 B27–B30 — Queue-aware scheduling + canary + judgment + N-slice validation | Active |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-2026-03-30.md | AUTONOMOUS-LOOP-FDN-01 — Autonomous execution loop control-plane foundation | Active |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-CLOSED-2026-03-30.md | CTRL-LOOP-01 — Closed-loop PQX + certification write-back bundle | Active |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-REVIEW-FIX-REENTRY-2026-03-30.md | CTRL-LOOP-01 — Grouped review ingestion + fix-roadmap + PQX re-entry slice | Active |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-OBSERVABILITY-2026-03-30.md | CTRL-LOOP-01 — cycle status/observability grouped PQX slice | Active |
| docs/review-actions/PLAN-CTRL-LOOP-JUDGMENT-LAYER-2026-03-30.md | CTRL-LOOP-01 grouped PQX slice — judgment + precedent layer | Active |
| docs/review-actions/PLAN-CTRL-LOOP-JUDGMENT-MANIFEST-COMPAT-2026-03-30.md | CTRL-LOOP-01 surgical hardening — cycle_manifest judgment field propagation | Active |
| docs/review-actions/PLAN-CTRL-LOOP-02-ENFORCEMENT-2026-03-30.md | CTRL-LOOP-02 grouped PQX slice — escalation enforcement action/outcome/remediation wiring | Active |
| docs/review-actions/PLAN-CTRL-LOOP-04-READINESS-OBSERVABILITY-2026-03-30.md | CTRL-LOOP-04 grouped PQX slice — remediation/reinstatement readiness observability | Active |
| docs/review-actions/PLAN-CTRL-LOOP-05-POLICY-LIFECYCLE-2026-03-30.md | CTRL-LOOP-05 grouped PQX slice — judgment policy lifecycle governance (canary/promotion/rollback/revoke) | Active |
| docs/review-actions/PLAN-CTRL-LOOP-05-LIFECYCLE-ENFORCEMENT-HARDENING-2026-03-30.md | CTRL-LOOP-05 grouped PQX slice — mandatory lifecycle/rollout enforcement in governed runtime/control paths | Active |
| docs/review-actions/PLAN-CTRL-LOOP-05-CYCLE-MANIFEST-PROPAGATION-FIX-2026-03-30.md | CTRL-LOOP-05 surgical hardening — cycle_manifest lifecycle/rollout producer propagation fix | Active |
| docs/review-actions/PLAN-STRATEGY-SOURCE-GOVERNANCE-HARDENING-2026-03-30.md | Grouped PQX slice — strategy/source authority enforcement for roadmap/review/progression seams | Active |
| docs/review-actions/PLAN-CTRL-LOOP-03-STRATEGY-SOURCE-AUTHORITY-2026-03-30.md | CTRL-LOOP-03 grouped PQX slice — strategy/source authority loop hard-gate wiring | Active |

| docs/review-actions/PLAN-PQX-NEXT-STEP-DECISION-POLICY-2026-03-30.md | PQX Next-Step Decision Policy Externalization | Active |
| docs/review-actions/PLAN-G11-ELIGIBILITY-DECISION-HARD-BINDING-2026-03-31.md | G11 — Eligibility → Decision Hard Binding | Active |
| docs/review-actions/PLAN-G11-CYCLE-MANIFEST-SOURCE-OF-TRUTH-2026-03-31.md | G11 — Cycle manifest source-of-truth hardening | Active |
| docs/review-actions/PLAN-STRATEGY-ENFORCEMENT-LAYER-2026-03-31.md | STRATEGY-ENFORCEMENT-LAYER — Strategy control enforcement across roadmap prompt/output and CI | Active |
| docs/review-actions/PLAN-ROADMAP-CONTRACT-REPAIR-2026-03-31.md | ROADMAP-CONTRACT-REPAIR — roadmap table contract and replay/trace compliance remediation | Active |
| docs/review-actions/PLAN-PQX-G14-EXECUTION-CHANGE-IMPACT-GATE-2026-03-30.md | G14 — Execution change impact pre-execution fail-closed gate | Active |
| docs/review-actions/PLAN-G17-MANIFEST-COMPLETENESS-GATE-2026-03-31.md | G17 — Manifest Completeness Gate (Pre-PR Structural Integrity) | Active |
| docs/review-actions/PLAN-G17-SCOPE-REPAIR-2026-03-31.md | G17 — Manifest Completeness Gate Scope Repair | Active |
| docs/review-actions/PLAN-ROADMAP-GENERATION-OPERATING-MODEL-2026-03-31.md | ROADMAP-GENERATION-OPERATING-MODEL — governed roadmap refresh + compatibility reconciliation | Active |
| docs/review-actions/PLAN-RE-06-ROADMAP-RECONCILIATION-2026-03-31.md | RE-06 — roadmap authority reconciliation to approved RE-05 corrections | Active |
| docs/review-actions/PLAN-RE-02-REPO-GAP-SCAN-2026-03-31.md | RE-02 — source-obligation repo gap scan and bottleneck classification | Active |
| docs/review-actions/PLAN-RE-07-CL-02-2026-03-31.md | RE-07 CL-02 — Error Budget Enforcement | Active |
| docs/review-actions/PLAN-RE-07-CL-02.1-2026-03-31.md | RE-07 CL-02.1 — Error Budget Contract Repair | Active |
| docs/review-actions/PLAN-RE-07-CL-03-2026-03-31.md | RE-07 CL-03 — Recurrence Prevention | Active |
| docs/review-actions/PLAN-RE-07-CL-05-2026-03-31.md | RE-07 CL-05 — Longitudinal Calibration | Active |
| docs/review-actions/PLAN-RE-07-CL-05.1-2026-03-31.md | RE-07 CL-05.1 — Longitudinal Calibration Linkage Repair | Active |

| docs/review-actions/PLAN-FOUNDATION-AUTHORITY-WIRING-2026-04-01.md | ROADMAP-GOVERNANCE-FOUNDATION-AUTHORITY-WIRING — foundation-first authority normalization | Active |
| docs/review-actions/PLAN-BUNDLE-B-017-2026-04-01.md | BUNDLE-B-017 — Proof Closure + Certification Hardening (G3/G4 + Hard Gate Proof) | Active |
| docs/review-actions/PLAN-ALIGNMENT-019-RESET-2026-04-01.md | ALIGNMENT-019-RESET — Foundation Alignment Reset (Trust Spine Closure, Preflight-First) | Active |
| docs/review-actions/PLAN-RED-TEAM-CLOSURE-021-2026-04-01.md | RED-TEAM-CLOSURE-021 — Post-ALIGNMENT_020 trust-spine hardening bundle | Active |
| docs/review-actions/PLAN-RED-TEAM-CLOSURE-021-FIX-2026-04-01.md | RED-TEAM-CLOSURE-021-FIX — Threshold context boundary repair (runtime vs comparative analysis) | Active |
| docs/review-actions/PLAN-CON-036-GAP-PACKET-PROPAGATION-AND-SEQUENCE-VISIBILITY-2026-04-02.md | CON-036 — PQX gap-packet propagation and sequence-level visibility | Active |
| docs/review-actions/PLAN-CONVERGENCE-025-TRUST-SPINE-INVARIANTS-2026-04-01.md | CONVERGENCE-025 — Trust-Spine Invariants + Cross-Seam Drift Detection Hardening | Active |
| docs/review-actions/PLAN-CONVERGENCE-026-TRUST-SPINE-EVIDENCE-COMPLETENESS-2026-04-01.md | CONVERGENCE-026 — Trust-Spine Evidence Completeness | Active |
| docs/review-actions/PLAN-CON-029-CONTROL-SURFACE-MANIFEST-2026-04-01.md | CON-029 — Control Surface Manifest + Invariant Coverage Registry | Active |
| docs/review-actions/PLAN-CON-030-CONTROL-SURFACE-ENFORCEMENT-2026-04-01.md | CON-030 — Control Surface Manifest Enforcement | Active |
| docs/review-actions/PLAN-CON-030-PREFLIGHT-FIX-2026-04-01.md | CON-030 — Preflight BLOCK reconciliation | Active |
| docs/review-actions/PLAN-CON-031-MANIFEST-RUNTIME-OBEDIENCE-PROOF-2026-04-01.md | CON-031 — Manifest-to-Runtime Obedience Proof | Active |
| docs/review-actions/PLAN-CON-032-CONTROL-SURFACE-GAP-TO-PQX-2026-04-01.md | CON-032 — Control Surface Gap → PQX Triage Integration | Active |
| docs/review-actions/PLAN-CON-032-FIX-RECONCILE-PREFLIGHT-BLOCK-2026-04-02.md | CON-032-FIX — Reconcile Preflight BLOCK | Active |
| docs/review-actions/PLAN-CON-033-TRUST-SPINE-EVIDENCE-COHESION-2026-04-02.md | CON-033 — Trust-spine evidence chain cohesion | Active |
| docs/review-actions/PLAN-CON-033-FIX-PREFLIGHT-BLOCK-2026-04-02.md | CON-033-FIX — Reconcile exact contract preflight BLOCK | Active |
| docs/review-actions/PLAN-CON-033-FIX-ARTIFACT-CLASS-GOVERNANCE-2026-04-02.md | CON-033-FIX-2 — Reconcile artifact_class enum drift | Active |
| docs/review-actions/PLAN-CON-034-CONTROL-SURFACE-GAP-EXTRACTION-2026-04-02.md | CON-034 — Control Surface Gap Extraction | Active |
| docs/review-actions/PLAN-CON-035-GAP-PACKET-PQX-BRIDGE-2026-04-02.md | CON-035 — Control Surface Gap Packet → PQX Bridge (Governed Ingestion) | Active |
| docs/review-actions/PLAN-CON-035-FIX-PREFLIGHT-GAP-PACKET-PQX-2026-04-02.md | CON-035-FIX — Preflight classification + required-test mapping alignment | Active |
| docs/review-actions/PLAN-CON-037-DEFAULT-PQX-EXECUTION-POLICY-2026-04-02.md | CON-037 — Default PQX Execution Policy for Governed Work | Active |
| docs/review-actions/PLAN-CON-037-FIX-CI-PREFLIGHT-COMPAT-2026-04-02.md | CON-037 FIX — Default PQX Execution Policy CI/Preflight Compatibility Hardening | Active |
| docs/review-actions/PLAN-CON-038-CODEX-TO-PQX-TASK-WRAPPER-2026-04-02.md | CON-038 — Codex-to-PQX Task Wrapper | Active |
| docs/review-actions/PLAN-CON-039-PQX-REQUIRED-CONTEXT-ENFORCEMENT-2026-04-02.md | CON-039 — PQX Required Context Enforcement | Active |
| docs/review-actions/PLAN-CON-039-FIX-SCHEMA-BACKED-PREFLIGHT-REQUIRED-CONTEXT-2026-04-02.md | CON-039-FIX — Schema-backed preflight required-context artifact completion | Active |
| docs/review-actions/PLAN-CON-039-FIX-COMMIT-RANGE-PREFLIGHT-COMPAT-2026-04-02.md | CON-039-FIX — Commit-range preflight compatibility (enforcement-aware) | Active |
| docs/review-actions/PLAN-CON-046-PQX-SEQUENTIAL-EXECUTION-LOOP-2026-04-02.md | CON-046 — PQX Sequential Execution Loop (Control-Loop Native MVP) | Active |
| docs/review-actions/PLAN-CON-046-FIX-PQX-AUTHORITY-EVIDENCE-2026-04-02.md | CON-046-FIX — Emit PQX Authority Evidence for Preflight Compatibility | Active |
| docs/review-actions/PLAN-CON-046-FIX2-DETERMINISTIC-PACKAGING-PREFLIGHT-BRIDGE-2026-04-02.md | CON-046-FIX2 — Deterministic study_state packaging + preflight authority bridge completion | Active |
| docs/review-actions/PLAN-CON-047-AUTHORITATIVE-PQX-EXECUTION-TRACE-2026-04-02.md | CON-047 — Authoritative PQX Execution Trace Artifact | Active |
| docs/review-actions/PLAN-CON-047-FIX-RUNTIME-SEAM-2026-04-02.md | CON-047-FIX — PQX runtime seam decision propagation + determinism fix | Active |

| docs/review-actions/PLAN-TPA-001-2026-04-03.md | TPA-001–TPA-005 — PQX two-pass governed construction integration | Active |
| docs/review-actions/PLAN-MAP-001-MAP-002-2026-04-03.md | MAP-001 + MAP-002 — Review artifact foundation and review→eval→control wiring | Active |
| docs/review-actions/PLAN-RDX-001-2026-04-03.md | RDX-001 — BATCH-M: Roadmap Artifact Foundation | Active |
| docs/review-actions/PLAN-RDX-002-2026-04-03.md | RDX-002 — BATCH-M: Roadmap Selection + Readiness Validation | Active |
| docs/review-actions/PLAN-RDX-002A-2026-04-03.md | RDX-002A — BATCH-M Follow-Up: Contract Preflight Repair | Active |
| docs/review-actions/PLAN-RDX-003-2026-04-03.md | RDX-003 — BATCH-M: Control Authorization for Roadmap-Selected Batch | Active |
| docs/review-actions/PLAN-RDX-004-2026-04-03.md | RDX-004 — BATCH-M: Authorized Batch Execution + Roadmap Progress Update | Active |
| docs/review-actions/PLAN-RDX-005-2026-04-03.md | RDX-005 — BATCH-M: End-to-End Roadmap Execution Loop Validation | Active |
| docs/review-actions/PLAN-RDX-006-2026-04-03.md | RDX-006 — BATCH-M: Bounded Multi-Batch Roadmap Execution | Active |

| docs/review-actions/PLAN-OPS-01-2026-04-04.md | OPS-01 — Autonomous Operations Runbook + Monitoring Contract | Active |

| docs/review-actions/PLAN-OPS-01-FIX-2026-04-04.md | OPS-01-FIX — Manifest Artifact Class Compatibility Repair | Active |
| docs/review-actions/PLAN-OPS-02-2026-04-04.md | OPS-02 — Scheduled Autonomous Execution + Passive Monitoring | Active |
| docs/review-actions/PLAN-OPS-03-FIX-2026-04-04.md | OPS-03-FIX — Contract Preflight Required-Surface Linkage Repair | Active |

Update this table when plans are created or completed.

---

| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-TRIGGER-2026-03-22.md | Governed Prompt Queue — automatic review triggering | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-BLOCKED-RECOVERY-2026-03-22.md | Governed Prompt Queue — blocked-item recovery policy | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-RETRY-POLICY-2026-03-22.md | Governed Prompt Queue — deterministic retry policy slice | Active |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-OBSERVABILITY-2026-03-22.md | Governed Prompt Queue — deterministic read-only observability snapshot slice | Active |
## Plan lifecycle

```
PLAN written → Codex/Claude review → BUILD/WIRE executes → VALIDATE passes → plan closed
```

A plan is **closed** when its VALIDATE slice passes and the result is committed.
Closed plans are not deleted — they remain as execution history.

| docs/review-actions/PLAN-SF-14-2026-03-24.md | SF-14 — Release + Canary Policy for governed staged promotion and rollback | Active |
| docs/review-actions/PLAN-SF-14.5-2026-03-24.md | SF-14.5 — Trust hardening for deterministic identity, precedence, indeterminate handling, and coverage parity | Active |
| docs/review-actions/PLAN-SF-14.6-2026-03-24.md | SF-14.6 — Cleanup for script boundaries, dependency bootstrap, and envelope consistency | Active |
| docs/review-actions/PLAN-ARTIFACT-ENVELOPE-HARDENING-2026-03-24.md | Artifact envelope hardening — canonical governed envelope enforcement | Active |
| docs/review-actions/PLAN-SRE-03-REPLAY-AUTH-SEAM-2026-03-26.md | SRE-03 — Replay authoritative seam hardening | Active |
| docs/review-actions/PLAN-SRE-03-REPLAY-FIXTURE-ALIGN-2026-03-26.md | SRE-03 — Replay fixture alignment follow-on | Active |
| docs/review-actions/PLAN-SRE-03-REPLAY-ENFORCEMENT-COMPLETION-2026-03-26.md | SRE-03 — Replay enforcement completion (replay-only downstream runtime boundary) | Active |
| docs/review-actions/PLAN-SRE-03-REPLAY-ENFORCEMENT-TEST-MIGRATION-2026-03-26.md | SRE-03 — Replay enforcement test migration for replay-only boundaries | Active |

| docs/review-actions/PLAN-PQX-QUEUE-10-2026-03-28.md | [ROW: QUEUE-10] Queue Certification Gate | Active |

| docs/review-actions/PLAN-RUNTIME-PROVENANCE-ANCHORS-2026-03-29.md | Post-runtime-identity hardening — provenance anchors across persistence and downstream seams | Active |

| docs/review-actions/PLAN-NEXT-STEP-DECISION-ENGINE-P1-2026-03-30.md | NEXT-STEP-DECISION-ENGINE-P1 — Controlled next-step decision engine | Active |

| docs/review-actions/PLAN-CONVERGENCE-024-TRUST-SPINE-HARDENING-2026-04-01.md | CONVERGENCE-024 — Trust-spine hardening convergence fix | Active |

| docs/review-actions/PLAN-CON-027-THRESHOLD-POLICY-SEMANTICS-UNIFICATION-2026-04-01.md | CON-027 — Threshold & Policy Semantics Unification | Active |

| docs/review-actions/PLAN-MAP-003-MAP-004-MAP-DOC-2026-04-03.md | MAP-003/MAP-004/MAP-DOC — review-gated PQX + roadmap derivation + process-flow doc | Active |
| docs/review-actions/PLAN-RDX-006A-2026-04-03.md | RDX-006A (BATCH-M) — Multi-Batch Stop-Reason Taxonomy Alignment + Boundary-Audit Closure | Active |
| docs/review-actions/PLAN-BATCH-Z-2026-04-03.md | BATCH-Z — Final Consolidation and Cross-Layer Validation | Active |
| docs/review-actions/PLAN-BATCH-RM-2026-04-03.md | BATCH-RM — Remediation Automation Layer | Active |
| docs/review-actions/PLAN-BATCH-L-2026-04-03.md | BATCH-L — Failure Learning Loop | Active |
| docs/review-actions/PLAN-BATCH-U-2026-04-03.md | BATCH-U — Operator / Usability Layer | Active |
| docs/review-actions/PLAN-BATCH-AEX-HARDEN-01-2026-04-08.md | BATCH-AEX-HARDEN-01 — AEX/TLC/PQX enforcement hardening and drift tests | Active |
| docs/review-actions/PLAN-BATCH-E-RQX-B4-2026-04-08.md | BATCH-E RQX-B4 — Operator handoff disposition/control integration | Active |
