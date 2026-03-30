# Spectrum Systems — System Roadmap

**Authority status:** ACTIVE ROADMAP AUTHORITY (Bundle B1, 2026-03-29)

## Intent
Consolidate roadmap execution authority into one repo-native document and provide an execution path that is explicitly grounded in (a) source design obligations and (b) current repository implementation evidence.

## System Goal
Operate Spectrum Systems as a governed, fail-closed, artifact-first execution surface that can run trusted PQX slices through eval → control → enforcement loops with replayable evidence and explicit certification boundaries.

## Architectural Invariants
- Schema-validated artifacts are required at all control boundaries. **[SOURCE + REPO]**
- Queue and runtime advancement must be driven by explicit decision artifacts, not prose interpretation. **[SOURCE + REPO]**
- Execution must halt on ambiguity, missing evidence, invalid contracts, or missing policy context. **[SOURCE + REPO]**
- Replayability and trace continuity are mandatory for trust claims. **[SOURCE + REPO]**
- Certification is a gate, not an annotation. **[SOURCE + REPO]**
- Missing raw source design PDFs are treated as a source-traceability constraint, not silently ignored. **[REPO + SOURCE GAP (FILLED)]**

## Execution Rules
- This file is the only active roadmap authority for implementation execution.
- `docs/roadmap/` and other roadmap-adjacent documents are subordinate or reference-only.
- Compatibility transition rule: `docs/roadmap/system_roadmap.md` is a required parseable operational mirror for legacy PQX consumers until migration is complete.
- Mirror contract rule: keep roadmap table header and operational rows parseable in the compatibility mirror; update both surfaces in lockstep during transition.
- PQX bridge rule (B2): PQX authority resolution must consume `docs/roadmaps/roadmap_authority.md`, then execute only the resolved machine roadmap (`docs/roadmap/system_roadmap.md` during transition). Ambiguous or inconsistent bridge metadata must fail closed.
- Status discipline is strict:
  - Done = implementation + tests + contracts + docs materially align.
  - Partial = real implementation exists but material gaps remain.
  - Present but fragmented = multiple seams exist with no dominant unified path.
  - Missing = materially absent.
  - Unclear = evidence insufficient.
- Do not infer multi-slice readiness from single-slice success.
- For claims where source materials are incomplete in-repo, mark **SOURCE GAP (FILLED)** explicitly.

## Source Inventory Used
| Source | Basis | Status |
| --- | --- | --- |
| Mapping Google SRE Reliability Principles to Spectrum Systems | SOURCE (structured extraction) | Available as structured artifact; raw source file missing in repo |
| Production-Ready Best Practices for Integrating AI Models into Automated Engineering Workflows | SOURCE (structured extraction) | Available as structured artifact; raw source file missing in repo |
| Spectrum Systems Build & Governance Engine (SBGE) Design | SOURCE (structured extraction) | Available as structured artifact; raw source file missing in repo |
| Agent + Eval Integration Design (Spectrum Systems) | SOURCE (structured extraction) | Available as structured artifact; raw source file missing in repo |
| Spectrum Systems AI Integration – Governed API Adapter Design | SOURCE (structured extraction) | Available as structured artifact; raw source file missing in repo |
| Spectrum Systems Done Certification Gate (GOV-10) Design | SOURCE (structured extraction) | Available as structured artifact; raw source file missing in repo |
| Repo implementation, tests, contracts, docs | REPO | Primary execution-state evidence surface |

## Current Repo State Summary
- Autonomous cycle loop now includes contract-first judgment policy/record/application/eval artifacts with deterministic precedent retrieval and fail-closed promotion gating. **[REPO]**
- Judgment learning control escalation now materializes deterministic downstream enforcement action/outcome/remediation artifacts with fail-closed progression blocking when required downstream artifacts are missing. **[REPO]**
- Repo has broad contract and module coverage for runtime, prompt queue, control, replay, observability, and certification seams. **[REPO]**
- PQX and queue capabilities exist across many modules and tests, but several behaviors remain distributed across parallel seams. **[REPO + INFERRED]**
- Roadmap authority signals are duplicated across `docs/roadmap/` and `docs/roadmaps/` trees and prior governance docs. **[REPO]**
- Source design extraction exists, but original raw source PDFs are missing; source-derived claims remain bounded by structured artifacts. **[REPO + SOURCE GAP (FILLED)]**

## System Decomposition
- Contract spine: `contracts/schemas/`, `contracts/standards-manifest.json`. **[REPO]**
- Runtime governance: `spectrum_systems/modules/runtime/`. **[REPO]**
- Prompt queue governance: `spectrum_systems/modules/prompt_queue/`. **[REPO]**
- Review and readiness evidence: `docs/reviews/`, `docs/review-actions/`. **[REPO]**
- Roadmap and execution control: `docs/roadmaps/`, subordinate `docs/roadmap/`. **[REPO + INFERRED]**

## Trust Boundaries
1. Contract validity boundary (schema conformance).
2. Context admission boundary (fail-closed).
3. Execution boundary (step result normalization).
4. Decision boundary (control/post-execution/transition policies).
5. Enforcement boundary (policy action materialization).
6. Replay boundary (resume + deterministic re-run).
7. Certification boundary (done/trusted gating).
8. Audit boundary (bundle completeness + lineage integrity).

## Control Loop Mapping
- Observe: admission, execution outputs, observability snapshots.
- Interpret: eval and review parsing artifacts.
- Decide: loop control, next-step, post-execution, policy decisions.
- Enforce: gating, retry/recovery branching, enforcement actions.
- Learn: replay, drift, policy backtesting, cross-run intelligence.

## Artifact Taxonomy
- Inputs: request/context/manifest/state artifacts.
- Execution: execution result, review invocation, parsing handoff/findings.
- Decisions: transition, loop control, gating, retry/recovery, next-step.
- Trust: replay records, certification records, integrity and consistency checks.
- Evidence: observability snapshots, audit bundles, trace + lineage attachments.

## Dependency Spine
1. Contract + schema authority
2. Context admission + adapter boundaries
3. Step execution + parsing normalization
4. Transition/control decision spine
5. Enforcement + gating
6. Replay/resume determinism
7. Certification + audit packaging
8. Multi-slice sequencing governance

## Roadmap Table

| Step ID | Step Name | What It Builds | Why It Matters | Source Basis | Repo Seams | Implementation Mode | Contracts | Artifacts | Integration | Control Loop | Dependencies | DoD | Prompt Class | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RM-01 | Roadmap authority consolidation | Single active roadmap authority with subordinate/reference designation | Removes competing execution signals | SOURCE + REPO | `docs/roadmaps/`, `docs/roadmap/`, `AGENTS.md`, `CODEX.md`, roadmap tests | MODIFY EXISTING | None | `roadmap_authority.md`, updated authority docs | Governance docs + tests | Decide/Enforce | None | One active authority file and no competing active claims | BUILD | Done |
| RM-02 | Execution-state inventory | Repo-native maturity inventory across PQX/governed layers | Prevents fake completeness and wrong execution claims | SOURCE + REPO + INFERRED | runtime + prompt_queue modules, tests, contracts, reviews | ADD NEW | None | `execution_state_inventory.md` | Contracts + runtime + reviews + PQX docs | Observe/Interpret/Decide/Learn | RM-01 | Layer statuses and blocking gaps documented with evidence discipline | BUILD | Done |
| PQX-BASE | Single trusted slice run path | Dominant one-slice governed path (admission→execution→decision→enforcement→certification) | Baseline for trusted execution | SOURCE + REPO | queue state machine, execution runner, transition policy, certification, audit | MODIFY EXISTING | Existing prompt queue/runtime schemas | sequence run + certification + audit artifacts | prompt queue + runtime + review seams | Full loop | RM-01, RM-02 | One path is executable with deterministic fail-closed handling and clear operator entrypoint | WIRE | Partial |
| PQX-SEQ-2 | Two-slice sequential governance | Reliable carry-forward state and bounded continuation for second slice | First real sequential trust threshold | SOURCE + REPO + SOURCE GAP (FILLED) | queue loop continuation, retry/reentry, sequence runner, replay resume | MODIFY EXISTING | existing queue sequence/replay schemas | sequential run records | queue + replay + control integration | Decide/Enforce/Learn | PQX-BASE | Second slice advancement is policy-gated, replayable, and non-ambiguous | WIRE | Partial |
| PQX-SEQ-3 | Three-slice sequential governance | Stable multi-hop sequencing with durable control visibility | Validates medium-chain reliability | SOURCE + INFERRED | queue observability, transition policies, certification integrity, review routing seams | MODIFY EXISTING | existing observability/certification/review schemas | sequence observability + certification evidence | PQX + review + cert | Full loop | PQX-SEQ-2 | Three ordered slices complete without manual override dependency | WIRE | Present but fragmented |
| PQX-SEQ-5-10 | 5–10 trusted sequential slice governance | Repeatable batch/sequence-run governance with bounded risk | Required for production-scale governed execution | SOURCE + INFERRED + SOURCE GAP (FILLED) | pqx sequence runner, policy backtesting, batch/routing seams | MODIFY EXISTING + ADD NEW | possibly additional sequence/batch governance contracts | durable sequence control artifacts | PQX + control + replay + certification + review routing | Full loop | PQX-SEQ-3 | 5–10 slice runs have explicit readiness gates, budget controls, and review/cert closure semantics | PLAN→BUILD→VALIDATE | Missing |

## Failure Modes Prevented
- Competing roadmap docs driving contradictory execution.
- Maturity inflation from isolated tests without integrated trust path evidence.
- Queue advancement without explicit decision artifacts.
- Certification claims without replay/cross-slice support.
- Multi-slice optimism that bypasses sequence governance gaps.

## Guarantees Provided
- One active roadmap authority location.
- Explicit classification discipline (SOURCE / REPO / INFERRED / SOURCE GAP (FILLED)).
- Repo-grounded readiness accounting for PQX sequential execution.
- Clear dependency ordering between authority consolidation, inventory, and sequential governance.

## Known Limits
- Source extraction artifacts are present, but raw source files are missing in-repo.
- Queue/review/replay/certification seams are broad but still distributed across many modules.
- Batch-level governance and long-horizon sequential readiness are not fully proven by current integrated evidence.

## Next Risks
- Authority drift reappears if status updates are written outside this file.
- Sequential readiness claims outpace deterministic replay/certification coupling.
- Review routing and repair reentry remain fragmented under scale.
- Policy/adapter/batch seams converge unevenly without focused follow-on bundle.

## Active Execution Order
1. RM-01 — maintain and enforce single authority.
2. RM-02 — keep execution-state inventory current after each bundle.
3. PQX-BASE — harden one dominant trusted slice path.
4. PQX-SEQ-2 — prove two-slice sequential reliability.
5. PQX-SEQ-3 — stabilize three-slice governance.
6. PQX-SEQ-5-10 — implement and validate batch-scale trusted sequencing.
