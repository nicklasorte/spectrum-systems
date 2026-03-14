# Systems Architecture Review: Spectrum Systems as Ecosystem Governance Layer

**Review Date:** 2026-03-14
**Repository:** `nicklasorte/spectrum-systems`
**Commit Reference:** `claude/review-governance-architecture-BrC9E` (post-PR-#56)
**Reviewer / Agent:** Claude (Reasoning Agent)
**Review Type:** Governance Layer Maturity Assessment — Follow-Up to 2026-03-14 Architecture Review
**Inputs Consulted:**
- `README.md`, `SYSTEMS.md`, `CONTRACTS.md`, `AGENTS.md`, `CLAUDE.md`, `CODEX.md`
- `contracts/standards-manifest.json`
- `docs/ecosystem-map.md`, `docs/contract-dependency-map.md`, `docs/artifact-flow.md`
- `docs/governance-enforcement-roadmap.md`, `docs/governance-conformance-checklist.md`
- `docs/implementation-boundary.md`, `docs/system-failure-modes.md`
- `docs/system-status-registry.md`, `docs/bottleneck-map.md`
- `docs/design-review-standard.md`, `docs/review-to-action-standard.md`
- `docs/review-registry.md`, `docs/review-actions/`
- `docs/reviews/2026-03-14-architecture-review.md` (prior review)
- All `systems/<system>/` doc sets (9 systems)
- All `workflows/*.md` (9 workflow specs)
- All `eval/` directories

**Scope:**
In-bounds: governance completeness, system design coverage, contract and schema ownership, artifact flow, orchestration responsibilities, cross-repo dependencies, governance enforcement readiness, architectural risks.
Out-of-bounds: implementation code quality in downstream repos, runtime performance, data security configuration.

---

## Executive Summary

`spectrum-systems` has made significant structural progress since the 2026-03-14 architecture review. The ecosystem map, contract dependency map, artifact flow documentation, governance enforcement roadmap, and all nine workflow specifications are now present. SYS-007 through SYS-009 have been modeled as systems with full five-document coverage. The governance layer is now architecturally coherent for the systems it defines.

However, five gaps prevent the repo from functioning as a fully stable constitutional layer:

1. **The governance process itself is not being executed.** The review registry is unpopulated and no action tracker exists for the prior review — the repo has the machinery but has not operated it.
2. **Three systems (SYS-007, SYS-008, SYS-009) are absent from the implementation boundary document** — their implementation repos have no formal declaration requirements derived from this repo.
3. **Failure mode coverage stops at SYS-006.** SYS-007 (working-paper-review-engine), SYS-008 (docx-comment-injection-engine), and SYS-009 (spectrum-pipeline-engine) are the most recently modeled systems and carry the highest cross-system failure propagation risk, yet none are in `docs/system-failure-modes.md`.
4. **The `external_artifact_manifest` contract is in `draft` status** while being consumed as a stable dependency by `spectrum-pipeline-engine` — a draft artifact in a stable contract chain creates governance inconsistency.
5. **Governance enforcement remains entirely manual.** The enforcement roadmap is well-structured, but Phase 1 (declared identity and contract pins) has not been initiated in any downstream repo.

The repo earns its constitutional role for the systems it has explicitly covered. The work ahead is closing the three second-order gaps in boundary declarations, failure mode coverage, and governance process execution — then beginning Phase 1 of the enforcement roadmap.

---

## Strengths

### S-1: Nine-System Ecosystem Is Now Fully Modeled
All nine systems (SYS-001 through SYS-009) have complete five-document governance coverage (`overview.md`, `interface.md`, `design.md`, `evaluation.md`, `prompts.md`) under `systems/<system>/`. The three systems that were absent from the prior review — `working-paper-review-engine` (SYS-007), `docx-comment-injection-engine` (SYS-008), and `spectrum-pipeline-engine` (SYS-009) — are now modeled. This closes the most critical structural gap identified in the prior review.

### S-2: All Nine Workflow Specifications Now Exist
`workflows/` now contains workflow specs for all nine systems including `workflows/meeting-minutes-engine.md` (the acknowledged gap from the prior review) and `workflows/spectrum-pipeline-engine.md`. Workflow specs are a prerequisite for lifecycle gate advancement; this completion unblocks implementation of the later-stage systems.

### S-3: Ecosystem Map Is Authoritative and Accurate
`docs/ecosystem-map.md` now provides a complete repo-level table mapping each repository to its role, system ID, produced/consumed contracts, upstream/downstream dependencies, and implementation status. The Mermaid diagram correctly shows the governance flow from `system-factory` through `spectrum-systems` to operational engines. This is the canonical navigation point for external engineers entering the ecosystem.

### S-4: Contract Dependency Map Makes Cross-Repo Obligations Explicit
`docs/contract-dependency-map.md` provides a producer-consumer table for all 16 contracts with explicit multi-system dependency callouts. The Mermaid flow diagram is accurate and matches `contracts/standards-manifest.json`. The note identifying the widest fan-out contracts (`comment_resolution_matrix_spreadsheet_contract`, `meeting_minutes`, `meeting_agenda_contract`, `pdf_anchored_docx_comment_injection_contract`, `external_artifact_manifest`, `reviewer_comment_set`) is operationally useful for risk-prioritized governance.

### S-5: Artifact Flow Is Documented with Storage Policy
`docs/artifact-flow.md` defines the full artifact pipeline from working paper through program advisory artifacts, with explicit producing system, consuming system, governing contract, and storage policy for each artifact type. The requirement that all artifacts live in approved external storage with `external_artifact_manifest` entries is formally stated. This closes the data boundary gap from the prior review.

### S-6: Governance Enforcement Roadmap Is Structured and Realistic
`docs/governance-enforcement-roadmap.md` defines a four-phase enforcement model (Phase 1: declared identity and contract pins → Phase 2: automated validation → Phase 3: CI-based conformance → Phase 4: ecosystem-level compatibility). Each phase defines its outputs, inputs, and tests. The `system-factory` path to automatic conformance through scaffolded governance primitives is the right architectural target. The roadmap is realistic and non-utopian.

### S-7: Schema Versioning Is Now Standardized Across the Ecosystem
`docs/schema-governance.md` and `CONTRACT_VERSIONING.md` are now aligned on `MAJOR.MINOR.PATCH` with consistent semver semantics. The manifest entries are semver-formatted, enabling downstream version pinning. The prior inconsistency in format across documents is resolved.

### S-8: Machine-Readable Contract Registry Is Comprehensive
`contracts/standards-manifest.json` registers 16 contracts with `schema_version`, `status`, `intended_consumers`, `introduced_in`, `last_updated_in`, `example_path`, and `notes`. The manifest is the single source of truth for contract pinning. The Python loader interface (`spectrum_systems.contracts.load_schema`, `validate_artifact`) provides a programmatic consumption path for downstream repos.

### S-9: Failure Mode Documentation Covers SYS-005 and SYS-006
The 2026-03-14 architecture review identified that SYS-005 and SYS-006 had no documented failure modes. Both are now covered in `docs/system-failure-modes.md` with specific failure patterns, detection strategies, and mitigations. The SYS-005 entry correctly identifies the complex failure propagation risk from its seven-input dependency structure.

### S-10: Governance Conformance Checklist Establishes Baseline
`docs/governance-conformance-checklist.md` provides a lightweight pre-release checklist for implementation repos covering identity, contract compliance, schema compliance, provenance, rules, and evaluation. This is the tangible enforcement artifact that makes governance obligations legible to implementation engineers.

---

## Structural Gaps

### G-1: Review Registry Is Unpopulated — Governance Process Is Not Executing (Critical)
`docs/review-registry.md` contains only the template placeholder row. No reviews have been registered, including the 2026-03-14 architecture review that directly preceded this review and generated all the Codex PRs (PR #47 through PR #56). The review-to-action standard (`docs/review-to-action-standard.md`) requires a registry entry and action tracker for every review; neither exists for the prior review. The governance process is documented but not being executed against its own outputs.

### G-2: No Action Tracker for Prior Review
`docs/review-actions/` contains only `README.md` and `action-tracker-template.md`. There is no action tracker derived from the 2026-03-14 architecture review despite that review generating 14 recommendations, 7 risk areas, and explicit action items. Without an action tracker, the prior review's open items (change-request process, deprecation policy, production code resolution, eval harness data) are tracked nowhere and will be rediscovered rather than closed.

### G-3: Implementation Boundary Stops at SYS-006 (High)
`docs/implementation-boundary.md` provides explicit system mappings (interface spec, schemas consumed, schemas produced, rule packs, evaluation harness location, required conformance declarations) for SYS-001 through SYS-006. SYS-007 (`working-paper-review-engine`), SYS-008 (`docx-comment-injection-engine`), and SYS-009 (`spectrum-pipeline-engine`) have no boundary mappings. These are the three most recently modeled systems and the ones with implementation repos listed as "Design drafted" — meaning implementation engineers may begin implementation without formal declaration requirements from the governance layer.

### G-4: System Failure Modes Stop at SYS-006 (High)
`docs/system-failure-modes.md` covers SYS-001 through SYS-006. SYS-007, SYS-008, and SYS-009 have no documented failure modes. SYS-009 (`spectrum-pipeline-engine`) is the highest-risk system for failure propagation — it orchestrates upstream artifacts across multiple engines, and its failure modes (version mismatch across consumers, sequencing errors, manifest emission failures) would propagate downstream to `spectrum-program-advisor` and governance boards. This is the highest-priority missing failure mode entry.

### G-5: `external_artifact_manifest` Is `draft` in a Stable Contract Chain (High)
In `contracts/standards-manifest.json`, `external_artifact_manifest` has `"status": "draft"` while all other contracts are `"status": "stable"`. However, `external_artifact_manifest` is listed as a required dependency for `spectrum-pipeline-engine` and `study-artifact-generator`, and `docs/artifact-flow.md` requires all artifacts to register in `external_artifact_manifest` with checksums and lineage links. A draft contract required by stable systems creates a governance inconsistency — downstream repos cannot pin a draft to a stable manifest entry, and system designs that depend on a draft artifact have no stability guarantee.

### G-6: No Change-Request or RFC Process Document (Medium)
`CONTRACT_VERSIONING.md` states that MAJOR changes require "coordinated updates to dependent schemas, prompts, workflows, and evaluators before adoption" but does not define how that coordination is initiated, reviewed, or completed. No `docs/change-request-process.md` or RFC template exists. When the first MAJOR schema change occurs, coordination will be informal and risk-prone. The nine systems now modeled make the impact surface of a MAJOR change significant.

### G-7: No Deprecation Timeline Policy (Medium)
`CONTRACT_VERSIONING.md` states deprecated fields stay documented "until the next MAJOR." There is no policy defining when fields are marked deprecated, how long the deprecated-but-present window lasts, or how consumers are notified. With all schemas at `1.0.x`, this has not yet mattered — but the ecosystem is approaching the scale where deprecation will occur.

### G-8: Production Python Runtime Remains in Design-First Repo (Medium)
`spectrum_systems/` is a Python package containing `study_runner/pipeline.py`, `study_runner/run_study.py`, `study_runner/artifact_writer.py`, `study_runner/load_config.py`, and a root-level `run_study.py`. `CLAUDE.md` explicitly states "This repository should NOT contain production implementation code." The prior review flagged this (Risk R-5). It remains unresolved. This creates a philosophy inconsistency visible to any downstream implementation engineer reading the repo.

### G-9: AGENTS.md Remains Thin (Low)
AGENTS.md was expanded by PR #52 but remains 35 lines with a 5-step development cycle (`Research → Plan → Implement → Test → Review`) that does not align with the 9-stage system lifecycle defined in `docs/system-lifecycle.md`. The `AGENTS.md` cycle skips the design, failure analysis, and evaluation plan stages. `CLAUDE.md` and `CODEX.md` are the substantive agent references; `AGENTS.md` adds minimal governance value in its current state and risks misleading agents that read it first.

### G-10: Eval Harnesses for SYS-005 Through SYS-009 Are Absent from `eval/` (Low)
`eval/` contains harness directories for SYS-001 through SYS-004 (`comment-resolution/`, `transcript-to-issue/`, `study-artifacts/`, `spectrum-study-compiler/`). SYS-005 through SYS-009 embed evaluation content inside `systems/<system>/evaluation.md` rather than `eval/`. The test matrix (`eval/test-matrix.md`) covers only SYS-001 through SYS-004. This creates inconsistency — systems designed later use a different evaluation artifact location pattern.

---

## Risk Areas

### R-1: Governance Process Integrity — The Meta-Governance Gap (High)
The governance layer has designed a complete review lifecycle: design-review-standard, review-to-action-standard, action tracker template, review registry, docs/reviews/ directory. None of these process elements are populated. A governance layer that does not execute its own governance processes is architecturally hollow at the process level, even if structurally sound at the schema level. When downstream repos ask "is this governance real?" the empty review registry is the visible answer.

**Severity:** High. The process documentation exists. The failure is execution.

### R-2: SYS-007/SYS-008/SYS-009 Implementation Boundary Gap Creates Governance Blind Spot (High)
The three most recently modeled systems are in "Design drafted" status. Their implementation repos will begin work against system designs and contract manifests, but without implementation boundary declarations they have no formal obligation to pin versions, declare `system_id`, or run evaluation harnesses. Schema drift in these systems propagates into the four systems they interact with: SYS-007 feeds SYS-001 and SYS-008; SYS-008 feeds SYS-009; SYS-009 feeds SYS-005. A drift failure in SYS-007 therefore cascades through four systems.

**Severity:** High. The cascade path is defined and unguarded.

### R-3: `spectrum-pipeline-engine` Bidirectional Dependency Creates Loop Risk (Medium)
The contract dependency map shows that `spectrum-pipeline-engine` (SYS-009) sends `meeting_agenda_contract` outputs to `meeting-minutes-engine` (SYS-006) and receives `meeting_minutes` back from SYS-006. This is a bidirectional dependency between two systems — not a directed acyclic graph. If both systems are operational simultaneously and SYS-006 output triggers a SYS-009 orchestration that produces an agenda that seeds another SYS-006 run, a cycle is possible without explicit termination conditions. Neither system's design documents model this loop explicitly.

**Severity:** Medium. The cycle is architectural, not yet operational.

### R-4: `external_artifact_manifest` Draft Status Undermines Data Boundary Governance (Medium)
The data boundary governance model (`docs/data-boundary-governance.md`) requires all artifacts to register in `external_artifact_manifest`. But the manifest contract itself is `draft`. If the schema changes before stabilization, existing manifest entries may become non-conformant, breaking provenance chains for all artifacts already registered. The fact that `artifact-flow.md` mandates `external_artifact_manifest` usage while the contract is unstable is a governance contradiction.

**Severity:** Medium. Immediately resolvable; high impact if left unresolved when implementation starts.

### R-5: Eval Harnesses Lack Labeled Test Fixtures for SYS-001 Through SYS-004 (Medium)
`eval/comment-resolution/`, `eval/transcript-to-issue/`, `eval/study-artifacts/`, `eval/spectrum-study-compiler/` are scaffold directories. `eval/comment-resolution/fixtures/fixtures.yaml` exists but is the only labeled fixture set. The evaluation harnesses are aspirational — the "blocking failures" defined in `eval/test-matrix.md` are not enforced by any test runner. This makes the evaluation-first governance principle non-executable.

**Severity:** Medium. Governance credibility depends on the ability to run tests.

### R-6: No Automated Enforcement Mechanism Despite Phase 1 Being Achievable (Medium)
The governance enforcement roadmap correctly identifies Phase 1 (declared identity and contract pins) as requiring no automation tooling — only repository metadata declarations. Yet no implementation repo has filed declarations against this repo's governance standards. Phase 1 is unblocked and unstarted. If no enforcement mechanism exists when first implementations reach pilot, conformance will rely entirely on checklist self-attestation.

**Severity:** Medium. Phase 1 does not require CI tooling; the blocking factor is process initiation, not technical complexity.

---

## Priority Action Items

### Action GA-001 — Register Prior Review and Create Its Action Tracker
**Priority:** Critical
**Description:** Register the `docs/reviews/2026-03-14-architecture-review.md` in `docs/review-registry.md`. Create an action tracker at `docs/review-actions/2026-03-14-architecture-actions.md` derived from that review's 14 recommendations. Mark items addressed by PRs #47–#56 as closed. Mark remaining open items (change-request process, deprecation policy, production code, eval harness data) as open. Register this review (`docs/reviews/2026-03-14-governance-architecture-review.md`) and its action tracker in the registry.
**Target Repository:** spectrum-systems
**Target Files:**
- `docs/review-registry.md` (add two rows)
- `docs/review-actions/2026-03-14-architecture-actions.md` (create from template)
- `docs/review-actions/2026-03-14-governance-architecture-actions.md` (create from template)

---

### Action GA-002 — Extend `docs/implementation-boundary.md` with SYS-007, SYS-008, SYS-009 Mappings
**Priority:** Critical
**Description:** Add explicit implementation boundary mappings for SYS-007 (`working-paper-review-engine`), SYS-008 (`docx-comment-injection-engine`), and SYS-009 (`spectrum-pipeline-engine`) following the same template as SYS-001 through SYS-006. Each mapping must specify: system ID, implementation repository name, interface spec location, canonical schemas consumed, canonical schemas produced, rule packs, evaluation harness location, and required conformance declarations.
**Target Repository:** spectrum-systems
**Target Files:**
- `docs/implementation-boundary.md` (add three system sections after SYS-006)

---

### Action GA-003 — Add SYS-007, SYS-008, SYS-009 to `docs/system-failure-modes.md`
**Priority:** Critical
**Description:** Add system-specific failure mode entries for SYS-007, SYS-008, and SYS-009. Key failure modes to document:
- SYS-007: PDF anchor extraction failure on non-standard layouts; reviewer ID normalization drift; working paper version mismatch
- SYS-008: Anchor verification failure causing injection to wrong DOCX location; audit report fields missing; comment_id uniqueness violations
- SYS-009: Contract version mismatch across upstream producers; orchestration loop with SYS-006 (bidirectional dependency); run manifest emission failure; missing upstream artifact causing partial bundle
**Target Repository:** spectrum-systems
**Target Files:**
- `docs/system-failure-modes.md` (add SYS-007, SYS-008, SYS-009 sections)

---

### Action GA-004 — Promote or Stabilize `external_artifact_manifest` Contract
**Priority:** High
**Description:** Either promote `external_artifact_manifest` to `stable` status in `contracts/standards-manifest.json` (after verifying the schema is ready for pinning) or document explicitly that systems depending on it must treat it as provisional and not pin until stabilized. Update `docs/artifact-flow.md` to reflect the current stability status where it mandates external manifest usage. Add a note to `CONTRACTS.md` explaining the promotion criteria for `external_artifact_manifest`.
**Target Repository:** spectrum-systems
**Target Files:**
- `contracts/standards-manifest.json` (update `external_artifact_manifest` status)
- `docs/artifact-flow.md` (add stability caveat if not yet promoted)
- `CONTRACTS.md` (add promotion note)

---

### Action GA-005 — Create `docs/change-request-process.md`
**Priority:** High
**Description:** Define the process for proposing contract and schema changes: who can propose, required RFC content (affected contracts, breaking/non-breaking classification, downstream repos affected, migration path), review period minimums (5 business days for MINOR, 10 for MAJOR), required document updates before merge (manifest, examples, changelog, system docs), and notification mechanism (GitHub issue label `contract-change` with affected consumer repos tagged). Include a short RFC template. This process is the missing enforcement complement to `CONTRACT_VERSIONING.md`.
**Target Repository:** spectrum-systems
**Target Files:**
- `docs/change-request-process.md` (create)
- `CONTRACT_VERSIONING.md` (add reference to the process doc)

---

### Action GA-006 — Model the SYS-009/SYS-006 Bidirectional Dependency
**Priority:** High
**Description:** Document the `spectrum-pipeline-engine` ↔ `meeting-minutes-engine` bidirectional dependency in both systems' interface documents and in `docs/artifact-flow.md`. Define the termination condition (e.g., `meeting_agenda_contract` outputs are consumed once per pipeline run; SYS-006 does not trigger SYS-009 re-runs automatically). Add a note in `docs/system-failure-modes.md` under SYS-009 describing the loop risk and its mitigation.
**Target Repository:** spectrum-systems
**Target Files:**
- `systems/spectrum-pipeline-engine/interface.md` (add cycle termination note)
- `systems/meeting-minutes-engine/interface.md` (add cycle termination note)
- `docs/artifact-flow.md` (add bidirectional note)
- `docs/system-failure-modes.md` (SYS-009 section)

---

### Action GA-007 — Initiate Phase 1 of Governance Enforcement Roadmap
**Priority:** High
**Description:** Initiate Phase 1 by creating a concrete governance conformance declaration template that implementation repos can complete. The template should be a machine-readable file (e.g., `.governance-declaration.json` or similar in YAML/JSON) covering: `system_id`, `contract_pins` (versions from standards manifest), `schema_pins`, `rule_version`, `evaluation_manifest_path`, `last_evaluation_date`, and `external_storage_policy`. Add this template to `contracts/` or `docs/` and update `docs/governance-conformance-checklist.md` to reference it. Document in `docs/governance-enforcement-roadmap.md` that Phase 1 has been initiated.
**Target Repository:** spectrum-systems
**Target Files:**
- `contracts/governance-declaration.template.json` (create)
- `docs/governance-conformance-checklist.md` (add reference and machine-readable requirement)
- `docs/governance-enforcement-roadmap.md` (mark Phase 1 initiated)

---

### Action GA-008 — Resolve Production Code in Design-First Repo
**Priority:** Medium
**Description:** Formally resolve the `spectrum_systems/` Python package presence. Preferred resolution: move `spectrum_systems/study_runner/` and `run_study.py` to the `spectrum-pipeline-engine` implementation repo and remove them from this repo. Alternative: add a formal `DECISIONS.md` entry and `README` notice declaring the package as a reference evaluation scaffold only, not for production use. In either case, update `docs/implementation-boundary.md` to state the resolution explicitly so downstream engineers receive clear guidance.
**Target Repository:** spectrum-systems (with possible move to spectrum-pipeline-engine)
**Target Files:**
- `DECISIONS.md` (document the resolution decision)
- `docs/implementation-boundary.md` (add note)
- `spectrum_systems/` (move or annotate as evaluation-only)

---

### Action GA-009 — Add `docs/deprecation-policy.md`
**Priority:** Medium
**Description:** Define the deprecation lifecycle for contract fields and schemas: deprecation marking criteria, minimum deprecated-but-present window (suggested: one MINOR version cycle), consumer notification process (GitHub issue + standards manifest `notes` field), removal procedure (MAJOR version), and the responsibility of `system-factory` to emit compatible scaffolds during transitions. Cross-reference from `CONTRACT_VERSIONING.md`.
**Target Repository:** spectrum-systems
**Target Files:**
- `docs/deprecation-policy.md` (create)
- `CONTRACT_VERSIONING.md` (add cross-reference)

---

### Action GA-010 — Expand or Consolidate `AGENTS.md`
**Priority:** Low
**Description:** Rewrite `AGENTS.md` to serve as the universal ecosystem agent entry point: include ecosystem context (all nine systems, repo roles, contract flows), link explicitly to `CLAUDE.md` and `CODEX.md`, align the development cycle with the 9-stage system lifecycle from `docs/system-lifecycle.md`, and add agent-specific guidance for the new systems (SYS-007 through SYS-009). Alternatively, consolidate `AGENTS.md` content into `CLAUDE.md` and redirect. Either path is acceptable; the current 35-line state adds minimal value.
**Target Repository:** spectrum-systems
**Target Files:**
- `AGENTS.md` (expand or consolidate)

---

### Action GA-011 — Add Eval Harness Directories for SYS-005 Through SYS-009
**Priority:** Low
**Description:** Create `eval/spectrum-program-advisor/`, `eval/meeting-minutes-engine/`, `eval/working-paper-review-engine/`, `eval/docx-comment-injection-engine/`, and `eval/spectrum-pipeline-engine/` with README files following the pattern of `eval/comment-resolution/README.md`. Add rows for SYS-005 through SYS-009 to `eval/test-matrix.md`. Keep `systems/<system>/evaluation.md` as the summary document linking to the eval harness directory. This makes the evaluation pattern consistent across all nine systems.
**Target Repository:** spectrum-systems
**Target Files:**
- `eval/spectrum-program-advisor/README.md` (create)
- `eval/meeting-minutes-engine/README.md` (create)
- `eval/working-paper-review-engine/README.md` (create)
- `eval/docx-comment-injection-engine/README.md` (create)
- `eval/spectrum-pipeline-engine/README.md` (create)
- `eval/test-matrix.md` (add SYS-005 through SYS-009 rows)

---

## Codex Implementation Prompts

---

### Codex Prompt for GA-001: Register Reviews and Create Action Trackers

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `docs/review-registry.md` — add two rows
- `docs/review-actions/2026-03-14-architecture-actions.md` — create from template
- `docs/review-actions/2026-03-14-governance-architecture-actions.md` — create from template

**Constraints:**
- Use the exact table structure from `docs/review-registry.md` (header columns: Review Date, Repo Reviewed, Reviewer/Agent, Review Scope, Review Artifact, Action Tracker, Status, Follow-up Due/Trigger)
- Use the exact tracker structure from `docs/review-actions/action-tracker-template.md` (Critical, High, Medium, Low, Blocking, Deferred sections)
- For the prior review tracker: mark as Closed all items addressed by PRs #47–#56 (ecosystem-map, contract-dependency-map, artifact-flow, governance-enforcement-roadmap, governance-conformance-checklist, implementation-boundary extensions SYS-002 through SYS-006, system-failure-modes SYS-005/SYS-006, meeting-minutes-engine workflow, schema versioning standardization, AGENTS.md expansion). Mark as Open: change-request process, deprecation policy, production code resolution, eval harness data, AGENTS.md substantive expansion.
- Do not modify `docs/design-review-standard.md` or `docs/review-to-action-standard.md`
- Do not create new schema files

**Expected output artifacts:**
- Two populated action trackers in `docs/review-actions/`
- `docs/review-registry.md` updated with two registered reviews, with links to artifacts and follow-up triggers

---

### Codex Prompt for GA-002: Extend Implementation Boundary for SYS-007, SYS-008, SYS-009

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `docs/implementation-boundary.md` — add three new system sections after the SYS-006 entry

**Constraints:**
- Use the exact same template as SYS-001 through SYS-006 sections (System ID, Implementation repository, Architecture source, Interface spec location, Canonical schemas consumed, Canonical schemas produced, Rule packs consumed, Evaluation harness location, Required conformance declarations)
- Derive schemas from `contracts/standards-manifest.json` — do not invent schema paths not present in the manifest or `schemas/`
- Implementation repository names: `working-paper-review-engine`, `docx-comment-injection-engine`, `spectrum-pipeline-engine`
- Rule packs: SYS-007 and SYS-008 consume none currently published; SYS-009 has no rule pack but pins prompt set in `systems/spectrum-pipeline-engine/prompts.md`
- Evaluation harness locations: reference `systems/<system>/evaluation.md` for SYS-007, SYS-008, SYS-009 (consistent with those systems' current patterns)
- Do not modify the existing SYS-001 through SYS-006 sections

**Expected output artifacts:**
- `docs/implementation-boundary.md` with three new system mapping sections covering SYS-007, SYS-008, SYS-009

---

### Codex Prompt for GA-003: Add SYS-007, SYS-008, SYS-009 Failure Modes

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `docs/system-failure-modes.md` — add system-specific entries for SYS-007, SYS-008, SYS-009 in the System-Specific Notes section

**Constraints:**
- Follow the existing format for SYS-001 through SYS-006 entries (system name, risks, detection, mitigation)
- For SYS-007 (`working-paper-review-engine`): include failures for PDF anchor extraction on non-standard layouts, reviewer ID normalization drift causing downstream matrix header mismatches, working paper version mismatch between PDF and DOCX
- For SYS-008 (`docx-comment-injection-engine`): include failures for anchor verification mismatch causing incorrect DOCX injection location, missing audit report fields, `comment_id`/`revision_id` uniqueness violations, DOCX source preservation failures
- For SYS-009 (`spectrum-pipeline-engine`): include failures for contract version mismatch across upstream producers, orchestration loop with SYS-006 (bidirectional dependency), run manifest emission failure, partial bundle assembly when upstream artifacts are missing
- Do not modify the cross-system failure modes section or existing SYS-001 through SYS-006 entries

**Expected output artifacts:**
- `docs/system-failure-modes.md` with three new system-specific sections appended to the System-Specific Notes block

---

### Codex Prompt for GA-004: Stabilize `external_artifact_manifest` Contract

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `contracts/standards-manifest.json` — update `external_artifact_manifest` status from `"draft"` to `"stable"`
- `docs/artifact-flow.md` — remove provisional caveats if any; confirm storage policy references are stable
- `CONTRACTS.md` — add a note to the `external_artifact_manifest` entry clarifying it is now stable and mandatory for boundary artifact registration

**Constraints:**
- Preserve all other fields in `contracts/standards-manifest.json` exactly as they are — only update the `status` field of the `external_artifact_manifest` entry
- Do not add new contracts or change schema versions of other contracts
- Do not modify `contracts/schemas/external_artifact_manifest.schema.json` or the example file
- If a stabilization rationale note is added to `CONTRACTS.md`, keep it under 3 sentences

**Expected output artifacts:**
- `contracts/standards-manifest.json` with `external_artifact_manifest` status changed to `"stable"`
- `CONTRACTS.md` with a brief stabilization note for `external_artifact_manifest`

---

### Codex Prompt for GA-005: Create Change-Request Process Document

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `docs/change-request-process.md` — create
- `CONTRACT_VERSIONING.md` — add one sentence cross-referencing `docs/change-request-process.md` in the section on MAJOR changes

**Constraints:**
- The change-request document must define: who can propose (any contributor), required RFC content (affected contracts, breaking/non-breaking classification per `CONTRACT_VERSIONING.md`, downstream repos affected, migration path), review periods (minimum 5 business days for MINOR, 10 for MAJOR), required pre-merge updates (manifest, examples, changelog, affected system docs in `systems/`), and notification mechanism (GitHub issue with label `contract-change`, affected `intended_consumers` from standards manifest tagged)
- Include a short RFC template section (can be a markdown checklist, not a full form)
- Do not contradict or duplicate `CONTRACT_VERSIONING.md` — reference it rather than restating semver rules
- Keep the document under 150 lines

**Expected output artifacts:**
- `docs/change-request-process.md` (new file, under 150 lines)
- `CONTRACT_VERSIONING.md` with one cross-reference sentence added

---

### Codex Prompt for GA-006: Document SYS-009/SYS-006 Bidirectional Dependency and Termination Condition

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `systems/spectrum-pipeline-engine/interface.md` — add a note on the bidirectional dependency with SYS-006 and the termination condition
- `systems/meeting-minutes-engine/interface.md` — add a mirror note
- `docs/artifact-flow.md` — add a note after the meeting minutes → program advisory artifacts pipeline explaining the agenda-generation feedback path and how it is bounded

**Constraints:**
- The termination condition to document: `meeting_agenda_contract` outputs produced by SYS-009 are consumed once per pipeline run; SYS-006 does not trigger SYS-009 re-runs automatically — agenda generation is a single-pass orchestration step, not a continuous feedback loop
- Do not change the interface document structures or remove existing content
- Do not add new contracts or modify `contracts/standards-manifest.json`
- The notes should be brief (3–5 sentences each) and placed in the existing "Dependencies" or "Interface" section of each system document

**Expected output artifacts:**
- `systems/spectrum-pipeline-engine/interface.md` with bidirectional dependency and termination condition note
- `systems/meeting-minutes-engine/interface.md` with mirror note
- `docs/artifact-flow.md` with agenda-generation feedback path note

---

### Codex Prompt for GA-007: Create Governance Declaration Template (Phase 1 Initiation)

**Repository:** `nicklasorte/spectrum-systems`

**Files to modify or create:**
- `contracts/governance-declaration.template.json` — create
- `docs/governance-conformance-checklist.md` — add reference to the template and machine-readable declaration requirement
- `docs/governance-enforcement-roadmap.md` — update Phase 1 description to note that the template exists and Phase 1 is initiated

**Constraints:**
- The template JSON must include: `system_id`, `implementation_repo`, `architecture_source` (always `"nicklasorte/spectrum-systems"`), `contract_pins` (object mapping `artifact_type` to `schema_version` from standards manifest), `schema_pins` (object mapping schema file to version), `rule_version` (string or null), `prompt_set_hash` (string or null), `evaluation_manifest_path` (string), `last_evaluation_date` (ISO 8601 date string), `external_storage_policy` (string), `governance_declaration_version` (string, `"1.0.0"`)
- Include a complete example entry for SYS-001 in the template (values filled, not placeholder strings)
- Do not include executable code in the template
- `docs/governance-conformance-checklist.md` must add exactly one new checklist item: "Machine-readable governance declaration file present and pinned to current standards manifest versions"

**Expected output artifacts:**
- `contracts/governance-declaration.template.json` with complete schema structure and SYS-001 example
- Updated `docs/governance-conformance-checklist.md`
- Updated `docs/governance-enforcement-roadmap.md` Phase 1 section

---

## Blocking Items

1. **GA-001 is a pre-condition for all future reviews.** The review registry must be populated before any additional architecture reviews are conducted, or the governance ledger becomes permanently unsynchronized. The review-to-action standard requires a registry entry and action tracker to declare a review complete; this review is not complete until GA-001 is executed.

2. **GA-005 (change-request process) should be resolved before any MINOR or MAJOR contract changes are made.** All 16 contracts are currently at `1.0.x`. The next update to any contract that changes semantics should go through a formal RFC, and the RFC process must exist before that update.

3. **`external_artifact_manifest` draft status (GA-004) should be resolved before any implementation repo begins production use of external storage.** If implementation begins while the manifest contract is draft, existing manifest entries may need retroactive migration when the schema stabilizes.

---

## Follow-Up Reviews

### Repository: `spectrum-pipeline-engine`
**Reason for review:** This is the highest cross-system risk system in the ecosystem. It orchestrates nine upstream contracts, has a bidirectional dependency with SYS-006, and is the gating system before `spectrum-program-advisor` receives advisory inputs. Its design was one of the most critical gaps in the prior review.
**Key architectural risks to examine:**
- Does the interface spec fully define the sequencing and failure handling for all nine consumed contracts?
- Is the SYS-006 bidirectional dependency modeled with explicit termination conditions in the implementation design?
- Are version-compatibility checks planned for incoming artifacts from different upstream engines?
- Does the run manifest design capture provenance across all upstream inputs?
**Suggested focus areas:** Interface completeness, failure mode coverage, version mismatch handling, run manifest schema, orchestration termination conditions.

---

### Repository: `working-paper-review-engine`
**Reason for review:** SYS-007 is the entry point for the entire artifact pipeline — it normalizes raw working papers into the canonical `reviewer_comment_set` and seeds the `comment_resolution_matrix_spreadsheet_contract`. Normalization failures here propagate through SYS-001, SYS-008, and SYS-009. The design was added in the post-prior-review Codex sprint but has not been reviewed.
**Key architectural risks to examine:**
- Are PDF anchor extraction rules consistent with the `pdf_anchored_docx_comment_injection_contract` requirements established in SYS-008?
- Does the reviewer ID normalization strategy produce stable IDs across comment cycles?
- Is the `working_paper_input` intake contract sufficient to handle the range of actual working paper formats?
**Suggested focus areas:** Anchor extraction design, ID normalization rules, intake contract coverage, handoff interface to SYS-001.

---

### Repository: `comment-resolution-engine`
**Reason for review:** SYS-001 is the most mature system (Design complete, evaluation scaffolding in place) and the one with the most governance coverage. However, its evaluation fixtures are minimal, and it is the adjudication step that determines what flows into SYS-008. A review would confirm evaluation harness readiness before this system reaches pilot.
**Key architectural risks to examine:**
- Are the evaluation fixtures in `eval/comment-resolution/` sufficient to block regressions?
- Is the disposition vocabulary in `rules/comment-resolution/` aligned with the `comment_resolution_matrix_spreadsheet_contract` column definitions?
- Does the system handle multi-agency comment submissions with overlapping section references?
**Suggested focus areas:** Evaluation fixture coverage, rule pack alignment with contract headers, multi-agency comment handling, provenance metadata completeness.

---

### Repository: `system-factory`
**Reason for review:** `system-factory` is the governance propagation mechanism — it scaffolds new implementation repos with contracts, governance files, and evaluation harnesses. A review of its behavior is the most direct way to assess whether governance is being inherited correctly by new repos.
**Key architectural risks to examine:**
- Does it emit the correct versions of `CLAUDE.md` and `CODEX.md` for new repos?
- Does it pull contract pins from the authoritative `contracts/standards-manifest.json`?
- Does it scaffold the machine-readable governance declaration file (once GA-007 is complete)?
- What happens when a new repo is scaffolded before Phase 1 declarations are defined?
**Suggested focus areas:** Scaffolding contract version fidelity, CLAUDE.md/CODEX.md template accuracy, governance declaration scaffold, lifecycle gate readiness.

---

*End of Review*
