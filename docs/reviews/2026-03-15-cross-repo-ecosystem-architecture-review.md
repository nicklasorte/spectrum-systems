# Cross-Repo Systems Architecture Review: Czar Repo Org

**Date:** 2026-03-15
**Reviewer:** Claude (Principal Systems Architect — cross-repo ecosystem audit stance)
**Scope:** Full cross-repository architectural audit of the 8-repo distributed ecosystem
**Review Type:** Ecosystem architecture audit — layering, governance propagation, coupling, interface integrity, scaling readiness

Repositories under review:
- system-factory (Layer 1 — Factory)
- spectrum-systems (Layer 2 — Constitution)
- comment-resolution-engine (Layer 3 — Operational Engine)
- working-paper-review-engine (Layer 3 — Operational Engine)
- meeting-minutes-engine (Layer 3 — Operational Engine)
- docx-comment-injection-engine (Layer 3 — Operational Engine)
- spectrum-pipeline-engine (Layer 4 — Orchestration)
- spectrum-program-advisor (Layer 5 — Program Intelligence)

---

## Executive Summary

This ecosystem does not yet behave like a coherent platform. It behaves like a well-documented aspiration for one.

The constitutional layer (spectrum-systems) is impressively thorough in documentation: 16 JSON schemas, a machine-readable standards manifest with semantic versioning, a 5-layer architecture diagram, 9 system designs each with 5 standardized documents, a contract dependency map with Mermaid diagrams, a 4-phase governance enforcement roadmap, and a 9-stage system lifecycle model. The architectural vocabulary is mature. The intent is clear and defensible.

But the ecosystem has three structural failures that prevent it from functioning as a platform today:

1. **The constitution cannot govern itself.** Production Python code (`spectrum_systems/` — a full study runner pipeline) lives inside a repository whose foundational rule is "no production implementation code." The artifact boundary CI check does not detect it. This is a governance constitution that violates its own most fundamental rule with zero mechanical consequence.

2. **Governance propagation is entirely aspirational.** The 4-phase enforcement roadmap is a design document. No phase is active. No downstream engine is mechanically validated against any contract, schema version pin, or compliance checklist. Governance exists as documentation. It does not exist as enforcement.

3. **The ecosystem cannot enumerate itself.** The ecosystem registry (`ecosystem/ecosystem-registry.json`) lists 4 of 8 repos. The four primary operational engines — the repos that actually need governing — are absent. A constitution that cannot name the entities it governs cannot govern them.

Below these three critical findings: the layering model is sound but untested under real cross-repo data flow. Contract schemas are well-defined but have no consumer-side validation. The orchestration layer (spectrum-pipeline-engine) is in "planned" status despite being the most dependency-heavy component. The system-factory exists as a concept but its ability to propagate governance updates to existing repos is undefined.

**Overall assessment:** The ecosystem is at maturity level 2 (Structured). It has the documentation of a level 3 (Governed) system but none of the enforcement. Moving to level 3 requires closing the self-governance gap, completing the ecosystem registry, and activating at least Phase 1 of the enforcement roadmap.

---

## Ecosystem Strengths

### 1. Contract czar model is explicit and machine-operable
`contracts/standards-manifest.json` is a real machine-readable registry: 17 contracts with schema versions, stability status (`stable`/`draft`), intended consumer lists, example paths, and publication metadata. `CONTRACT_VERSIONING.md` defines semantic versioning rules (MAJOR for breaking, MINOR for additive, PATCH for documentation). `contracts/schemas/` holds 16 full JSON Schema Draft 2020-12 definitions. This is not aspirational governance — it is the infrastructure for real governance. The gap is in consumption enforcement, not in publication quality.

### 2. The 5-document system pattern provides universal governance surface area
Every system (all 9) has `overview.md`, `interface.md`, `design.md`, `evaluation.md`, and `prompts.md` under `systems/<system>/`. This enforced consistency means that any agent, engineer, or auditor can find the same categories of information for any system. Coverage is not partial. This is the correct design-first discipline.

### 3. Contract dependency map traces artifact flow across all systems
`docs/contract-dependency-map.md` maps every contract to its producer and consumer systems with a Mermaid diagram showing cross-engine data flow. Combined with `docs/artifact-flow.md`, the ecosystem has explicit, traceable artifact lineage from working paper intake through program advisory output. This is the kind of cross-repo visibility that most distributed systems lack entirely.

### 4. ADR-001 establishes the foundational architectural decision with rationale
The czar repo pattern, the three-tier separation (factory → constitution → engines), and the explicit rejection of alternatives (monorepo, per-system repos without control plane, document-only coordination) are formally recorded. The architectural intent is unambiguous.

### 5. System lifecycle gates create a defined maturation path
The 9-stage lifecycle (`docs/system-lifecycle.md`) from problem definition through operationalization, combined with the status registry (`docs/system-status-registry.md`) tracking all 9 systems, provides a clear framework for advancing systems toward production. Systems cannot skip stages. Exit criteria must be documented. This prevents premature implementation.

### 6. Governance compliance schema exists and is well-structured
`governance/repo-compliance.schema.json` defines a machine-readable compliance checklist with controls, statuses, and evidence fields. This is the schema that could power Phase 2/3 enforcement — if it were ever instantiated against actual engine repos.

### 7. Failure mode analysis covers cross-system patterns
`docs/system-failure-modes.md` identifies 6 cross-system failure modes (schema drift, missing provenance, revision mismatch, non-deterministic prompts, clustering errors, traceability loss) and provides system-specific failure patterns for SYS-001 through SYS-006. The detection and mitigation strategies are actionable.

### 8. Agent role separation reduces cross-cutting confusion
CLAUDE.md, CODEX.md, and AGENTS.md establish distinct roles: Claude for reasoning and design, Codex for repository modifications, Copilot for code implementation. Combined with design-review standards and action tracker templates, the ecosystem has a defined workflow for how different agents contribute to architectural evolution.

---

## Cross-Repo Structural Risks

### Risk 1 (Critical): Constitution violates its own foundational boundary rule

**Scope:** Ecosystem-wide credibility
**Files:** `spectrum_systems/`, `run_study.py`, `tests/test_contracts.py`, `requirements-dev.txt`

The `spectrum_systems/` Python package contains a full production study runner pipeline: `pipeline.py` (path loss calculations, interference modeling, protection zone computation), `artifact_writer.py`, `load_config.py`, and `run_study.py`. CLAUDE.md states: "This repository should NOT contain production implementation code."

The CI boundary check (`scripts/check_artifact_boundary.py`) bans `.pdf`, `.docx`, and binary extensions. It does not detect Python source files. The boundary rule is unenforced against the most obvious violation in the repo.

Worse: `tests/test_contracts.py` imports from `spectrum_systems.contracts`, coupling the test suite to the production code. Removing the package breaks CI. The constitution is structurally dependent on its own violation.

**Why this is ecosystem-critical:** Every downstream engine team that reads the constitution repo and sees a working Python pipeline will reasonably conclude that hosting implementation code in governance repos is acceptable. Governance that does not enforce its own rules cannot credibly enforce rules on others.

### Risk 2 (Critical): No cross-repo governance enforcement exists

**Scope:** All downstream repos
**Enforcement roadmap:** `docs/governance-enforcement-roadmap.md` — 4 phases, 0 active

Downstream engines can currently:
- Declare incompatible contract versions with no CI failure
- Redefine schemas locally, diverging from `contracts/schemas/`
- Skip system_id declarations entirely
- Ignore provenance requirements
- Omit CLAUDE.md/CODEX.md governance files

The `governance/repo-compliance.schema.json` exists but is never instantiated against any repo. The conformance checklist (`docs/governance-conformance-checklist.md`) is a manual checklist with no automation. The system-factory is described as the propagation path but has no documented mechanism for delivering enforcement primitives.

**Ecosystem impact:** The governance gap grows quadratically with ecosystem size. Each new engine added before Phase 1 enforcement is activated represents a permanently unverifiable governance claim.

### Risk 3 (Critical): Ecosystem registry is materially incomplete

**File:** `ecosystem/ecosystem-registry.json`

| Present | Missing |
|---------|---------|
| spectrum-systems | working-paper-review-engine |
| system-factory | comment-resolution-engine |
| spectrum-pipeline-engine | meeting-minutes-engine |
| spectrum-program-advisor | docx-comment-injection-engine |

The four missing repos are the primary Layer 3 consumers of the contract czar model — the very entities the constitution exists to govern. Without them in the registry, no ecosystem-level health check, compliance report, or automated propagation can enumerate the complete governance surface.

The registry also lacks `compliance_status`, `governance_version`, and `contract_pins` fields. It records existence but not governance state.

### Risk 4 (High): Dual-track schema registries create ambiguous authority

**Directories:** `schemas/` (10 files, kebab-case) vs. `contracts/schemas/` (16 files, snake_case)

The repo maintains two schema authorities with different naming conventions, different structural depth, and different governance coverage. `schemas/comment-schema.json` coexists with `contracts/schemas/comment_resolution_matrix.schema.json`. `schemas/provenance-schema.json` coexists with `contracts/schemas/provenance_record.schema.json`.

The `SYSTEMS.md` catalog for SYS-001 through SYS-004 references `schemas/` files. SYS-005 through SYS-009 reference `contracts/schemas/` files. This inconsistency means different systems within the same ecosystem point to different schema authorities.

No CI check validates that the two tracks are consistent. A downstream engine consuming `schemas/comment-schema.json` as its contract reference will drift from an engine consuming `contracts/schemas/comment_resolution_matrix.schema.json`. The dual-track model is a schema drift generator.

### Risk 5 (High): Review-to-action loop terminates at markdown

**Files:** `docs/review-actions/`, `docs/review-registry.md`

Architecture reviews produce action trackers (GA-001 through GA-011, CR-1 through LI-2, RC-1 through RE-8). These live as markdown files in `docs/review-actions/`. The `scripts/ingest-claude-review.js` ingestion exists but does not create GitHub issues. Action items accumulate in markdown. They are not assigned, not tracked, and have no completion signal.

The 2026-03-14 reviews produced 22+ action items. The 2026-03-15 constitution audit produced 15. Their completion status is unknown because there is no tracking mechanism beyond the documents themselves. Reviews generate documents. Documents do not generate tracked work. This is a governance feedback loop that is open on one end.

### Risk 6 (High): Orchestration layer (SYS-009) has the highest cross-repo coupling and the least governance maturity

`spectrum-pipeline-engine` depends on contracts from every other engine: `meeting_minutes`, `meeting_agenda_contract`, `comment_resolution_matrix_spreadsheet_contract`, readiness artifacts, `external_artifact_manifest`. It has "planned" status in the ecosystem registry and "design drafted" in the status registry.

When this system is implemented, it will be the first to discover contract incompatibilities across all upstream engines simultaneously. Its failure modes are inherently cross-system. Its governance coverage (no implementation boundary declaration, limited failure mode documentation) is the thinnest of any system at its dependency level.

### Risk 7 (Medium): No constitutional release versioning

Engine repos can pin to individual contract versions but cannot pin to a governance version that packages a consistent set of contracts, schemas, prompts, and standards together. When 3 contracts change between governance releases, engines face 3 separate migration decisions with no coordinated compatibility signal.

Without governance releases, the ecosystem cannot answer: "Is engine X compatible with the current constitution?" Only: "Is engine X compatible with contract Y version Z?" — repeated for every contract.

### Risk 8 (Medium): System-factory update propagation is undefined

System-factory is designed to scaffold new repos with governance primitives. The mechanism for propagating governance updates (new contract versions, updated prompts, schema changes) to **existing** repos is not documented or implemented. As the constitution evolves, existing engines will drift. The propagation model — push (factory generates PRs), pull (engine maintainers manually adopt), or notification (health check flags stale pins) — has not been decided.

### Risk 9 (Medium): Evaluation harness coverage is incomplete

`eval/test-matrix.md` covers SYS-001 through SYS-004 with structured evaluation fixtures. SYS-005 through SYS-009 have `evaluation.md` files in their `systems/` directories but no corresponding `eval/<system>/` directories with test cases, fixtures, or rubrics. Systems cannot be validated before implementation repos consume their contracts if there are no evaluation fixtures to validate against.

---

## Repo-by-Repo Assessment

### system-factory

**Role in ecosystem:** Layer 1 — scaffolds new repositories with governance defaults, contract pins, and starter manifests so downstream repos begin aligned to `spectrum-systems`.

**Role clarity:** Partially clear. The scaffolding purpose is well-stated in ADR-001 and `docs/ecosystem-architecture.md`. However, the distinction between "scaffolding new repos" and "propagating updates to existing repos" is not addressed. The repo's responsibilities stop at creation; the lifecycle responsibility gap is unacknowledged.

**Major strengths:**
- Clear architectural mandate as the generation layer
- Referenced as the consumer of `standards-manifest.json` in every contract entry (listed as `intended_consumers` for 10+ contracts)
- Positioned to deliver Phase 1 enforcement primitives (system_id declarations, contract pins, manifest templates)

**Major risks:**
- **Update propagation gap:** No mechanism for delivering governance updates to repos it previously scaffolded. Scaffolding is a point-in-time operation; governance is continuous. As contracts evolve, previously scaffolded repos have no defined update path.
- **Governance fidelity unknown:** Without access to the system-factory repo, it is impossible to verify that its templates actually reflect the current contract versions and governance standards in spectrum-systems. Template-to-constitution drift is a live risk.
- **Phase 1 dependency:** The enforcement roadmap identifies system-factory as the delivery mechanism for Phase 1 (declared identity and contract pins). This gives system-factory a critical path dependency that is not yet reflected in its implementation status.

**Architectural notes:** System-factory needs a dual mandate: (1) scaffold new repos correctly, (2) provide a mechanism for existing repos to detect when they have drifted from the current governance baseline. Without (2), the factory creates repos that are compliant at birth and increasingly non-compliant over time.

---

### spectrum-systems

**Role in ecosystem:** Layer 2 — Constitution. Defines governance rules, contracts, schemas, standards, review protocols, and architectural guidance for all downstream repositories.

**Role clarity:** Very clear. The czar model is explicit. CONTRACTS.md declares this repo as the authoritative source. ADR-001 records the decision. The ecosystem map positions it as the control plane.

**Major strengths:**
- 17 machine-readable contracts with JSON Schema definitions, versioning, and examples
- Standards manifest provides a single registry for all contract versions and consumers
- 9 systems fully documented with consistent 5-document structure
- Contract dependency map with Mermaid diagrams traces artifact flow
- Governance compliance schema (`repo-compliance.schema.json`) ready for instantiation
- Architecture Decision Record discipline established (though underused)
- Review infrastructure (design-review schema, ingest workflow, registry)

**Major risks:**
- **Self-governance violation (Critical):** Production Python code in `spectrum_systems/` directly contradicts the foundational boundary rule. CI does not catch it. Tests depend on it.
- **Dual-track schema ambiguity (High):** `schemas/` and `contracts/schemas/` directories with overlapping concerns and inconsistent naming conventions.
- **No enforcement of published standards (Critical):** All governance is documentary. The enforcement roadmap is Phase 0.
- **Review actions not tracked (High):** 37+ action items from three reviews sitting in markdown with no issue tracking.
- **Ecosystem registry incomplete (Critical):** 4 of 8 repos missing.

**Architectural notes:** This repo's documentation quality is its greatest asset and its greatest risk. The documentation is so thorough that it creates an illusion of governance. The gap between "standards published" and "standards enforced" is the single most important structural issue in the ecosystem. Every other risk is downstream of this one.

---

### comment-resolution-engine

**Role in ecosystem:** Layer 3 — Operational Engine (SYS-001). Adjudicates comments against working papers, updates resolution matrices with dispositions, and emits normalized outputs per the `comment_resolution_matrix_spreadsheet_contract`.

**Role clarity:** Clear. Well-defined interfaces, clear upstream (working-paper-review-engine) and downstream (docx-comment-injection-engine, spectrum-pipeline-engine) consumers. The most governance-mature of the operational engines.

**Major strengths:**
- Most detailed governance coverage: full implementation boundary declaration in `docs/implementation-boundary.md`
- Dedicated rule packs in `rules/comment-resolution/` with YAML validation rules, disposition rules, drafting rules, and canonical terms
- Evaluation harness scaffolded in `eval/comment-resolution/` with fixtures
- Contract schemas clearly identified for both consumption and production

**Major risks:**
- **No verification of governance compliance from this repo's side.** The constitution defines what the engine should do; there is no mechanism to verify that the actual implementation repo does it.
- **Rule pack consumption model untested.** The rules in `rules/comment-resolution/` are published but the mechanism for the engine repo to import and version-pin them is not specified.
- **Status "Design complete; evaluation scaffolding in place" but no evidence of implementation repo existing.** The governance side is ready; whether an implementation repo exists and conforms is invisible from here.

**Architectural notes:** SYS-001 is the template for how operational engine governance should work. If the ecosystem achieves Phase 1 enforcement, this system should be the pilot because its governance coverage is the most complete.

---

### working-paper-review-engine

**Role in ecosystem:** Layer 3 — Operational Engine (SYS-007). Normalizes working papers into `reviewer_comment_set` and seeds initial `comment_resolution_matrix_spreadsheet_contract` for downstream adjudication.

**Role clarity:** Clear. The intake role is well-defined: working papers enter the ecosystem through this engine. Clear downstream consumer (comment-resolution-engine).

**Major strengths:**
- Clear artifact pipeline position as the ecosystem entry point
- Produces two critical cross-engine contracts (`reviewer_comment_set`, `comment_resolution_matrix_spreadsheet_contract`)
- Interface specification defined in `systems/working-paper-review-engine/interface.md`

**Major risks:**
- **Missing from ecosystem registry** — governance state invisible at ecosystem level
- **No implementation boundary declaration** — SYS-007 is absent from `docs/implementation-boundary.md`
- **No dedicated evaluation harness** in `eval/` — only `systems/working-paper-review-engine/evaluation.md` (design-level, not fixture-level)
- **Schema references in SYSTEMS.md point to `contracts/examples/` rather than `contracts/schemas/`** — the catalog links to example payloads, not to the authoritative schema definitions. This is misleading for implementers.

**Architectural notes:** As the ecosystem entry point, this engine has outsized impact on data quality. Malformed outputs from SYS-007 cascade through the entire pipeline. Its governance coverage should be at the same level as SYS-001 (implementation boundary, dedicated eval harness, rule packs). Currently it is not.

---

### meeting-minutes-engine

**Role in ecosystem:** Layer 3 — Operational Engine (SYS-006). Converts meeting transcripts into contract-governed minutes conforming to `meeting_minutes_contract.yaml`.

**Role clarity:** Clear. Well-scoped to a single transformation: transcript → structured minutes. The contract is one of the most precisely defined in the ecosystem (JSON + DOCX + validation report with `additionalProperties: false`).

**Major strengths:**
- Contract precisely defined in YAML with strict schema enforcement
- Failure modes documented with transcript-specific risks (missing timestamps, template mismatch, malformed segments)
- Clear output contract consumed by spectrum-pipeline-engine and spectrum-program-advisor

**Major risks:**
- **Missing from ecosystem registry**
- **No implementation boundary declaration** for SYS-006 (though SYS-006 is partially covered in `docs/implementation-boundary.md` — it has a mapping but is less detailed than SYS-001–004)
- **Dual contract format risk:** The meeting minutes contract uses YAML (`contracts/meeting_minutes_contract.yaml`) while all other contracts use JSON Schema. This format inconsistency creates a different validation pathway.
- **Transcript intake contract is implicit.** The interface spec describes expected transcript format but there is no formal transcript schema. This makes the intake boundary fuzzy.

**Architectural notes:** The YAML vs. JSON Schema inconsistency for this contract is a minor governance risk. More significantly, the absence of a formal transcript input schema means the upstream boundary of this engine is governed by prose description rather than machine-readable contract. Every other engine in the ecosystem has JSON Schema contracts at both its input and output boundaries. SYS-006 has one at the output only.

---

### docx-comment-injection-engine

**Role in ecosystem:** Layer 3 — Operational Engine (SYS-008). Injects anchored comments from resolution matrices into DOCX documents, producing annotated output with audit manifests.

**Role clarity:** Clear. Well-scoped to a specific transformation: adjudicated matrices + PDF anchors → commented DOCX. The `pdf_anchored_docx_comment_injection_contract` is one of the most detailed contracts in the ecosystem.

**Major strengths:**
- Contract includes mandatory audit requirements (anchor verification, canonical column order, unique keys, source DOCX preservation)
- Clear fail-fast behavior on anchor mismatch or header drift
- Well-defined position between comment-resolution-engine (upstream) and spectrum-pipeline-engine (downstream)

**Major risks:**
- **Missing from ecosystem registry**
- **No implementation boundary declaration** — SYS-008 absent from `docs/implementation-boundary.md`
- **No dedicated evaluation harness** — relies on `systems/docx-comment-injection-engine/evaluation.md` (design-level only)
- **Binary artifact handling.** This engine produces DOCX files. The ecosystem's data boundary governance (`docs/data-boundary-governance.md`) and external artifact manifest are still `draft` status. The engine depends on a governance artifact that is not yet stable.

**Architectural notes:** SYS-008 is the most binary-artifact-heavy system in the ecosystem. Its dependency on the `external_artifact_manifest` contract (still in `draft` status) is a concrete risk. This engine cannot implement a compliant storage strategy until that contract is promoted to `stable`.

---

### spectrum-pipeline-engine

**Role in ecosystem:** Layer 4 — Orchestration. Sequences operational engines, aligns contract versions across a pipeline run, and emits pipeline run manifests and readiness bundles for the program advisor.

**Role clarity:** Clear in concept, underspecified in practice. The role is architecturally sound — orchestration is the correct placement for cross-engine sequencing. But the specifics of how orchestration works (API-based, file-based, event-driven) are not resolved.

**Major strengths:**
- Correct architectural placement as the layer between engines and program intelligence
- Contract consumption model well-documented: pinned versions of meeting_minutes, meeting_agenda_contract, comment_resolution_matrix_spreadsheet_contract, readiness artifacts, and external_artifact_manifest
- Meeting agenda contract (`meeting_agenda_contract`) positions the pipeline as a producer of downstream workflow seeds
- Run manifest requirements ensure provenance for every pipeline execution

**Major risks:**
- **Highest cross-repo coupling, thinnest governance coverage.** Depends on contracts from every other engine but has the least governance maturity of any Layer 3+ system.
- **"Planned" status in ecosystem registry** — lowest maturity of any registered repo
- **No implementation boundary declaration** — absent from `docs/implementation-boundary.md`
- **No failure mode documentation specific to orchestration** — `docs/system-failure-modes.md` does not cover SYS-009
- **Orchestration model undefined.** Is this synchronous? Asynchronous? File-based? API-based? Event-driven? The interface spec describes inputs and outputs but not the execution model. This is the single most important architectural decision for this repo and it has not been made (or recorded as an ADR).

**Architectural notes:** The pipeline engine is the most architecturally sensitive repo in the ecosystem. It is the first system that will attempt to compose contracts from multiple upstream engines into a single execution. Contract version incompatibilities that are invisible at the individual engine level will surface here. Its governance coverage needs to be elevated to at least the level of SYS-001 before implementation begins. The orchestration execution model needs an ADR.

---

### spectrum-program-advisor

**Role in ecosystem:** Layer 5 — Program Intelligence. Analyzes orchestrated artifacts (readiness bundles, decision logs, risk registers, milestone plans) and produces advisory outputs for program governance decisions.

**Role clarity:** Partially clear. The role as a downstream intelligence consumer is well-defined. The boundary between "advisory output" and "decision support tool" is less clear. With 7 output contracts (program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan), this repo has the largest output surface of any system.

**Major strengths:**
- Clear upstream dependency: consumes readiness bundles from spectrum-pipeline-engine
- Output contracts are the most detailed in the ecosystem — 7 schemas covering decisions, risks, assumptions, milestones, and recommendations
- Failure modes documented with specific patterns: stale inputs, dependency graph inconsistencies, field normalization divergence, contract version mismatches
- Example implementation repo structure provided in `examples/spectrum-program-advisor/` with CLAUDE.md, CODEX.md, src/, tests/

**Major risks:**
- **Scope creep risk.** 7 output contracts is a large surface for a single repo. The boundary between "advisor outputs" and "program management system" is not explicitly drawn. Without explicit scope constraints, this repo is at risk of absorbing responsibilities that belong in a dedicated program management tool.
- **"Experimental" status in ecosystem registry** — reflects genuine uncertainty about the repo's scope and readiness
- **Heavy upstream dependency.** Requires readiness bundles from spectrum-pipeline-engine, which is itself in "planned" status. SYS-005 cannot be meaningfully tested until SYS-009 produces real outputs.
- **Advisory outputs may need feedback loops.** Decisions, risks, and milestones change over time. The current model treats the advisor as a terminal consumer. If advisory outputs need to flow back into the pipeline (e.g., a risk assessment triggers re-sequencing), the ecosystem architecture lacks a feedback path.

**Architectural notes:** The example implementation structure in `examples/spectrum-program-advisor/` is a valuable pattern but it needs to be promoted into system-factory as the canonical scaffold. The 7-contract output surface should be reviewed for consolidation — some of these contracts (decision_log, risk_register, assumption_register, milestone_plan) may be better modeled as components of a single `program_state` aggregate rather than independent artifacts.

---

## Layer Integrity Assessment

### Layer 1 — Factory (system-factory)

**Integrity:** Partially real. The scaffolding concept is clear and referenced throughout the ecosystem. system-factory is listed as an intended consumer of 10+ contracts in the standards manifest. However:
- Its actual implementation fidelity is unverifiable from this repo
- The update propagation mechanism for existing repos is completely undefined
- It is positioned as the delivery vehicle for Phase 1 enforcement but has no documented enforcement capabilities

**Sustainability:** At risk if the ecosystem grows beyond 4-5 engines without a defined update propagation model. Scaffolding-only creates compliant-at-birth repos that drift over time.

### Layer 2 — Constitution (spectrum-systems)

**Integrity:** Structurally real, operationally aspirational. The contract schemas, standards manifest, system designs, and governance documentation are genuinely thorough. The gap is between publication and enforcement. This layer publishes governance but does not enforce it.

**Sustainability:** Sustainable as a documentation layer. Unsustainable as a governance layer without enforcement mechanisms. The dual-track schema issue and the production code violation need immediate resolution to maintain credibility.

### Layer 3 — Operational Engines (comment-resolution, working-paper-review, meeting-minutes, docx-comment-injection)

**Integrity:** Partially real. System designs exist for all four engines with consistent document structures. Interface contracts are defined. But:
- None of the four engines appear in the ecosystem registry
- Governance coverage is uneven: SYS-001 has full implementation boundary declarations; SYS-007, SYS-008 have none
- Whether the actual engine repos exist and conform to their governance specifications is invisible from the constitution

**Sustainability:** The 5-document pattern is sustainable. The uneven governance coverage is not. As engines move to implementation, the ones with thin governance coverage (SYS-007, SYS-008) will be the first to drift from the constitutional model.

### Layer 4 — Orchestration (spectrum-pipeline-engine)

**Integrity:** Aspirational. The role is architecturally correct. The contract consumption model is documented. But the execution model is undefined, the governance coverage is thin, and the system is in "planned" status. This layer exists as a well-positioned placeholder.

**Sustainability:** This is the layer most likely to break the ecosystem. Orchestration is where cross-engine contract incompatibilities first become visible. Without the orchestration execution model defined, implementation teams will make ad hoc decisions that bake in coupling. This layer needs an ADR before implementation begins.

### Layer 5 — Program Intelligence (spectrum-program-advisor)

**Integrity:** Partially real. The role is clear and the output contracts are detailed. The "experimental" status is honest. The 7-contract output surface is ambitious.

**Sustainability:** At risk of scope creep. The boundary between "advisory outputs" and "program management system" needs explicit documentation. The dependency on Layer 4 (which is itself "planned") means this layer cannot be validated end-to-end.

---

## Required Ecosystem Changes

These are structural changes needed before the ecosystem adds further engines or moves existing engines to implementation.

### REC-1: Remove production implementation code from the constitution repo
**Priority:** Critical — must be first
**Target repo:** spectrum-systems
**Action:** Relocate `spectrum_systems/study_runner/` to a dedicated engine repo. Evaluate whether `spectrum_systems/contracts/__init__.py` belongs in a narrow published SDK or can be replaced with direct JSON schema loading. Refactor `tests/test_contracts.py` to not import from a production package. Remove `run_study.py`.
**Rationale:** A constitution that violates its own foundational rule is not credible as a governing authority. This must be resolved before any downstream enforcement is attempted.

### REC-2: Complete the ecosystem registry
**Priority:** Critical
**Target repo:** spectrum-systems
**Action:** Add working-paper-review-engine, comment-resolution-engine, meeting-minutes-engine, and docx-comment-injection-engine to `ecosystem/ecosystem-registry.json`. Add `compliance_status`, `governance_version`, and `contract_pins` fields per entry. Add a CI check that validates registry completeness.
**Rationale:** Ecosystem-level governance, health checks, and automation require a complete enumeration of governed entities.

### REC-3: Extend artifact boundary CI to enforce architecture boundary
**Priority:** Critical
**Target repo:** spectrum-systems
**Action:** Extend `scripts/check_artifact_boundary.py` to detect Python packages with business logic, runnable pipeline scripts, and `src/` directories. Define an allowlist for governance utilities (e.g., `scripts/`).
**Rationale:** The boundary check must enforce the same rule the documentation states. A data-only boundary check is necessary but insufficient.

### REC-4: Activate Phase 1 governance enforcement
**Priority:** High
**Target repos:** spectrum-systems, system-factory
**Action:** Define a `system-manifest.json` schema requiring `system_id`, `contract_pins`, and `governance_version`. Wire system-factory to generate this file for new repos. Add a CI step validating that ecosystem registry entries have conforming manifests.
**Rationale:** Phase 1 is the foundation for all subsequent enforcement phases. Without declared identity and contract pins, no downstream validation is possible.

### REC-5: Complete SYS-007/008/009 governance coverage
**Priority:** High
**Target repo:** spectrum-systems
**Action:** Add implementation boundary declarations for SYS-007, SYS-008, SYS-009. Complete failure mode documentation. Validate interface spec depth.
**Rationale:** These systems are next in line for implementation. Governance gaps at implementation time become permanent architectural debt.

### REC-6: Resolve external_artifact_manifest draft status
**Priority:** High
**Target repo:** spectrum-systems
**Action:** Promote to `stable` or explicitly block consumers from depending on it. The current state — `draft` in the manifest, consumed as stable in the dependency map — is a contradiction.
**Rationale:** SYS-008 (docx-comment-injection-engine) depends on this contract for storage governance. Implementation against a draft contract is implementation against an unstable interface.

### REC-7: Wire review-to-issue automation
**Priority:** High
**Target repo:** spectrum-systems
**Action:** Create or extend a script that reads action tracker files (markdown or JSON) and creates GitHub issues. Wire to CI.
**Rationale:** 37+ action items from three reviews sitting in markdown with no issue tracking. The governance feedback loop is open.

### REC-8: Define the orchestration execution model via ADR
**Priority:** High
**Target repo:** spectrum-systems (ADR), spectrum-pipeline-engine (implementation)
**Action:** Record an ADR defining whether the orchestration layer is synchronous/asynchronous, file-based/API-based, event-driven/polling, and how it handles partial pipeline failures.
**Rationale:** The most architecturally sensitive repo in the ecosystem has an undefined execution model. Implementation without this ADR will bake in ad hoc coupling decisions.

---

## Recommended Ecosystem Enhancements

### ENH-1: Resolve dual-track schema ambiguity
**Target:** spectrum-systems
**Action:** Document explicit ownership rules for `schemas/` vs. `contracts/schemas/`. Add CI to validate no contradictions between tracks. Migrate SYSTEMS.md references to use `contracts/schemas/` consistently.

### ENH-2: Create machine-readable contract consumer registry
**Target:** spectrum-systems
**Action:** Build a `consumer-registry.json` mapping each engine to its pinned contract versions. This enables automated impact analysis when contracts evolve.

### ENH-3: Implement constitutional release versioning
**Target:** spectrum-systems
**Action:** Tag governance releases (`governance-v1.0.0`) packaging a consistent set of contracts, schemas, and standards. Maintain a governance changelog. Engine repos pin to governance releases, not individual contracts.

### ENH-4: Extend evaluation harness coverage to all 9 systems
**Target:** spectrum-systems
**Action:** Create `eval/<system>/` directories with test cases, fixtures, and rubrics for SYS-005 through SYS-009. Prioritize SYS-009 (pipeline engine) due to its cross-cutting dependencies.

### ENH-5: Create ADRs for decisions made since ADR-001
**Target:** spectrum-systems
**Action:** Record ADRs for: dual-track schema model, evaluation coverage boundary, agent role separation, enforcement roadmap phasing, orchestration execution model. Establish policy that interface-affecting decisions require ADRs.

### ENH-6: Formalize system-factory update propagation
**Target:** spectrum-systems (documentation), system-factory (implementation)
**Action:** Define and document whether governance updates to existing repos use a push model (factory generates PRs), pull model (engine maintainers adopt), or notification model (health check flags stale pins).

### ENH-7: Implement ecosystem health signal
**Target:** spectrum-systems
**Action:** Create a CI job generating `ecosystem-health.json` aggregating registry completeness, per-repo compliance status, open action items, and evaluation coverage. This is the minimum viable observability primitive.

### ENH-8: Add schema backward-compatibility CI tests
**Target:** spectrum-systems
**Action:** On contract schema changes, validate that examples valid under the old schema remain valid under the new schema. This mechanically enforces the backward compatibility promise in CONTRACT_VERSIONING.md.

### ENH-9: Consolidate spectrum-program-advisor output surface
**Target:** spectrum-systems
**Action:** Evaluate whether the 7 output contracts (decision_log, risk_register, assumption_register, milestone_plan, program_brief, study_readiness_assessment, next_best_action_memo) should be modeled as components of a single `program_state` aggregate. Document the decision as an ADR.

---

## Future Evolution Risks

### Contract drift across engines
As engines implement against contracts, they will discover ambiguities and add local fields. Without Phase 2/3 enforcement, local extensions become de facto standards. By the time drift is detected, migration cost is prohibitive. **This is the most probable failure mode.**

### Dual-standard emergence
Each engine that cannot easily parse governance standards will create local copies. The `docs/` directory of each engine will accumulate documents contradicting `spectrum-systems` standards. This has already happened once (the Python package). Without enforcement, it will happen in every dimension.

### Governance bypass normalization
If engineers observe that no compliance check catches violations, bypass becomes the path of least resistance. The visible production code in `spectrum_systems/` demonstrates that violations have no consequence. This is a cultural risk that begins with a technical failure.

### Review artifact accumulation without tracked work
If the 37+ action items from three reviews remain in markdown without becoming GitHub issues, the review process will be perceived as generating documentation rather than driving change. Engineers will disengage from reviews.

### Orchestration becoming a coupling amplifier
Without a defined execution model, spectrum-pipeline-engine implementation will make ad hoc integration decisions that create hidden coupling between engines. The orchestration layer — designed to isolate engines from each other — will become the thing that binds them together most tightly.

### Program advisor absorbing unbounded scope
With 7 output contracts and no explicit scope boundary, spectrum-program-advisor risks becoming the catch-all for "anything related to program management." Each new stakeholder request that doesn't fit elsewhere will be routed here. Without scope constraints, it becomes the ecosystem's junk drawer.

### ADR vacuum creating revisitation cycles
Without ADRs for major decisions, the same architectural questions will resurface as the team grows. "Why two schema directories?" will be debated repeatedly. The cost of undocumented decisions compounds with team size.

---

## Ecosystem Maturity Assessment

**Rating: 2 — Structured**

| Dimension | Rating | Rationale |
|-----------|--------|-----------|
| Architecture clarity | 3 | Layer model clear; ADR-001 explicit; ecosystem maps complete |
| Interface contracts | 2.5 | Machine-readable manifest exists; 17 schemas defined; consumer registry absent; dual-track ambiguity |
| Governance model | 1.5 | Roadmap documented; zero phases active; constitution violates own boundary |
| Ecosystem cohesion | 2 | Contracts well-defined; 4 engines unregistered; propagation path undeclared |
| Cross-repo enforcement | 1 | No mechanical enforcement exists anywhere in the ecosystem |
| Failure mode analysis | 2 | SYS-001–006 covered; SYS-007–009 gaps; no cross-repo failure detection |
| Automation readiness | 1.5 | Boundary CI for binaries exists; no contract compliance automation |
| Evolution strategy | 2 | Lifecycle gates defined; no release versioning; no update propagation |
| Observability | 1 | No ecosystem health signal; review registry is markdown; no dashboard |
| Human factors | 2 | Agent guidance clear; production code violation unpunished by CI |
| ADR discipline | 1 | One ADR; subsequent decisions untracked |

**Composite: 2 (Structured)**

The ecosystem has the documentation density and architectural vocabulary of a level 3 system. It lacks the enforcement, registry completeness, and feedback loops that distinguish "governed" from "structured." The gap is not in thinking — the thinking is excellent. The gap is in execution.

Level 3 (Governed) requires at minimum:
1. No self-governance violations
2. Complete ecosystem registry with compliance state
3. Phase 1 enforcement active (declared identity and contract pins)
4. Closed review-to-issue feedback loop
5. No governance coverage gaps for systems approaching implementation

None of these conditions are met today.

---

## Next-Step Architecture Moves

To move from level 2 (Structured) to level 3 (Governed):

**Move 1: Close the self-governance gap (REC-1 + REC-3)**
Remove `spectrum_systems/` production code. Extend boundary CI. This is a credibility prerequisite.

**Move 2: Complete the ecosystem registry (REC-2)**
Add all four missing engines. Add compliance status and governance version fields. This makes ecosystem-level automation possible.

**Move 3: Activate Phase 1 enforcement (REC-4)**
Define `system-manifest.json` schema. Wire system-factory scaffolding. Add CI validation. This is the foundation for Phases 2–4.

**Move 4: Close the review-to-issue loop (REC-7)**
Even a simple script that creates GitHub issues from action tracker files. The loop must be mechanical.

**Move 5: Resolve governance gaps for approaching implementation (REC-5 + REC-6)**
Complete SYS-007/008/009 governance coverage. Stabilize `external_artifact_manifest`. These are pre-flight checks.

**Move 6: Define orchestration execution model (REC-8)**
Record an ADR. The pipeline engine is the most architecturally sensitive repo and its execution model is undefined.

These six moves, executed in order, bring the ecosystem to the minimum viable governed state. Everything after that — consumer registries, release versioning, health dashboards, backward-compatibility tests — is enhancement on a solid foundation.

---

## Machine-Operable Follow-Up Artifact

See paired file: `docs/review-actions/2026-03-15-ecosystem-architecture-audit-actions.json`
