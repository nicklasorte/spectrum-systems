This file is subordinate to docs/roadmap/system_roadmap.md

# Roadmap Status

## Authority
Execution authority is delegated to `docs/roadmap/system_roadmap.md`. This file is reference context only.

## REFERENCE ROADMAPS
- docs/architecture/module-pivot-roadmap.md
- docs/100-step-roadmap.md
- docs/roadmaps/operational-ai-systems-roadmap.md
- docs/governance-enforcement-roadmap.md

## DEPRECATED ROADMAPS
- docs/roadmap.md

---

# Codex Prompt Roadmap — H through AJ

**Status:** Reference
**Date:** 2026-03-18
**Scope:** spectrum-systems — module-first platform, governance/foundations through final hardening
**Supersedes:** Level-16 Roadmap table in `docs/architecture/module-pivot-roadmap.md` (execution model only; strategic order is preserved)

---

## Purpose

This document expresses every active roadmap item as Codex-optimal prompt slices.

Each item is broken into three sub-slices:
- **A** = `PLAN` — write the execution plan before any code or doc change
- **B** = `BUILD` or `WIRE` — implement a single well-scoped transformation
- **C** = `VALIDATE` or `REVIEW` — run evidence collection, golden-path checks, and emit a result

One prompt = one primary transformation. Do not mix types.

### Prompt type legend
| Label | Type | Description |
| --- | --- | --- |
| A | PLAN | Write execution plan to `PLANS.md` or `docs/review-actions/` before BUILD/WIRE |
| B | BUILD | Implement one module, schema, or document change |
| B | WIRE | Connect two existing artifacts (contract pin, pipeline link, interface binding) |
| C | VALIDATE | Run tests, golden-path checks, emit evidence bundle |
| C | REVIEW | Prepare Claude review pack, collect findings, update action tracker |

### Checkpoint legend
Major checkpoints block advancement until Claude review findings are addressed or formally deferred.

```
★ = Major checkpoint — run checkpoint-packager + claude-review-prep
```

---

## H through L — Governance and Foundations

### H — Operating Model and Prompt Infrastructure

| Slice | Type | Objective |
| --- | --- | --- |
| H-A | PLAN | Plan the operating model update: root AGENTS.md, scoped AGENTS.md files, .codex/skills/, PLANS.md |
| H-B | BUILD | Create root AGENTS.md with prompt type system, rules, and navigation; create scoped AGENTS.md in modules/, contracts/, tests/, scripts/ |
| H-C | VALIDATE | Verify all AGENTS.md files are present and coherent; verify .codex/skills/ contains five valid SKILL.md files |

### I — Standards Manifest and Contract Catalog

| Slice | Type | Objective |
| --- | --- | --- |
| I-A | PLAN | Plan contracts to add or update; identify version bumps needed in standards-manifest.json |
| I-B | BUILD | Add or update JSON Schemas in contracts/schemas/; bump versions in standards-manifest.json |
| I-C | VALIDATE | Run `pytest tests/test_contracts.py`; run `contract-boundary-audit`; run `golden-path-check` for each changed contract |

### J — System Registry and Dependency Graph

| Slice | Type | Objective |
| --- | --- | --- |
| J-A | PLAN | Plan system registry updates: new modules, updated module paths, dependency graph refresh |
| J-B | BUILD | Update SYSTEMS.md and ecosystem/roadmap-tracker.json; run `python scripts/build_dependency_graph.py` |
| J-C | VALIDATE | Run `pytest tests/test_ecosystem_registry.py`; verify dependency graph is acyclic and complete |

### K — Control Loop Hardening (K2)

| Slice | Type | Objective |
| --- | --- | --- |
| K-A | PLAN | Plan control loop hardening: guardrails, golden paths, reconciliation loops, human checkpoints |
| K-B | BUILD | Implement control loop hardening in `control_plane/`; enforce lifecycle gates and guardrail rules |
| K-C | VALIDATE | Run `pytest tests/test_control_loop_hardening.py`; run `validate_module_architecture.py`; emit evidence bundle |

### L — Level Gate Enforcement ★

| Slice | Type | Objective |
| --- | --- | --- |
| L-A | PLAN | Plan lifecycle enforcer: maturity level gates, evidence requirements, promotion criteria |
| L-B | BUILD | Implement lifecycle enforcer in `control_plane/lifecycle/`; wire to evaluation harness |
| L-C | REVIEW | Run `pytest tests/test_lifecycle_enforcer.py`; run `checkpoint-packager checkpoint-L`; run `claude-review-prep checkpoint-L` |

**★ Checkpoint L:** Claude review — governance integrity. Are contracts, schemas, and lifecycle gates structurally sound? Advancement to M–P stage blocked until review clears.

---

## M through P+2 — Meeting Minutes and Slide Layer

### M — Meeting Intelligence Module

| Slice | Type | Objective |
| --- | --- | --- |
| M-A | PLAN | Plan meeting intelligence module: inputs (transcript), outputs (minutes record, signals, study state), contract pins |
| M-B | BUILD | Implement `workflow_modules/meeting_intelligence/` (or refine `spectrum_systems/modules/meeting_minutes_pipeline.py`); pin to `meeting_minutes_record` contract |
| M-C | VALIDATE | Run `pytest tests/test_meeting_minutes_contract.py`; run `golden-path-check meeting_minutes_record`; emit evidence bundle |

### N — Comment Resolution Module

| Slice | Type | Objective |
| --- | --- | --- |
| N-A | PLAN | Plan comment resolution module: inputs (reviewer_comment_set, working_paper), outputs (comment_resolution_matrix), contract pins |
| N-B | BUILD | Implement `workflow_modules/comment_resolution/`; pin to `comment_resolution_matrix` and `reviewer_comment_set` contracts |
| N-C | VALIDATE | Run `pytest tests/test_contract_enforcement.py -k comment`; run `golden-path-check comment_resolution_matrix`; emit evidence bundle |

### O — Working Paper Review Module

| Slice | Type | Objective |
| --- | --- | --- |
| O-A | PLAN | Plan working paper review module: inputs (working_paper_input), outputs (reviewer_comment_set), contract pins |
| O-B | BUILD | Implement `workflow_modules/working_paper_review/`; pin to `working_paper_input` and `reviewer_comment_set` contracts |
| O-C | VALIDATE | Run tests for working paper review; run `golden-path-check reviewer_comment_set`; emit evidence bundle |

### P — Comment Injection Module

| Slice | Type | Objective |
| --- | --- | --- |
| P-A | PLAN | Plan comment injection module: inputs (pdf_anchored_docx_comment_injection_contract), outputs (DOCX + audit), contract pins |
| P-B | BUILD | Implement `workflow_modules/comment_injection/`; pin to `pdf_anchored_docx_comment_injection_contract` |
| P-C | VALIDATE | Run tests for comment injection; run `golden-path-check pdf_anchored_docx_comment_injection_contract`; emit evidence bundle |

### P1 — Slide Intelligence Module

| Slice | Type | Objective |
| --- | --- | --- |
| P1-A | PLAN | Plan slide intelligence module: inputs (slide_deck), outputs (slide_intelligence_packet), gap detection integration |
| P1-B | BUILD | Refine `spectrum_systems/modules/slide_intelligence.py`; ensure gap detection delegates to `gap_detection.py`; pin to `slide_intelligence_packet` contract |
| P1-C | VALIDATE | Run `pytest tests/test_gap_detection.py`; run `golden-path-check slide_intelligence_packet`; emit evidence bundle |

### P2 — Workflow Module Evidence Bundles ★

| Slice | Type | Objective |
| --- | --- | --- |
| P2-A | PLAN | Plan evidence bundle format for workflow modules M–P1; define shared run_id convention |
| P2-B | WIRE | Wire artifact packager to emit evidence bundles (run manifest, validation, evaluation, provenance) for each workflow module |
| P2-C | REVIEW | Run `checkpoint-packager checkpoint-P`; run `claude-review-prep checkpoint-P` |

**★ Checkpoint P:** Claude review — workflow correctness. Do workflow modules produce and consume artifacts correctly end-to-end? Advancement to Q–R stage blocked until review clears.

---

## Q through R — Cross-Source Integration

### Q — Artifact Bus

| Slice | Type | Objective |
| --- | --- | --- |
| Q-A | PLAN | Plan artifact bus: routing rules, contract compatibility checks, cross-module artifact handoff protocol |
| Q-B | WIRE | Implement `orchestration/artifact_bus/`; wire workflow modules M–P to artifact bus; enforce contract compatibility before routing |
| Q-C | VALIDATE | Run pipeline integration tests; verify artifact bus rejects incompatible contract versions; emit evidence bundle |

### R — Lifecycle State Machine ★

| Slice | Type | Objective |
| --- | --- | --- |
| R-A | PLAN | Plan lifecycle state machine: states, transitions, forbidden paths, reconciliation loop |
| R-B | BUILD | Implement `orchestration/state_machine/`; wire to lifecycle enforcer (L); enforce forbidden transitions |
| R-C | REVIEW | Run `checkpoint-packager checkpoint-QR`; run `claude-review-prep checkpoint-QR` |

**★ Checkpoint Q+R:** Claude review — integration coherence. Does cross-source wiring respect contract boundaries? Does the state machine correctly sequence module outputs? Advancement to S–W stage blocked until review clears.

---

## S through W — Reasoning and Operator Outputs

### S — Study Planning Module

| Slice | Type | Objective |
| --- | --- | --- |
| S-A | PLAN | Plan study planning module: inputs (readiness assessment), outputs (study_readiness_assessment, milestone_plan), contract pins |
| S-B | BUILD | Implement `workflow_modules/study_planning/`; pin to `study_readiness_assessment` and `milestone_plan` contracts |
| S-C | VALIDATE | Run study planning tests; run `golden-path-check study_readiness_assessment`; emit evidence bundle |

### T — Agency Question Radar

| Slice | Type | Objective |
| --- | --- | --- |
| T-A | PLAN | Plan agency question radar: inputs (transcript, working paper), outputs (structured question set, next_best_action_memo) |
| T-B | BUILD | Implement `workflow_modules/agency_question_radar/`; pin to `next_best_action_memo` contract |
| T-C | VALIDATE | Run agency question radar tests; run `golden-path-check next_best_action_memo`; emit evidence bundle |

### U — Knowledge Capture Module

| Slice | Type | Objective |
| --- | --- | --- |
| U-A | PLAN | Plan knowledge capture: inputs (decision_log, assumption_register), outputs (knowledge_graph_edge), provenance chain |
| U-B | BUILD | Implement `domain_modules/knowledge_capture/`; pin to `decision_log`, `assumption_register`, `knowledge_graph_edge` contracts |
| U-C | VALIDATE | Run knowledge capture tests; run `golden-path-check knowledge_graph_edge`; emit evidence bundle |

### V — Allocation Intelligence Module

| Slice | Type | Objective |
| --- | --- | --- |
| V-A | PLAN | Plan allocation intelligence: inputs (band metadata, allocation tables), outputs (structured allocation artifact), domain data strategy |
| V-B | BUILD | Implement `domain_modules/allocation_intelligence/`; wire to shared provenance layer |
| V-C | VALIDATE | Run allocation intelligence tests; verify output is a structured artifact (not free-text); emit evidence bundle |

### W — Interference Assistant Module

| Slice | Type | Objective |
| --- | --- | --- |
| W-A | PLAN | Plan interference assistant: inputs (study inputs, methodology records), outputs (structured interference analysis artifact) |
| W-B | BUILD | Implement `domain_modules/interference_assistant/`; wire to provenance layer; pin to artifact_envelope |
| W-C | VALIDATE | Run interference assistant tests; verify structured output with provenance; emit evidence bundle |

---

## X through Z — Packaging, Checkpoints, and Extraction Discipline

### X — Observability Baseline

| Slice | Type | Objective |
| --- | --- | --- |
| X-A | PLAN | Plan shared observability platform: telemetry schema, SLO definitions, run evidence correlation |
| X-B | BUILD | Implement observability baseline in `control_plane/observability/`; emit structured telemetry per module run |
| X-C | VALIDATE | Run `pytest tests/test_observability.py`; verify telemetry keyed by run_id; emit evidence bundle |

### Y — SLO and Error Budget Gates

| Slice | Type | Objective |
| --- | --- | --- |
| Y-A | PLAN | Plan SLO definitions per module (M–W); define error budget thresholds and release gate rules |
| Y-B | WIRE | Wire SLO checks to CI release gates; implement error budget burn detection |
| Y-C | VALIDATE | Run SLO gate tests; verify release gate blocks on budget exhaustion; emit evidence bundle |

### Z — Extraction Discipline and Checkpoint Bundles ★

| Slice | Type | Objective |
| --- | --- | --- |
| Z-A | PLAN | Plan extraction discipline: define what constitutes a complete artifact extraction for each workflow module |
| Z-B | WIRE | Wire `checkpoint-packager` to CI for automated bundle generation at each stage boundary |
| Z-C | REVIEW | Run `checkpoint-packager checkpoint-XZ`; run `claude-review-prep checkpoint-XZ`; verify all prior checkpoint bundles are complete |

**★ Checkpoint X+Z:** Claude review — packaging discipline. Are checkpoint bundles complete? Are extraction artifacts traceable? Advancement to AA–AJ stage blocked until review clears.

---

## AA through AJ — Hardening and Final Proof

### AA — Cross-Repo Contract Validation

| Slice | Type | Objective |
| --- | --- | --- |
| AA-A | PLAN | Plan cross-repo contract validation gate: scanner scope, failure modes, CI integration |
| AA-B | WIRE | Wire `test_cross_repo_compliance_scanner.py` to CI gate; verify it blocks on schema drift |
| AA-C | VALIDATE | Run `pytest tests/test_cross_repo_compliance_scanner.py`; confirm gate fires on test drift scenario |

### AB — Governance Enforcement and Anomaly Detection ★

| Slice | Type | Objective |
| --- | --- | --- |
| AB-A | PLAN | Plan governance enforcement: auto-issue filing on violations, anomaly detection from telemetry |
| AB-B | BUILD | Implement governance enforcement automation (`control_plane/governance/`); wire to CI and observability |
| AB-C | REVIEW | Run `checkpoint-packager checkpoint-AB`; run `claude-review-prep checkpoint-AB` |

**★ Checkpoint AB:** Claude review — hardening progress. Are guardrails, SLOs, and reconciliation loops operational?

### AC — Incident and Postmortem Loop

| Slice | Type | Objective |
| --- | --- | --- |
| AC-A | PLAN | Plan incident response loop: runbook library, postmortem template, action tracking integration |
| AC-B | BUILD | Publish runbook library and postmortem template; wire incident signals to work-item creation |
| AC-C | VALIDATE | Verify runbooks cover all known failure modes for workflow modules M–W |

### AD — Artifact Signing and Supply-Chain Attestations

| Slice | Type | Objective |
| --- | --- | --- |
| AD-A | PLAN | Plan artifact signing: signing key management, SBOM generation, CI attestation workflow |
| AD-B | WIRE | Wire artifact signing to `artifact_packager.py`; add SBOM generation to CI |
| AD-C | VALIDATE | Verify signed artifacts carry valid signatures; verify SBOMs are emitted in CI |

### AE — Performance and Capacity Baseline

| Slice | Type | Objective |
| --- | --- | --- |
| AE-A | PLAN | Plan performance baseline: throughput targets, latency bounds, capacity test scenarios |
| AE-B | BUILD | Add performance test fixtures for workflow modules M–W; define regression thresholds |
| AE-C | VALIDATE | Run performance tests; verify no throughput regression against baseline |

### AF — Knowledge Graph and Institutional Memory

| Slice | Type | Objective |
| --- | --- | --- |
| AF-A | PLAN | Plan knowledge graph: node types (ADRs, decisions, runs, artifacts), edge types, query interface |
| AF-B | BUILD | Implement knowledge graph in `domain_modules/institutional_memory/`; wire to decision_log and assumption_register |
| AF-C | VALIDATE | Run knowledge graph tests; verify ADRs and decisions are queryable; emit evidence bundle |

### AG — External Audit Readiness Package

| Slice | Type | Objective |
| --- | --- | --- |
| AG-A | PLAN | Plan audit package: policies, evidence bundles, attestations, governance chain documentation |
| AG-B | BUILD | Assemble audit readiness package in `artifacts/audit/`; include all checkpoint bundles and governance declarations |
| AG-C | VALIDATE | Verify audit package is complete against Level-16 Definition of Done criteria |

### AH — Adaptive Orchestration and Policy Guardrails

| Slice | Type | Objective |
| --- | --- | --- |
| AH-A | PLAN | Plan adaptive orchestration: policy engine rules, rollback paths, approval gates for dynamic workflows |
| AH-B | BUILD | Implement policy guardrails in `orchestration/`; enforce approvals before any dynamic path divergence |
| AH-C | VALIDATE | Run orchestration policy tests; verify policy engine blocks unapproved paths |

### AI — Level-16 Evidence Package

| Slice | Type | Objective |
| --- | --- | --- |
| AI-A | PLAN | Plan Level-16 evidence compilation: map each Level-16 criterion to its evidence artifact |
| AI-B | BUILD | Compile Level-16 evidence package in `artifacts/level-16/`; link each criterion to proof |
| AI-C | VALIDATE | Verify all Level-16 criteria from `docs/architecture/module-pivot-roadmap.md` are satisfied; no partial credit |

### AJ — Final Proof and Institutionalization ★

| Slice | Type | Objective |
| --- | --- | --- |
| AJ-A | PLAN | Plan final proof: last gap analysis, strategic planning institutionalization, roadmap tracker update |
| AJ-B | BUILD | Update roadmap tracker, maturity tracker, and review registry with Level-16 completion evidence |
| AJ-C | REVIEW | Run `checkpoint-packager checkpoint-AJ`; run `claude-review-prep checkpoint-AJ`; submit for final Claude review |

**★ Checkpoint AJ:** Claude review — final proof. Does the system satisfy all Level-16 criteria? Is institutional memory active and queryable? Are all domain module outputs structured, traceable, and usable?

---

## Parallel execution rules

Safe to parallelize (distinct artifact types, no shared truth layers):
- **M + N + O** — workflow modules with independent contracts
- **S + T + U** — distinct domain areas at same level
- **V + W** — independent domain modules

Must be serialized (shared truth layers):
- Schema changes in `contracts/schemas/`
- `contracts/standards-manifest.json` updates
- Lifecycle state definition changes
- Review artifact structure changes

---

## Checkpoint summary

| Checkpoint | After | Stage focus |
| --- | --- | --- |
| ★ L | Governance/foundations | Contract integrity, lifecycle gates |
| ★ P | Workflow modules M–P1 | End-to-end workflow correctness |
| ★ Q+R | Cross-source integration | Artifact bus and state machine coherence |
| ★ X+Z | Packaging/checkpoints | Bundle completeness, extraction discipline |
| ★ AB | Hardening AA–AB | Guardrails, SLOs, reconciliation loops |
| ★ AJ | Final proof | Level-16 criteria, institutional memory |
