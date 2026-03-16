# Architecture Review: Operational AI Systems Roadmap

## Review Metadata

- **Review Date:** 2026-03-16
- **Repository:** spectrum-systems
- **Document Reviewed:** `docs/roadmaps/operational-ai-systems-roadmap.md`
- **Reviewer:** Claude (Principal Systems Architect — Opus 4.6)
- **Review Type:** Systems architecture review of strategic roadmap
- **Inputs Consulted:**
  - `docs/roadmaps/operational-ai-systems-roadmap.md`
  - `docs/systems-registry.md`
  - `docs/ecosystem-map.md`
  - `docs/bottleneck-map.md`
  - `docs/data-lake-strategy.md`
  - `docs/data-provenance-standard.md`
  - `docs/artifact-flow.md`
  - `docs/100-step-roadmap.md`
  - `docs/implementation-boundary.md`
  - `docs/system-failure-modes.md`
  - `docs/design-review-standard.md`
  - `docs/review-to-action-standard.md`
  - `CLAUDE.md`, `CODEX.md`
  - Prior review artifacts in `docs/reviews/` and `docs/review-actions/`

## Scope

**In-bounds:** Architectural coherence and feasibility of the operational AI systems roadmap; alignment with the existing ecosystem architecture (system-factory, spectrum-systems, operational engines, spectrum-pipeline-engine, spectrum-program-advisor); layering integrity; data architecture risks; governance implications; build sequencing; repo boundary implications; long-term feasibility of the Spectrum Intelligence Map.

**Out-of-bounds:** Code review (no production code exists); individual engine design evaluation (separate reviews exist); evaluation harness design; prompt engineering; deployment infrastructure.

---

## A. Executive Summary

The Operational AI Systems Roadmap is a well-structured, ambitious document that describes a coherent three-layer architecture for building governed AI systems in the spectrum domain. Key findings:

- **Coherent vision.** The roadmap articulates a clear progression from narrow operational engines through study-scale integration to ecosystem-scale intelligence. The layering is logical and the dependency relationships are generally sound.
- **Compatible with ecosystem architecture.** The roadmap reinforces the existing czar repo org structure and does not conflict with established governance patterns. It correctly positions spectrum-systems as the governance layer and describes appropriate repo boundaries.
- **Significant gap between current state and roadmap scope.** The systems registry currently tracks 9 systems (SYS-001 through SYS-009). The roadmap describes 15 systems, 6 of which have no registry entry, no schema, no contract, and no bottleneck mapping. This gap is the primary architectural risk.
- **Missing enabling infrastructure.** The roadmap underestimates the infrastructure required beneath its Layer 2 and Layer 3 systems — specifically canonical identifier systems, ontology infrastructure, artifact storage, and cross-engine validation. These are not optional add-ons; they are prerequisites.
- **Build sequencing has flaws.** The dependency ladder places the Spectrum Study Operating System at position 14 (second to last), but it is architecturally the connective tissue that Layer 2 systems depend on. The Knowledge Capture Engine is positioned too late relative to its consumers.
- **Governance implications are substantial.** Implementing this roadmap will require spectrum-systems to define new artifact contracts, canonical identifiers, ontology schemas, and cross-engine interface standards that do not yet exist.
- **The apex system is feasible but distant.** The Spectrum Intelligence Map is technically feasible as a long-term goal, but realistic delivery depends on institutional adoption, sustained data accumulation, and stable Layer 1/Layer 2 outputs — conditions that will take years to establish.

---

## B. Architectural Fit

### Reinforcements

The roadmap reinforces the existing ecosystem architecture in several important ways:

1. **Governance centralization.** The roadmap explicitly states that all engines should conform to standards in spectrum-systems and that contracts should be defined before automation. This aligns perfectly with the czar repo model.

2. **Composability principle.** The roadmap's requirement that "outputs of one engine should be usable as inputs to another without manual transformation" directly supports the artifact flow architecture already defined in `docs/artifact-flow.md`.

3. **system-factory alignment.** The roadmap states new repos should be created from system-factory and declare artifact contracts at creation time. This matches the existing scaffolding model.

4. **spectrum-pipeline-engine role.** The roadmap correctly describes the pipeline engine as an orchestrator that "does not implement engine logic directly," consistent with `docs/ecosystem-map.md`.

5. **spectrum-program-advisor role.** The roadmap positions the advisor as "a consumer of the ecosystem, not a producer of governance standards," which matches the existing design.

### Conflicts and Tensions

1. **Registry gap.** The systems registry defines SYS-001 through SYS-009. The roadmap introduces 6 new systems (Band Study Plan Generator, Agency Question Radar, Interference Analysis Assistant, Working Paper Stress Test, Allocation Intelligence Engine, Knowledge Capture Engine) that have no system IDs, no registry entries, and no schema definitions. This creates a governance gap: the roadmap describes systems outside the governance framework that the roadmap itself advocates.

2. **Naming inconsistency.** The roadmap uses different names for systems that map to existing registry entries:
   - "Meeting Intelligence System" (roadmap) vs. "Meeting Minutes Engine" (SYS-006)
   - "Spectrum Study Program Advisor" (roadmap) vs. "Spectrum Program Advisor" (SYS-005)
   - "Comment Resolution Engine" is consistent, but "Working Paper Stress Test" (roadmap) overlaps with "Working Paper Review Engine" (SYS-007) without a clear boundary

3. **Layer 2 systems vs. existing architecture.** The five Layer 2 systems (Spectrum Study Operating System, Institutional Memory Engine, Regulatory Impact Simulator, Review Prediction Engine, Spectrum Study Autopilot) introduce an architectural tier that sits between spectrum-pipeline-engine and spectrum-program-advisor. The current ecosystem map shows a linear flow from engines → pipeline → advisor. The roadmap implies a more complex graph topology that the current pipeline engine is not designed to orchestrate.

4. **Bottleneck traceability.** The bottleneck map defines BN-001 through BN-006. The six new Layer 1 systems in the roadmap do not have bottleneck IDs. This breaks the design principle that every system should trace to a specific bottleneck.

---

## C. Layering Integrity

### Layer 1 — Operational Engines

**Assessment: Well-defined with some boundary issues.**

The nine Layer 1 systems are clearly scoped as narrow artifact transformers. Each has defined inputs, outputs, and a clear value proposition. However:

- **Working Paper Stress Test vs. Review Prediction Engine.** The Stress Test (Layer 1) "predicts weaknesses, missing evidence, and likely reviewer objections." The Review Prediction Engine (Layer 2) "predicts likely reviewer objections and agency concerns." These systems overlap significantly. The distinction appears to be that the Stress Test operates on a single paper while the Review Prediction Engine uses historical data — but this boundary is not explicitly drawn in the roadmap.

- **Knowledge Capture Engine placement.** The Knowledge Capture Engine is described as capturing "decisions, assumptions, rationale, and supporting evidence from meetings and study artifacts." This is fundamentally a cross-cutting infrastructure concern, not a narrow artifact transformer. It consumes outputs from multiple engines and produces a knowledge base. Its architectural role is closer to Layer 2 than Layer 1. Placing it in Layer 1 underestimates its complexity and cross-engine dependencies.

- **Spectrum Study Program Advisor layer ambiguity.** The roadmap places this in Layer 1, but the systems registry already treats SYS-005 as a program-level intelligence system distinct from operational engines. The roadmap's own description ("program-level status aggregator and risk surface") makes it sound like a Layer 2 system. The existing ecosystem map places it at the end of the data flow, consuming pipeline outputs — again, more consistent with Layer 2.

### Layer 2 — Study-Scale Intelligence Systems

**Assessment: Architecturally sound concept, but boundaries need tightening.**

The Layer 2 concept of combining Layer 1 outputs into study-lifecycle intelligence is the right abstraction. However:

- **Spectrum Study Operating System is infrastructure, not intelligence.** The description — "links assumptions, modeling outputs, working papers, comments, and decisions into a governed study lifecycle" — describes integration infrastructure (a study artifact graph with dependency tracking). This is enabling infrastructure that Layer 2 intelligence systems depend on, not itself an intelligence system. It should either be a separate infrastructure concern or be explicitly positioned as the foundation that other Layer 2 systems build on.

- **Spectrum Study Autopilot vs. Spectrum Study Program Advisor.** The Autopilot "monitors study progress and recommends next actions, sequencing changes, and risk mitigations." The Program Advisor "monitors study progress, open risks, artifact maturity, and coordination gaps." These are nearly identical in function. The Autopilot consumes Advisor outputs, which suggests it is a thin wrapper. Either merge them or draw a much sharper boundary.

- **Institutional Memory Engine vs. Knowledge Capture Engine.** The Knowledge Capture Engine (Layer 1) "captures decisions, assumptions, rationale" and outputs feed the Institutional Memory Engine (Layer 2) which "stores persistent records of decisions, rationale, evidence." The distinction between "capture" and "store" is architecturally thin. In practice, these are likely a single system with ingestion and query interfaces.

### Layer 3 — Ecosystem-Scale Intelligence Layer

**Assessment: Conceptually well-motivated, but underspecified as architecture.**

The Spectrum Intelligence Map is described as five integrated layers (Allocation/Regulatory, Real-World System, Physics/Propagation, Policy/Constraint, Decision/Scenario). This is a compelling vision, but:

- The five "layers" within the Intelligence Map are really five data domains, not architectural layers. Calling them layers within a layer creates confusion.
- There is no discussion of how these data domains would be represented, stored, queried, or kept consistent. The document describes what the system would answer, not how it would be built.
- The dependency section is accurate (it depends on stable Layer 1/2 outputs), but there is no discussion of the data integration architecture needed to unify five fundamentally different data types (regulatory text, engineering parameters, propagation models, policy constraints, decision records).

### Recommended Refinements

1. Move Knowledge Capture Engine and Spectrum Study Program Advisor to Layer 2.
2. Merge or sharply distinguish Working Paper Stress Test (Layer 1) and Review Prediction Engine (Layer 2).
3. Merge or sharply distinguish Knowledge Capture Engine and Institutional Memory Engine.
4. Merge or sharply distinguish Spectrum Study Autopilot and Spectrum Study Program Advisor.
5. Reclassify Spectrum Study Operating System as integration infrastructure, not an intelligence system.
6. Rename the five "layers" within the Spectrum Intelligence Map to "domains" or "facets" to avoid confusion with the three system layers.

---

## D. Missing Systems

### Critical Missing Infrastructure

1. **Canonical ID Registry / Service.**
   Every engine in this ecosystem produces artifacts with IDs — comment IDs, transcript IDs, assumption IDs, study artifact IDs, run IDs. The provenance standard defines `record_id` as a required field. But there is no system or standard for how IDs are generated, scoped, or resolved across engines. Without a canonical ID system, cross-engine traceability breaks down as soon as two engines independently assign IDs to the same artifact.

2. **Schema and Contract Governance Engine.**
   The roadmap assumes contracts exist and are versioned. The 100-step roadmap includes "contract compatibility matrix" (step 20) and "cross-repo contract validation gate" (step 49). But there is no system described for managing schema evolution, deprecation, consumer notification, or backward compatibility across 15+ engines. As the ecosystem grows, schema governance will become a bottleneck itself.

3. **Ontology / Taxonomy Service.**
   The data lake strategy (Tier 4, Class 16) describes "taxonomy and ontology tables" as long-game infrastructure. But the Agency Question Radar needs to cluster questions by topic, the Allocation Intelligence Engine needs to reason about service definitions and footnote relationships, and the Spectrum Intelligence Map needs a unified conceptual vocabulary. Ontology is not a Tier 4 luxury; it is Tier 2 enabling infrastructure.

4. **Artifact Store / Data Lake Infrastructure.**
   The data lake strategy defines 18 data classes across 4 tiers. Multiple engines are described as producing artifacts that "feed" other engines. But there is no system for artifact storage, retrieval, versioning, or lifecycle management. The `external_artifact_manifest` contract exists but is described as needing stabilization (GA-004 in prior reviews). Without a governed artifact store, each engine will implement its own storage, creating fragmentation.

5. **Artifact Validation Service.**
   The roadmap requires that "every engine should produce a structured provenance record with each output artifact." The 100-step roadmap includes evaluation harnesses per engine. But there is no cross-engine artifact validation service that can verify an artifact conforms to its declared contract, has valid provenance, and has not been tampered with. This is essential before Layer 2 systems consume outputs from multiple Layer 1 engines.

### Important Missing Infrastructure

6. **Simulation Infrastructure.**
   The Regulatory Impact Simulator (Layer 2) and the Spectrum Intelligence Map (Layer 3) both depend on simulation capabilities. The Interference Analysis Assistant (Layer 1) consumes simulation outputs. But there is no description of the simulation infrastructure itself — how simulations are defined, parameterized, executed, tracked, and validated. This is a significant dependency that is treated as external to the roadmap.

7. **Observability and Audit System.**
   The 100-step roadmap includes observability steps (26, 36, 44, 54, 57, 81). But the operational AI systems roadmap does not mention observability at all. For a governed ecosystem producing policy-relevant artifacts, a unified observability and audit system is not optional infrastructure — it is a first-class system.

8. **Cross-Engine Event Bus / Notification System.**
   The current architecture assumes linear artifact flow (engine A produces, engine B consumes). The roadmap's Layer 2 systems require event-driven coordination: when a comment matrix is updated, the Institutional Memory Engine should be notified; when a study plan changes, the Spectrum Study Operating System should re-evaluate dependencies. No event architecture is described.

---

## E. Repo Boundary Implications

Based on the roadmap, the following repositories will likely need to exist. For each, I assess the role, standalone justification, key contracts, and ecosystem interactions.

### Repositories That Should Exist as Standalone Repos

**1. `band-study-plan-engine`**
- **Role:** Generate structured study plans from band inputs and prior patterns.
- **Standalone justification:** Clear single-purpose engine with defined inputs/outputs. Follows the operational engine pattern.
- **Contracts consumed:** Band input schema, study template schema (both from spectrum-systems).
- **Contracts exposed:** `study_plan` artifact contract.
- **Interactions:** Outputs consumed by spectrum-study-operating-system and spectrum-program-advisor.

**2. `agency-question-radar`**
- **Role:** Extract, cluster, and track recurring agency questions from transcripts and comment matrices.
- **Standalone justification:** Clear single-purpose engine. Produces a unique artifact type (clustered question register) not produced elsewhere.
- **Contracts consumed:** `meeting_minutes_contract`, `comment_resolution_matrix_spreadsheet_contract`.
- **Contracts exposed:** `question_register` artifact contract.
- **Interactions:** Outputs feed working-paper-stress-test and review-prediction-engine.

**3. `interference-analysis-assistant`**
- **Role:** Convert simulation/MATLAB outputs into structured engineering summaries and policy-ready language.
- **Standalone justification:** Bridges technical analysis and regulatory documentation. Unique transformation not covered by other engines.
- **Contracts consumed:** Simulation output schema, scenario definition schema.
- **Contracts exposed:** `interference_analysis_summary` artifact contract.
- **Interactions:** Outputs feed working-paper-stress-test and spectrum-intelligence-map.

**4. `working-paper-stress-test`**
- **Role:** Pre-review analysis of working paper drafts to predict weaknesses and reviewer objections.
- **Standalone justification:** Distinct from working-paper-review-engine (SYS-007), which normalizes reviewer feedback into structured comments. The stress test operates before review; SYS-007 operates during/after review. *However, the boundary must be explicitly documented in both repos.*
- **Contracts consumed:** `working_paper_input`, `question_register`, `interference_analysis_summary`.
- **Contracts exposed:** `stress_test_report` artifact contract.
- **Interactions:** Outputs inform working paper revision before submission to SYS-007.

**5. `allocation-intelligence-engine`**
- **Role:** Analyze allocation tables, service definitions, and footnotes; detect conflicts in candidate allocation changes.
- **Standalone justification:** Unique analytical capability not covered by other engines. Requires specialized regulatory data ingestion.
- **Contracts consumed:** Allocation table schema, footnote schema (both new, to be defined in spectrum-systems).
- **Contracts exposed:** `allocation_analysis` artifact contract, `conflict_detection_report`.
- **Interactions:** Outputs feed regulatory-impact-simulator and spectrum-intelligence-map.

**6. `knowledge-capture-engine`**
- **Role:** Extract decisions, assumptions, and rationale from meeting and artifact outputs into persistent institutional memory records.
- **Standalone justification:** Justified if the engine is genuinely a narrow extractor. If it also manages storage and query, it should merge with institutional-memory-engine.
- **Contracts consumed:** Decision log entries, assumption records, meeting minutes, artifact metadata.
- **Contracts exposed:** `knowledge_record` artifact contract.
- **Interactions:** Outputs feed institutional-memory-engine.

### Repositories That May Need to Exist (Layer 2 / Infrastructure)

**7. `spectrum-study-operating-system`**
- **Role:** Integration layer linking study artifacts into a governed lifecycle graph.
- **Standalone justification:** Yes, but this is fundamentally integration infrastructure, not a narrow engine. It will be one of the most complex repos in the ecosystem. It should be built incrementally, starting as a study artifact registry with dependency tracking.
- **Contracts consumed:** All Layer 1 artifact contracts.
- **Contracts exposed:** `study_lifecycle_status`, `artifact_dependency_graph`, `compliance_report`.
- **Interactions:** Central integration point for Layer 2 systems. spectrum-pipeline-engine routes artifacts to it; spectrum-study-autopilot and spectrum-program-advisor consume its outputs.

**8. `institutional-memory-engine`**
- **Role:** Persistent, queryable store of institutional decisions, rationale, and evidence.
- **Standalone justification:** Yes, but consider merging with knowledge-capture-engine. If separated, the memory engine is the storage/query layer and the capture engine is the ingestion layer.
- **Contracts consumed:** `knowledge_record`, decision logs, provenance records.
- **Contracts exposed:** Knowledge query API, cross-study pattern reports.
- **Interactions:** Critical dependency for review-prediction-engine and spectrum-intelligence-map.

**9. `regulatory-impact-simulator`**
- **Role:** Simulate effects of proposed regulatory/allocation changes.
- **Standalone justification:** Yes. This is a specialized analytical system with unique computational requirements (simulation execution, scenario comparison).
- **Contracts consumed:** `allocation_analysis`, allocation tables, engineering analysis artifacts.
- **Contracts exposed:** `impact_assessment_report`, `scenario_comparison`.
- **Interactions:** Feeds spectrum-intelligence-map. Depends on allocation-intelligence-engine and institutional-memory-engine.

**10. `review-prediction-engine`**
- **Role:** Predict reviewer objections using historical data.
- **Standalone justification:** Questionable. This overlaps significantly with working-paper-stress-test. Consider making prediction a capability within the stress test engine rather than a separate repo.
- **Contracts consumed:** Institutional memory records, `question_register`, historical comment/resolution records.
- **Contracts exposed:** `prediction_report`.
- **Interactions:** Depends on institutional-memory-engine and agency-question-radar.

**11. `spectrum-study-autopilot`**
- **Role:** Intelligent study management recommendations.
- **Standalone justification:** Questionable. Overlaps with spectrum-program-advisor (SYS-005). Consider extending SYS-005 with autopilot capabilities rather than creating a separate repo.
- **Contracts consumed:** Study lifecycle status, program advisor outputs, action registers.
- **Contracts exposed:** `action_recommendations`, `escalation_report`.
- **Interactions:** Depends on spectrum-study-operating-system and spectrum-program-advisor.

### Infrastructure Repos Not in the Roadmap That Will Likely Be Needed

**12. `spectrum-ontology` (or defined within spectrum-systems)**
- **Role:** Canonical taxonomy and ontology definitions for the spectrum domain.
- **Standalone justification:** Could live in spectrum-systems as a governed artifact set, or as a standalone repo if the ontology is large and evolves independently.
- **Contracts exposed:** Term definitions, relationship schemas, concept hierarchies.
- **Interactions:** Consumed by agency-question-radar, allocation-intelligence-engine, and spectrum-intelligence-map.

**13. `spectrum-artifact-store` (or `spectrum-data-lake`)**
- **Role:** Governed storage, retrieval, and lifecycle management for artifacts produced by all engines.
- **Standalone justification:** Yes, if a shared artifact store is adopted. The current architecture relies on `external_artifact_manifest` but has no actual storage system.
- **Contracts consumed:** Artifact envelope standard, provenance records.
- **Contracts exposed:** Storage API, retrieval API, lifecycle events.
- **Interactions:** All engines deposit artifacts; all consumers retrieve them.

---

## F. Data Architecture Risks

### 1. Schema Fragmentation (High Risk)

The roadmap describes 15 systems, each producing at least one artifact type with a defined schema. Currently, only SYS-001 through SYS-009 have schemas defined (or partially defined) in spectrum-systems. The six new Layer 1 systems and five Layer 2 systems will need approximately 15–20 new artifact schemas.

**Risk:** Without a schema governance process that enforces naming conventions, field types, provenance inclusion, and versioning discipline, schemas will fragment. Different engines will represent the same concept (e.g., "agency," "frequency range," "protection criteria") with incompatible field names and types.

**Guardrail:** Define a schema design standard in spectrum-systems that specifies required common fields, naming conventions, type vocabulary, and versioning rules. Enforce it through system-factory scaffolding and CI validation.

### 2. Duplicated Artifact Definitions (Medium Risk)

Several system pairs produce closely related artifacts:
- Knowledge Capture Engine → "decision records with rationale" / Institutional Memory Engine → "persistent decision database"
- Working Paper Stress Test → "predicted reviewer objections" / Review Prediction Engine → "predicted objection list"
- Spectrum Study Program Advisor → "program status report" / Spectrum Study Autopilot → "recommended next action sequence"

**Risk:** If these systems define independent artifact types with different schemas for semantically identical data, consumers will need translation logic, which is the "adapter hell" the 100-step roadmap warns about.

**Guardrail:** Define canonical artifact types for shared concepts (decision records, prediction reports, program status). Multiple systems can produce instances of the same canonical type.

### 3. Inconsistent Identifiers Across Engines (High Risk)

The provenance standard defines `record_id` as required but does not specify its structure, namespace, or uniqueness scope. When the Knowledge Capture Engine references a decision made in a meeting processed by the Meeting Intelligence System, both systems need to agree on how to identify that decision.

**Risk:** Without canonical identifiers, cross-engine artifact linking will rely on fragile heuristics (matching by timestamp, text similarity, or manual correlation). This undermines the traceability that the entire architecture depends on.

**Guardrail:** Define a canonical ID standard in spectrum-systems specifying ID format (e.g., `{system_id}-{artifact_type}-{uuid}`), namespace rules, and resolution conventions.

### 4. Weak Traceability Between Inputs and Outputs (Medium Risk)

The roadmap requires provenance records but does not describe how multi-hop traceability works. When the Spectrum Intelligence Map traces a conclusion back through Review Prediction Engine → Institutional Memory Engine → Knowledge Capture Engine → Meeting Intelligence System → original transcript, every intermediate link must preserve `derived_from` references.

**Risk:** If any engine in the chain drops or corrupts `derived_from` references, end-to-end traceability breaks silently.

**Guardrail:** Require every engine to emit a `derivation_chain` field that includes all upstream artifact IDs, not just the immediate input. Validate chain integrity in the pipeline engine.

### 5. Governance Drift Across Repos (Medium Risk)

As the ecosystem grows from 8 repos to 15–20+, the risk of governance drift increases. Each repo pins contract versions via system-factory, but there is no mechanism described for propagating governance updates across all repos simultaneously.

**Risk:** Repos that are less actively maintained will fall behind on contract versions, creating compatibility islands.

**Guardrail:** The 100-step roadmap addresses this (steps 49–52), but the operational AI systems roadmap should reference these governance mechanisms explicitly and identify which Layer 2 systems are most vulnerable to drift.

### 6. Duplicated Knowledge Stores (Medium Risk)

The roadmap describes three systems that store knowledge:
- Knowledge Capture Engine ("query-ready knowledge base entries")
- Institutional Memory Engine ("persistent decision and assumption database")
- Spectrum Intelligence Map ("unified, queryable intelligence layer")

**Risk:** Three independent knowledge stores with overlapping content will create consistency problems and query confusion (which store is authoritative for a given fact?).

**Guardrail:** Define a single canonical knowledge model in spectrum-systems. Knowledge Capture Engine ingests into it; Institutional Memory Engine maintains it; Spectrum Intelligence Map indexes and queries it. One store, three interfaces.

---

## G. Governance Implications

The roadmap implies new governance artifacts that spectrum-systems should define. Below are recommended governance documents and standards.

### New Governance Documents Needed

1. **Ontology / Taxonomy Standard** (`docs/ontology-standard.md`)
   Define canonical terms, hierarchies, and relationships for the spectrum domain. Required before Agency Question Radar, Allocation Intelligence Engine, or Spectrum Intelligence Map can be built. Tier 4 in the data lake strategy, but Tier 2 in practice.

2. **Canonical Identifier Standard** (`docs/canonical-id-standard.md`)
   Define ID format, namespace rules, uniqueness scope, and resolution conventions. Required before any cross-engine artifact linking is reliable.

3. **Cross-Engine Artifact Contract Registry** (extension of `contracts/standards-manifest.json`)
   The current manifest tracks contracts per system. As Layer 2 systems consume from multiple Layer 1 engines, a cross-engine contract registry is needed that specifies which artifact types flow between which systems, with version compatibility constraints.

4. **Simulation Interface Standard** (`docs/simulation-interface-standard.md`)
   Define how simulation inputs, parameters, outputs, and metadata are structured. Required before the Interference Analysis Assistant or Regulatory Impact Simulator can be built with composable interfaces.

5. **Decision Record Schema** (`schemas/decision-record.schema.json`)
   Define the canonical schema for decision records produced by Knowledge Capture Engine and consumed by Institutional Memory Engine and Spectrum Intelligence Map. Currently implicit in multiple system descriptions.

6. **Memory Object Schema** (`schemas/memory-object.schema.json`)
   Define the canonical schema for institutional memory entries including assumptions, rationale, evidence links, and validation status.

7. **Scenario Evaluation Schema** (`schemas/scenario-evaluation.schema.json`)
   Define the canonical schema for scenario analyses produced by the Regulatory Impact Simulator and consumed by the Spectrum Intelligence Map.

8. **Study Plan Artifact Contract** (`contracts/study-plan-contract.json`)
   Define the contract for study plan artifacts produced by the Band Study Plan Generator.

9. **Knowledge Query Interface Standard** (`docs/knowledge-query-standard.md`)
   Define how institutional memory is queried — input format, result format, provenance requirements on query results. Required before multiple systems can query the knowledge base consistently.

10. **Layer 2 Integration Standard** (`docs/layer-2-integration-standard.md`)
    Define how Layer 2 systems compose Layer 1 outputs: event-driven vs. polling, artifact resolution, conflict handling, and lifecycle coordination.

---

## H. Build Sequencing

### Assessment of Proposed Dependency Ladder

The roadmap proposes this build order:

1. Band Study Plan Generator
2. Meeting Intelligence System
3. Agency Question Radar
4. Comment Resolution Engine
5. Working Paper Stress Test
6. Interference Analysis Assistant
7. Allocation Intelligence Engine
8. Knowledge Capture Engine
9. Spectrum Study Program Advisor
10. Institutional Memory Engine
11. Review Prediction Engine
12. Regulatory Impact Simulator
13. Spectrum Study Autopilot
14. Spectrum Study Operating System
15. Spectrum Intelligence Map

### Sequencing Problems

**Problem 1: Knowledge Capture Engine is too late.**
Position 8 is too late for the Knowledge Capture Engine. It is described as consuming outputs from the Meeting Intelligence System (position 2), Comment Resolution Engine (position 4), and other engines. But more importantly, the Institutional Memory Engine (position 10) depends on it, and the Review Prediction Engine (position 11) depends on the Institutional Memory Engine. If the Knowledge Capture Engine is not producing stable outputs early, the entire knowledge accumulation pipeline is delayed. It should move to position 4 or 5.

**Problem 2: Spectrum Study Operating System is too late.**
Position 14 (second to last) is wrong for the Spectrum Study Operating System. It is described as "the connective tissue" for a study lifecycle. The Spectrum Study Autopilot (position 13) depends on it. The Spectrum Study Program Advisor (position 9) depends on "artifact status records from the Spectrum Study Operating System." Placing the operating system after its consumers is a dependency violation. It should move to position 10 or 11, after enough Layer 1 engines are producing stable outputs to make integration meaningful.

**Problem 3: Agency Question Radar before Comment Resolution Engine.**
The roadmap places the Agency Question Radar at position 3 and the Comment Resolution Engine at position 4. But the Agency Question Radar consumes "comment matrices from working papers" — which are the output of the Comment Resolution Engine. This is a circular dependency that the roadmap does not acknowledge. In practice, the Radar can operate on raw comment inputs, but the dependency should be clarified.

**Problem 4: Missing infrastructure sequencing.**
The dependency ladder contains only the 15 application systems. It does not account for enabling infrastructure (canonical ID standard, ontology, artifact store, schema governance tooling) that must exist before Layer 2 integration works. These infrastructure dependencies should be interleaved into the ladder.

### Recommended Revised Sequence

**Phase 1 — Foundation Engines (can be built independently)**
1. Meeting Intelligence System (high artifact availability, existing transcripts)
2. Comment Resolution Engine (addresses BN-001, highest-value bottleneck)
3. Band Study Plan Generator (operates at study start, no upstream dependencies)
4. Knowledge Capture Engine (start accumulating institutional memory early)

**Phase 2 — Analysis Engines (benefit from Phase 1 outputs)**
5. Agency Question Radar (operates on comment matrices and transcripts from 1–2)
6. Working Paper Stress Test (uses outputs from 5 and prior analysis artifacts)
7. Interference Analysis Assistant (operates on external simulation outputs)
8. Allocation Intelligence Engine (operates on external regulatory data)

**Infrastructure Gate: Before proceeding to Phase 3, the following must be stable:**
- Canonical ID standard
- Cross-engine artifact contracts for all Phase 1–2 engines
- Artifact store or manifest infrastructure
- Ontology baseline for spectrum domain

**Phase 3 — Integration Layer**
9. Spectrum Study Program Advisor (consumes Phase 1–2 outputs via pipeline)
10. Spectrum Study Operating System (integration infrastructure for study lifecycle)
11. Institutional Memory Engine (queryable store for accumulated knowledge)

**Phase 4 — Intelligence Systems**
12. Review Prediction Engine (depends on institutional memory and question radar)
13. Regulatory Impact Simulator (depends on allocation intelligence and memory)
14. Spectrum Study Autopilot (extends program advisor with proactive recommendations)

**Phase 5 — Apex**
15. Spectrum Intelligence Map (requires stable outputs from all layers)

---

## I. Long-Term Vision Feasibility

### Spectrum Intelligence Map — Feasibility Assessment

**Technical Feasibility: Achievable with significant infrastructure investment.**

The Spectrum Intelligence Map is essentially a multi-domain knowledge graph with simulation capabilities. The five data domains (regulatory, real-world systems, physics/propagation, policy/constraints, decisions) can be represented as a graph with typed nodes and edges. Graph database technology (e.g., Neo4j, Amazon Neptune, or even well-structured relational models) can support the query patterns described.

The simulation aspect — "simulate proposed regulatory or allocation changes and observe predicted downstream effects" — is the most technically demanding feature. This requires:
- A complete-enough graph of regulatory constraints and system parameters
- Validated models for how changes propagate through the constraint network
- A way to express "what-if" scenarios as graph mutations
- Confidence scoring for predictions

This is achievable as a rule-based system for direct effects (e.g., modifying a footnote affects these services). Predicting cascading or second-order effects with confidence is a harder research problem.

**Data Requirements: Substantial and slow to accumulate.**

The Intelligence Map depends on structured data from every Layer 1 and Layer 2 system. A useful version requires:
- At least 3–5 completed studies with full artifact lineage
- A populated allocation table with footnotes and service definitions
- Historical decision records spanning multiple review cycles
- Validated interference analysis results for multiple bands

This data will accumulate over years, not months. The map's value scales with data volume.

**Organizational Adoption Barriers: The primary risk.**

The Spectrum Intelligence Map's value depends on institutional adoption:
- Engineers must use the operational engines consistently (not just for demonstrations)
- Decision-makers must accept system-produced intelligence as input to their decisions
- Multiple agencies must participate in a shared information architecture
- Data quality and completeness must be sustained across personnel changes

These are organizational challenges, not technical ones. The roadmap acknowledges this implicitly ("the value of this architecture is cumulative") but does not discuss adoption strategy.

**Likely Dependencies:**
- All Layer 1 engines producing stable, contract-governed outputs
- Institutional Memory Engine operational with 2+ years of accumulated data
- Canonical ontology covering spectrum domain concepts
- Allocation table and footnote database populated and maintained
- Artifact store operational with lineage tracking

**Realistic Timeline:**
- A prototype with one or two populated data domains could be useful within 2–3 years of sustained Layer 1 engine operation
- A "minimum useful" version spanning regulatory terrain, real-world systems, and decision history could be achieved in 3–5 years
- The full five-domain intelligence map with simulation capabilities is a 5–8 year aspiration, assuming sustained institutional commitment

The roadmap correctly positions this as "long-term strategic value" and does not promise near-term delivery. This is the right framing.

---

## J. Actionable Recommendations

### Recommendation 1: Register All Roadmap Systems
Assign system IDs (SYS-010 through SYS-020) to all 15 systems described in the roadmap. Add them to `docs/systems-registry.md` with status "Roadmap — Not Yet Scoped." This closes the governance gap between the roadmap and the registry.

### Recommendation 2: Resolve Naming Inconsistencies
Establish canonical names for systems that appear under different names in the roadmap vs. registry. Document the mapping in the systems registry. Specifically: Meeting Intelligence System ↔ Meeting Minutes Engine; Working Paper Stress Test ↔ relationship to Working Paper Review Engine.

### Recommendation 3: Define Canonical ID Standard
Write `docs/canonical-id-standard.md` defining ID format, namespace, uniqueness scope, and resolution conventions. This is a prerequisite for cross-engine traceability and should be completed before any Layer 2 system is built.

### Recommendation 4: Elevate Ontology to Tier 2 Priority
Move taxonomy/ontology from Tier 4 in the data lake strategy to active governance work. Define an initial ontology covering: spectrum services, frequency bands, regulatory constructs, study phases, artifact types, and agency identifiers. Publish in spectrum-systems.

### Recommendation 5: Define Canonical Knowledge Model
Specify a single knowledge model (decision records, assumption records, memory objects) in spectrum-systems that the Knowledge Capture Engine, Institutional Memory Engine, and Spectrum Intelligence Map all share. Prevent three independent knowledge representations.

### Recommendation 6: Add Infrastructure Gate to Dependency Ladder
Insert an explicit infrastructure gate between Layer 1 and Layer 2 systems requiring: canonical IDs, cross-engine contracts, artifact store readiness, and ontology baseline. Do not begin Layer 2 systems until the gate is passed.

### Recommendation 7: Revise Build Sequencing
Adopt the revised four-phase sequence proposed in Section H. Move Knowledge Capture Engine earlier (Phase 1). Move Spectrum Study Operating System to Phase 3. Add infrastructure gate before Phase 3.

### Recommendation 8: Sharpen Overlapping System Boundaries
Write explicit boundary documents for the three system pairs with unclear boundaries: (a) Working Paper Stress Test vs. Review Prediction Engine, (b) Knowledge Capture Engine vs. Institutional Memory Engine, (c) Spectrum Study Program Advisor vs. Spectrum Study Autopilot. For each, state what artifacts each system exclusively owns, and where the handoff occurs.

### Recommendation 9: Add Bottleneck Mappings for New Systems
Create BN-007 through BN-012 in the bottleneck map for the six new systems. Every system should trace to a specific bottleneck to maintain the design discipline of bottleneck-driven automation.

### Recommendation 10: Define Simulation Interface Standard
Write `docs/simulation-interface-standard.md` specifying how simulation inputs, parameters, outputs, and metadata are structured. Required before the Interference Analysis Assistant or Regulatory Impact Simulator can expose composable interfaces.

### Recommendation 11: Add Observability as a Cross-Cutting Concern to the Roadmap
The operational AI systems roadmap does not mention observability. Add a section on cross-cutting concerns that references the observability requirements from the 100-step roadmap and specifies minimum observability requirements per layer.

### Recommendation 12: Define Layer 2 Integration Pattern
Write `docs/layer-2-integration-standard.md` specifying how Layer 2 systems compose outputs from multiple Layer 1 engines: event-driven vs. polling, artifact resolution, conflict handling, multi-engine transaction boundaries, and failure modes.

---

## K. Design Review Action List

### Action Table

| Action ID | Severity | Category | Description | Recommended Action | Affected Components |
| --- | --- | --- | --- | --- | --- |
| RM-001 | High | Governance | Six roadmap systems have no system IDs, no registry entries, and no bottleneck mappings. The roadmap describes systems outside the governance framework. | Assign SYS-010 through SYS-020. Add to `docs/systems-registry.md` with status "Roadmap — Not Yet Scoped." Create BN-007 through BN-012. | spectrum-systems: systems-registry.md, bottleneck-map.md |
| RM-002 | High | Data Model | No canonical identifier standard exists. Cross-engine artifact linking will be fragile without namespaced, structured IDs. | Write `docs/canonical-id-standard.md` specifying ID format, namespace, uniqueness scope, and resolution conventions. | spectrum-systems, all engine repos |
| RM-003 | High | Architecture | Build sequencing places Spectrum Study Operating System at position 14, after systems that depend on it. Knowledge Capture Engine at position 8 is too late. | Revise dependency ladder per Section H recommendations. Move Knowledge Capture Engine to Phase 1, Spectrum Study Operating System to Phase 3. | spectrum-systems: roadmap document |
| RM-004 | High | Data Model | Three knowledge stores (Knowledge Capture, Institutional Memory, Intelligence Map) risk creating inconsistent, duplicated knowledge representations. | Define a canonical knowledge model (decision records, assumption records, memory objects) in spectrum-systems that all three systems share. | spectrum-systems: schemas/, knowledge-capture-engine, institutional-memory-engine |
| RM-005 | Medium | Architecture | Working Paper Stress Test / Review Prediction Engine overlap. Knowledge Capture / Institutional Memory Engine overlap. Program Advisor / Autopilot overlap. | Write explicit boundary documents for each pair specifying exclusive artifact ownership and handoff points. | spectrum-systems: roadmap, affected engine repos |
| RM-006 | Medium | Governance | Ontology/taxonomy is classified as Tier 4 in data lake strategy but is a practical prerequisite for Layer 2 and Layer 3 systems. | Elevate ontology to active governance work. Define initial ontology for spectrum domain in spectrum-systems. Write `docs/ontology-standard.md`. | spectrum-systems: data-lake-strategy.md, new ontology docs |
| RM-007 | Medium | Architecture | No infrastructure gate between Layer 1 and Layer 2. Layer 2 systems will fail if built before enabling infrastructure (IDs, contracts, artifact store, ontology) is stable. | Insert explicit infrastructure gate into the dependency ladder with defined readiness criteria. | spectrum-systems: roadmap document |
| RM-008 | Medium | Data Model | Schema fragmentation risk across 15+ engines. No schema design standard enforces common fields, naming conventions, or versioning rules. | Define a schema design standard in spectrum-systems. Enforce through system-factory scaffolding. | spectrum-systems, system-factory |
| RM-009 | Medium | Governance | Naming inconsistencies between roadmap and systems registry. "Meeting Intelligence System" vs. "Meeting Minutes Engine," "Working Paper Stress Test" vs. relationship to SYS-007. | Establish canonical names. Document the mapping in the systems registry with aliases. | spectrum-systems: systems-registry.md, roadmap |
| RM-010 | Medium | Architecture | No simulation interface standard. Interference Analysis Assistant and Regulatory Impact Simulator depend on simulation infrastructure that is undefined. | Write `docs/simulation-interface-standard.md`. | spectrum-systems, interference-analysis-assistant, regulatory-impact-simulator |
| RM-011 | Low | Architecture | Roadmap does not mention observability as a cross-cutting concern, despite the 100-step roadmap dedicating significant steps to it. | Add a "Cross-Cutting Concerns" section to the roadmap covering observability, auditability, and security. | spectrum-systems: roadmap document |
| RM-012 | Low | Architecture | No Layer 2 integration pattern defined. Multiple systems consuming from multiple engines will need a standard for composition, event handling, and failure modes. | Write `docs/layer-2-integration-standard.md`. | spectrum-systems, Layer 2 engine repos |
| RM-013 | Low | Repo Structure | Review Prediction Engine and Spectrum Study Autopilot may not justify standalone repos. Their functions significantly overlap with existing systems. | Evaluate whether these should be capabilities within existing repos (working-paper-stress-test and spectrum-program-advisor) rather than separate repos. | spectrum-systems: roadmap, potential repos |
| RM-014 | Medium | Process | No artifact store or data lake infrastructure described despite 15+ systems producing artifacts that other systems consume. | Evaluate artifact store requirements. Determine whether spectrum-artifact-store should be a standalone repo or a service defined in spectrum-systems. Stabilize `external_artifact_manifest` (carries forward GA-004). | spectrum-systems, potential spectrum-artifact-store repo |

---

## Extracted Action Items

1. **RM-001** — Register all roadmap systems (SYS-010–SYS-020) in the systems registry and create bottleneck mappings BN-007–BN-012. Owner: TBD. Acceptance: All 15 systems have registry entries; all new systems have bottleneck IDs.
2. **RM-002** — Write canonical ID standard. Owner: TBD. Acceptance: Standard is published in spectrum-systems; system-factory scaffolding includes ID generation.
3. **RM-003** — Revise dependency ladder in the roadmap. Owner: TBD. Acceptance: Revised sequence adopted; infrastructure gate defined.
4. **RM-004** — Define canonical knowledge model schemas. Owner: TBD. Acceptance: decision-record, assumption-record, and memory-object schemas published in spectrum-systems.
5. **RM-005** — Write boundary documents for three overlapping system pairs. Owner: TBD. Acceptance: Each pair has a published boundary document specifying exclusive artifacts and handoffs.
6. **RM-006** — Elevate ontology to active work; publish initial ontology standard. Owner: TBD. Acceptance: `docs/ontology-standard.md` exists with initial term set.
7. **RM-007** — Define infrastructure gate with readiness criteria. Owner: TBD. Acceptance: Gate criteria documented in roadmap; criteria are testable.
8. **RM-008** — Write schema design standard. Owner: TBD. Acceptance: Standard published; system-factory templates enforce it.
9. **RM-009** — Resolve naming inconsistencies. Owner: TBD. Acceptance: Registry and roadmap use consistent names with documented aliases.
10. **RM-010** — Write simulation interface standard. Owner: TBD. Acceptance: Standard published; Interference Analysis Assistant contract references it.
11. **RM-011** — Add cross-cutting concerns section to roadmap. Owner: TBD. Acceptance: Roadmap includes observability, auditability, and security requirements per layer.
12. **RM-012** — Write Layer 2 integration standard. Owner: TBD. Acceptance: Standard published with event handling, composition, and failure mode patterns.
13. **RM-013** — Evaluate standalone vs. merged repos for Review Prediction Engine and Autopilot. Owner: TBD. Acceptance: Decision recorded in an ADR.
14. **RM-014** — Evaluate artifact store requirements and stabilize external artifact manifest. Owner: TBD. Acceptance: Artifact store decision made; manifest contract stabilized.

## Blocking Items

- **RM-002 (Canonical ID Standard)** blocks reliable cross-engine artifact linking. Must be resolved before Layer 2 development.
- **RM-004 (Canonical Knowledge Model)** blocks Knowledge Capture Engine and Institutional Memory Engine development with consistent schemas.
- **GA-004 (External Artifact Manifest Stabilization)** from prior reviews remains unresolved and blocks artifact flow infrastructure.

## Deferred Items

- **RM-013 (Repo merge evaluation)** — Defer until Working Paper Stress Test and Spectrum Study Program Advisor are stable enough to evaluate extension feasibility. Trigger: When either system reaches "Design complete" status.
- **Spectrum Intelligence Map detailed architecture** — Defer until at least 3 Layer 1 engines are producing stable outputs. Trigger: When Phase 2 of revised build sequence is complete.

---

## Follow-up Review Triggers

1. When RM-001 through RM-003 are completed, conduct a follow-up review to verify registry completeness and sequencing soundness.
2. When the first Layer 2 system begins design, review the Layer 2 integration standard (RM-012) for completeness.
3. When 3+ Layer 1 engines are producing stable outputs, conduct a data architecture review to assess schema consistency and traceability.
