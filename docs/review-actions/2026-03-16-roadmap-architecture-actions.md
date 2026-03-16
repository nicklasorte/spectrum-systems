# Action Tracker: Operational AI Systems Roadmap Architecture Review
**Review ID:** 2026-03-16-roadmap-review
**Review Date:** 2026-03-16
**Review Document:** `docs/reviews/2026-03-16-operational-ai-systems-roadmap-architecture-review.md`

---

## Executive Summary

The 100-step roadmap is architecturally sound but requires **10 concrete governance and execution actions** to prevent data fragmentation, schema conflicts, and integration debt. Critical actions are frontloading data architecture governance and moving contract validation left in the build sequence.

**Critical blockers:** Study context schema, data lake governance, knowledge graph schema, policy language definition must be in place before dependent roadmap steps begin.

---

## Action Items

### ACTION-001: Frontload Data Architecture Governance (Critical)
**Source Gap:** F. Data Architecture Risks, Risk 1-5
**Recommendation:** J.1
**Status:** Pending
**Priority:** Critical
**Target Maturity:** Level 4 → 5
**Owner:** spectrum-systems governance team
**Target Repository:** spectrum-systems

**Description:**
Insert three new governance definition steps after Step 10 of the roadmap:
- 10a: "Publish data architecture governance charter"
- 10b: "Define study context artifact schema"
- 10c: "Create data-to-lake interface contract"

**Acceptance Criteria:**
1. Data architecture governance charter (`docs/data-lake-governance.md`) drafted and approved by governance review.
2. Study context artifact schema (`contracts/schemas/study-context.schema.json`) defined with mandatory fields: study_id, artifact_version, provenance_reference, study_phase.
3. Data-to-lake interface contract (`docs/data-lake-interface.md`) specifies artifact submission rules, schema validation, provenance enforcement.
4. All three artifacts are referenced in standards-manifest.
5. CI includes schema validation step that enforces study context compliance.

**Evidence Required:**
- Approved governance documents
- Schema JSON file with examples
- CI validation script and test results

**Timeline:** Q2 2026 (4 weeks)
**Dependencies:** Step 10 of roadmap must be complete
**Blocking:** Steps 29, 38, 48, 65
**Notes:** This is a hard blocker for downstream pipeline and learning work. If deferred, artifact schema fragmentation will accumulate and cannot be reversed.

---

### ACTION-002: Move Contract Validation Left (High)
**Source Gap:** H. Build Sequencing Analysis, Issue 1
**Recommendation:** J.2
**Status:** Pending
**Priority:** High
**Target Maturity:** Level 3 → 8
**Owner:** CI/DevOps team + spectrum-systems governance
**Target Repository:** spectrum-systems + operational-engines (all)

**Description:**
Execute cross-repo contract validation gate immediately after Step 10 (not at Step 49). Implement manifest validation and schema compatibility checks in CI across all ecosystem repositories.

**Acceptance Criteria:**
1. CI pipeline includes contract validation stage that:
   - Validates `governance/schemas/spectrum-governance.schema.json` in all repos.
   - Checks that pinned contract versions exist in standards-manifest.
   - Validates artifact schemas against contract versions.
   - Blocks commits with unknown schemas or mismatched versions.
2. Validation is enabled in system-factory scaffolds for all new repos.
3. All existing repos (meeting-minutes-engine, review-engine, comment-resolution-engine, etc.) pass validation without modification.
4. Documentation updated: `docs/contract-validation-ci.md`.

**Evidence Required:**
- CI script implementation
- Test results showing validation passing on all repos
- Documentation of validation rules

**Timeline:** Q2 2026 (2 weeks)
**Dependencies:** Step 10 of roadmap, standards-manifest published
**Blocks:** Steps 21-48 (engines must not violate contracts before validation)
**Notes:** This prevents contract drift from accumulating. If deferred to Step 49, many systems will be built with violations that become expensive to fix.

---

### ACTION-003: Define Knowledge Graph Schema and Governance (High, Deferred)
**Source Gap:** C. Layering Integrity, Layer 3 / D. Missing Systems, Issue 2
**Recommendation:** J.3
**Status:** Pending / Deferred
**Priority:** High
**Target Maturity:** Level 15-16
**Owner:** spectrum-program-advisor team + spectrum-systems governance
**Target Repository:** spectrum-systems (governance), spectrum-program-advisor (implementation)

**Description:**
Before Steps 85-86 begin (knowledge graph), define the graph schema, query interface, ownership model, and governance contract. Create specifications for nodes (ADRs, decisions, runs, artifacts), edges (derived-from, blocked-by, references, instantiates), and query language.

**Acceptance Criteria:**
1. Knowledge graph schema (`contracts/schemas/knowledge-graph.schema.json`) published with:
   - Node types: decision, ADR, run, artifact, system, finding
   - Edge types: derived-from, blocked-by, references, instantiates, updates, confirms
   - Required metadata for each node type
2. Query interface specification (`docs/knowledge-graph-query-interface.md`) defines:
   - Query language (e.g., GraphQL subset or custom DSL)
   - Rate limits, access control, performance SLOs
   - Example queries (find decisions blocking a run, trace artifact lineage, etc.)
3. Governance model (`docs/knowledge-graph-governance.md`) specifies:
   - Who can add/modify nodes/edges
   - Versioning and deprecation model
   - Relationship to systems-registry and dependency-graph (not a replacement, a semantic layer)
4. Index strategy for search performance

**Evidence Required:**
- Schema document with examples
- Query interface specification with test queries
- Governance model document
- Performance benchmark plan

**Timeline:** Q3 2027 (4 weeks, before Steps 85-86)
**Dependencies:** Level 14 maturity achieved, governance debt addressed
**Blocks:** Steps 85-86, any downstream intelligence work depending on knowledge graph
**Notes:** This is deferred to Q3 2027 pending maturity gate review. Proceeding without schema will cause rework. Execution should happen early in Phase 6.

---

### ACTION-004: Establish Data Quality and Learning Readiness Checkpoints (High)
**Source Gap:** I. Long-Term Vision Feasibility, Data Requirements / F. Data Architecture Risks
**Recommendation:** J.4
**Status:** Pending
**Priority:** High
**Target Maturity:** Level 12 → 14
**Owner:** Observability team + data lake team + program-advisor team
**Target Repository:** spectrum-systems (framework), spectrum-program-advisor (implementation)

**Description:**
In Q1 2027, before initiating cross-study learning (Steps 64-65), conduct a data quality audit and establish minimum thresholds for learning readiness. Define ongoing measurement framework.

**Acceptance Criteria:**
1. Data quality audit report completed:
   - Artifact schema consistency: % of artifacts using study context schema
   - Provenance completeness: % of artifacts with full lineage recorded
   - Study context compliance: % of artifacts including study_id, artifact_version, provenance_reference
2. Minimum thresholds defined and published:
   - ≥95% schema consistency (no more than 5% non-conforming artifacts)
   - ≥90% provenance completeness (90%+ of artifacts have lineage)
   - ≥100% study context compliance (all artifacts include mandatory fields)
3. Continuous measurement framework established:
   - Metrics dashboard shows compliance over time
   - Alerts fire if thresholds drop below minimum
   - Weekly reports to data lake team
4. Steps 64-65 blocked until thresholds are met (documented in action plan)

**Evidence Required:**
- Data quality audit report with statistics
- Threshold definition document
- Metrics dashboard implementation
- Alert rules in monitoring system

**Timeline:** Q1 2027 (3 weeks)
**Dependencies:** Step 53 (observability baseline complete)
**Blocks:** Steps 64-65 (cannot proceed without clean data)
**Notes:** This is essential to prevent learning pipelines from working with bad data. Thresholds ensure data quality is measurable and sustained.

---

### ACTION-005: Define Confidence and Risk Scoring Framework (High)
**Source Gap:** D. Missing Systems, Issue 6 / F. Data Architecture Risks, general
**Recommendation:** J.5
**Status:** Pending
**Priority:** High
**Target Maturity:** Level 14 → 16
**Owner:** Data science team + spectrum-program-advisor team
**Target Repository:** spectrum-program-advisor, spectrum-systems (governance)

**Description:**
Before program advisor MVP begins (Step 62), define how confidence bounds and risk scores are computed, validated, and calibrated. Create recommendation contract and model evaluation protocol.

**Acceptance Criteria:**
1. Confidence scoring framework (`docs/confidence-framework.md`) specifies:
   - How confidence is computed (ensemble agreement, historical accuracy, sample size, epistemic uncertainty)
   - Calibration method (e.g., binning observed frequency against predicted probability)
   - Range and interpretation (0-100%, what each range means to operators)
2. Model evaluation protocol (`docs/model-evaluation-protocol.md`) defines:
   - Train/validation/holdout split strategy
   - Evaluation metrics (precision, recall, F1, calibration error)
   - Backtesting requirements before production use
   - Retraining triggers
3. Recommendation contract (`contracts/schemas/recommendation-contract.json`) specifies:
   - Recommendation text, action identifier, confidence score, evidence bundle reference
   - Alternative recommendations considered, why preferred option was chosen
   - Expiration/review trigger
4. First models trained and backtested on holdout study with calibration report

**Evidence Required:**
- Framework and protocol documents
- Recommendation contract JSON with examples
- Model evaluation and calibration report
- Backtesting results on holdout study

**Timeline:** Q2 2027 (3 weeks, before Step 62)
**Dependencies:** Step 54 (observability baseline), Level 12 maturity
**Blocks:** Steps 62+, any production advisory work
**Notes:** Transparent confidence is essential for organizational trust. Models without backtesting evidence are not production-ready. This should be completed before any recommendation is served to decision-makers.

---

### ACTION-006: Consolidate Governance Registries (Medium)
**Source Gap:** F. Data Architecture Risks, Risk 3
**Recommendation:** J.6
**Status:** Pending
**Priority:** Medium
**Target Maturity:** Level 12 → 13
**Owner:** Governance team
**Target Repository:** spectrum-systems

**Description:**
Define a registry consolidation strategy that establishes single source of truth and synchronization rules for systems-registry, maturity-tracker, and dependency-graph. Prevent drift and contradictions.

**Acceptance Criteria:**
1. Registry consolidation strategy document (`docs/registry-consolidation-strategy.md`) specifies:
   - Systems Registry is source of truth (system existence, roles, loop alignment)
   - Dependency Graph is derived artifact (regenerated from system manifests in CI)
   - Maturity Tracker references both registry and graph (cross-linked)
   - Knowledge Graph is semantic layer (not a replacement for registries)
2. CI validates consistency:
   - Dependency graph regeneration on manifest changes
   - Maturity tracker entries reference valid system IDs
   - No orphaned entries in any registry
3. Update procedures documented for manual changes (rare) with governance approval required
4. Test suite verifies registry consistency (automated)

**Evidence Required:**
- Strategy document with ownership and update rules
- CI validation script and test results
- Reconciliation report showing current consistency status

**Timeline:** Q2 2027 (2 weeks)
**Dependencies:** Step 16, Step 51 (dependency graph and registry already exist)
**Blocks:** Steps 85-86 (knowledge graph depends on clear registry semantics)
**Notes:** This prevents confusion and operational errors. Should be completed early in Phase 4 (before registry complexity increases).

---

### ACTION-007: Define Simulation Engine Interface Contract (Medium)
**Source Gap:** D. Missing Systems, Issue 3 / C. Layering Integrity
**Recommendation:** J.7
**Status:** Pending
**Priority:** Medium
**Target Maturity:** Level 6 → 7
**Owner:** spectrum-systems governance team
**Target Repository:** spectrum-systems

**Description:**
After Step 6 (engine interface standard), insert a new step to define simulation engine boundary and interface contract. Specify inputs, outputs, provenance requirements, and control signals.

**Acceptance Criteria:**
1. Simulation engine interface contract (`contracts/simulation-engine-contract.json`) specifies:
   - Inputs: study context, parameter ranges, baseline assumptions, initial conditions
   - Outputs: scenario traces, outcome predictions, confidence bounds, decision points
   - Provenance: which inputs led to which outputs, parameter sensitivity
   - Control signals: progress reporting, cancellation, resource limits
2. Interface documentation (`docs/simulation-engine-interface.md`) provides:
   - Example invocations (simulate risk mitigation strategy, forecast timeline impact, etc.)
   - Error handling and recovery
   - SLA expectations (response time, max scenario count, etc.)
3. Integration path with spectrum-pipeline-engine defined and tested

**Evidence Required:**
- Interface contract JSON with examples
- Documentation with usage examples
- Integration test showing pipeline can invoke simulator

**Timeline:** Q3 2026 (2 weeks, right after Step 6)
**Dependencies:** Step 6 (engine interface standard)
**Blocks:** Step 92 (scenario simulation depends on interface being clear)
**Notes:** Defining this early prevents the simulation engine from becoming a one-off component. It should integrate with the same interface patterns as other engines.

---

### ACTION-008: Create Roadmap Tracking Dashboard (Medium)
**Source Gap:** H. Build Sequencing Analysis (visibility/tracking)
**Recommendation:** J.8
**Status:** Pending
**Priority:** Medium
**Target Maturity:** Level 13
**Owner:** Program management / governance team
**Target Repository:** spectrum-systems

**Description:**
Build a roadmap progress tracker and status dashboard to make execution progress visible and highlight blockers early. Enable data-driven timeline adjustments.

**Acceptance Criteria:**
1. Roadmap tracker artifact (`ecosystem/roadmap-tracker.json`) captures:
   - Step number, title, status (not-started, in-progress, complete)
   - Maturity level and evidence type
   - Assigned owner and timeline
   - Blocking issues or dependencies
   - Completion evidence (PR, artifact, approval date)
2. Automated updates:
   - CI updates tracker when related PR is merged or artifact is added to spectrum-systems
   - Quarterly reviews refresh evidence status
3. Human-readable dashboard:
   - `docs/roadmap-status.md` auto-generated from tracker
   - Phase summaries, timeline view, blocker visualization
   - Current location indicator
4. Quarterly review cadence:
   - Every Q (Feb, May, Aug, Nov), governance team reviews progress
   - Timeline adjusted if evidence quality is lower than expected
   - Reviewed in maturity tracker update

**Evidence Required:**
- Tracker JSON schema and implementation
- CI automation script
- Dashboard generation script
- Sample dashboard output

**Timeline:** Q2 2026 (3 weeks)
**Dependencies:** Roadmap published and approved
**Blocks:** N/A (enables better governance, not a blocking requirement)
**Notes:** This increases transparency and enables evidence-driven management. Updates should be part of quarterly maturity review process.

---

### ACTION-009: Stage Intelligence Work with Maturity Gate (Medium, Ongoing)
**Source Gap:** I. Long-Term Vision Feasibility
**Recommendation:** J.9
**Status:** Pending / Ongoing
**Priority:** Medium
**Target Maturity:** Level 14 → 20
**Owner:** Program management / governance team
**Target Repository:** spectrum-systems

**Description:**
Insert a maturity gate before Steps 85-100 (Institutional Memory & Intelligence). Intelligence work only proceeds when Level 14 is achieved with evidence in three dimensions: governance, observability, data quality.

**Acceptance Criteria:**
1. Maturity gate criteria documented in roadmap (`docs/roadmap-maturity-gates.md`):
   - **Governance dimension:** All governance artifacts defined/versioned, governance debt ≤2 items, no critical blockers
   - **Observability dimension:** SLO scoreboard active, all engines reporting telemetry, release gates tied to error budgets, ≥90% run coverage
   - **Data dimension:** Study context schema compliance ≥100%, data lake schema consistency ≥99%, ≥5 study cycles completed, learning readiness thresholds met
2. Gate review process:
   - Quarterly maturity review includes gate assessment
   - Evidence collected in maturity-tracker
   - Gate decision documented and approved by governance lead
3. Contingency plan if gate is not cleared by target date:
   - Extend Phase 4 work (governance, observability, data)
   - Re-plan Intelligence phase work based on new evidence
   - Communicate timeline adjustments to leadership

**Evidence Required:**
- Gate criteria document
- Checklist for each dimension
- Evidence summary from maturity tracker
- Approval notes from quarterly review

**Timeline:** Q3 2027 (ongoing, gate decision in each quarterly review)
**Dependencies:** Steps 1-75 progressing on schedule
**Blocks:** Steps 85-100 (cannot proceed without gate clearance)
**Notes:** This prevents speculative work and ensures intelligence layer is built on solid foundation. Gate should be clearly communicated to prevent surprises.

---

### ACTION-010: Establish Quarterly Roadmap + Maturity Alignment Reviews (Low, Recurring)
**Source Gap:** H. Build Sequencing Analysis / I. Feasibility Assessment
**Recommendation:** J.10
**Status:** Pending / Ongoing
**Priority:** Low
**Target Maturity:** All levels
**Owner:** Governance team
**Target Repository:** spectrum-systems

**Description:**
Establish a recurring quarterly checkpoint to review roadmap progress against maturity model, verify evidence is recorded, and adjust timeline based on data (not intuition).

**Acceptance Criteria:**
1. Quarterly review cadence established (Feb, May, Aug, Nov):
   - Fixed date: 3rd Friday of the month
   - Attendees: Governance lead, program manager, architecture lead, data science lead
   - Duration: 4 hours
2. Review checklist includes:
   - Steps completed since last review: verify evidence is recorded
   - Upcoming steps: assess blockers and readiness
   - Maturity dimension assessment: progress on 9 dimensions
   - Evidence quality audit: random sample of recorded evidence
   - Timeline adjustments: recommended postponements or accelerations
3. Review output:
   - Quarterly update to `ecosystem/maturity-tracker.json` with evidence references
   - Roadmap status updated (`docs/roadmap-status.md`)
   - Summary email to leadership with timeline implications
4. Integration with maturity gate process:
   - Gate assessment at each quarterly review
   - Gate decision documented

**Evidence Required:**
- Review meeting template and agenda
- Checklist and scoring rubric
- Sample quarterly review report
- Maturity tracker update showing evidence links

**Timeline:** Ongoing (first review Feb 2026, then May, Aug, Nov)
**Dependencies:** Roadmap tracker and maturity tracker established
**Blocks:** N/A (governance process enabler)
**Notes:** This is a lightweight but high-impact governance practice. Time-boxes the review to 4 hours, which is manageable for a team already tracking maturity quarterly.

---

## Summary Table

| ID | Action | Priority | Timeline | Owner | Status |
|---|---|---|---|---|---|
| 001 | Frontload data architecture governance | Critical | Q2 2026 | spectrum-systems | Pending |
| 002 | Move contract validation left | High | Q2 2026 | CI/DevOps + governance | Pending |
| 003 | Define knowledge graph schema | High | Q3 2027 | spectrum-program-advisor + governance | Deferred |
| 004 | Establish data quality baselines | High | Q1 2027 | Observability + data lake | Pending |
| 005 | Define confidence framework | High | Q2 2027 | Data science + program-advisor | Pending |
| 006 | Consolidate registries | Medium | Q2 2027 | Governance team | Pending |
| 007 | Define simulation engine interface | Medium | Q3 2026 | spectrum-systems | Pending |
| 008 | Create roadmap tracking dashboard | Medium | Q2 2026 | Program management | Pending |
| 009 | Stage intelligence work with maturity gate | Medium | Q3 2027 (ongoing) | Program management | Pending |
| 010 | Quarterly alignment reviews | Low | Ongoing (Feb/May/Aug/Nov) | Governance team | Pending |

---

## Blocking Relationships

```
ACTION-001 (data governance) blocks: ACTION-004, ACTION-005, major pipeline work (Step 38+)
ACTION-002 (contract validation) blocks: avoiding technical debt in Steps 21-48
ACTION-003 (knowledge graph) blocks: Steps 85-86
ACTION-004 (data quality) blocks: Steps 64-65 (cross-study learning)
ACTION-005 (confidence) blocks: Step 62+ (advisor MVP and beyond)
ACTION-007 (simulation interface) blocks: Step 92 (scenario simulation)
ACTION-009 (maturity gate) blocks: Steps 85-100 (intelligence layer)
ACTION-010 (quarterly reviews) enables: all maturity promotions and timeline adjustments
```

---

## Next Steps

1. **Immediate (by end of Q2 2026):**
   - ACTION-001: Publish data governance charter and study context schema
   - ACTION-002: Enable contract validation in CI
   - ACTION-008: Implement roadmap tracking dashboard
   - ACTION-010: Schedule first quarterly review (May 2026)

2. **Phase 2 (Q3 2026):**
   - ACTION-007: Define simulation engine interface
   - Execution of Steps 21-30 (first engines) with clean contracts

3. **Phase 3 (Q1-Q2 2027):**
   - ACTION-004: Conduct data quality audit and establish thresholds
   - ACTION-005: Define confidence framework before advisor MVP
   - ACTION-006: Consolidate registries
   - Execution of Steps 31-75 (multi-engine orchestration, governance, observability)

4. **Phase 4 (Q3 2027):**
   - ACTION-003: Define knowledge graph schema (if maturity gate is met)
   - ACTION-009: Assess maturity gate for intelligence work
   - Plan for Steps 85-100 based on evidence

---

**End of Action Tracker**
