# Systems Architecture Review: Spectrum Systems as Ecosystem Governance Constitution — Deep Review

**Date:** 2026-03-16
**Reviewer:** Claude (Principal Systems Architect — Governance Constitutional Review)
**Scope:** Deep architecture and governance review of `spectrum-systems` as the governing "constitution" for the full multi-repo ecosystem. Covers governance completeness, cross-repo constitutional strength, review culture, operational readiness, artifact and contract quality, and CI/automation enforcement.
**Review Type:** Deep governance and constitutional architecture review
**Prior Reviews Reconciled:** `2026-03-14-architecture-review`, `2026-03-14-governance-architecture-review`, `2026-03-15-ecosystem-constitution-audit`, `2026-03-15-cross-repo-ecosystem-architecture-review`, `2026-03-15-governance-architecture-audit`, `2026-03-16-operational-ai-systems-roadmap-architecture-review`, `2026-03-16-operational-ai-systems-roadmap-review`
**Finding IDs:** [F-1], [F-2], [F-3], [F-4], [F-5], [F-6], [F-7], [F-8], [F-9], [F-10]

---

## 1. Review Metadata

- **Repository:** `nicklasorte/spectrum-systems`
- **Date:** 2026-03-16
- **Reviewer:** Claude (Principal Systems Architect — Governance Constitutional Review)
- **Inputs consulted:**
  - `docs/design-review-standard.md`
  - `docs/governance-enforcement-roadmap.md`
  - `docs/governance-conformance-checklist.md`
  - `docs/implementation-boundary.md`
  - `contracts/standards-manifest.json`
  - `ecosystem/ecosystem-registry.json`
  - `governance/compliance-scans/run-cross-repo-compliance.js`
  - `scripts/check_artifact_boundary.py`
  - `.github/workflows/` (all five workflow files)
  - `design-reviews/claude-review.schema.json`
  - `docs/reviews/review-registry.json`
  - All prior review artifacts in `docs/reviews/`
  - `spectrum_systems/` Python package
  - `systems/*/interface.md` for all nine systems
  - `contracts/standards-manifest.json` (18 contracts)
  - `schemas/README.md`, `contracts/schemas/` structure

---

## 2. Scope

**In scope:**
- Governance completeness: schemas, manifests, registries, ADRs, review artifacts, and internal consistency
- Cross-repo constitutional strength: clarity, scaling readiness, drift prevention
- Review and design culture: repeatability, actionability, tracking fidelity
- Operational readiness: prototype vs. production-minded components, failure risk
- Artifact and contract quality: schema quality, alignment between docs and enforcement
- CI/automation enforcement: coverage, gaps, weak assertions

**Out of scope:**
- Implementation repositories (comment-resolution-engine, working-paper-review-engine, etc.) — only governance obligations from this repo toward them are in scope
- Roadmap feasibility — covered by prior 2026-03-16 roadmap reviews

---

## 3. Executive Summary

`spectrum-systems` has evolved into a structurally sound governance layer with real CI enforcement, comprehensive contract definitions, and a sophisticated design-review culture. Seven reviews over four days have produced a meaningful institutional record. The schemas are machine-operable, the review artifact pipeline is schema-backed, and the ecosystem registry now lists all ten repositories. However, a critical gap persists: **the governance model is still enforced through documentation and manual review rather than through mechanical constraints that downstream repos cannot bypass.**

The five most important findings:

1. **[F-1] Phase 1 enforcement has not been initiated.** The `governance-enforcement-roadmap.md` defines four enforcement phases; none is active. The `governance-declaration.template.json` — explicitly requested in GA-007 — does not yet exist. Every downstream repo can enter implementation without having made any machine-verifiable governance commitment.

2. **[F-2] The artifact boundary CI enforces data artifacts, not the implementation code boundary.** `spectrum_systems/study_runner/` — a full production pipeline — passes the boundary check without raising any alert. The check covers `.pdf`, `.docx`, binary blobs; it does not cover Python packages or runnable root scripts.

3. **[F-3] The production Python package remains.** `spectrum_systems/study_runner/` and `run_study.py` have been flagged as boundary violations in RC-1 (2026-03-15), A-1 (2026-03-15 audit), and GA-008 (2026-03-14 governance review). They remain present in the repository, constituting a self-governance failure that weakens the constitutional posture of the repo.

4. **[F-4] Schema authority is split across two directories without a canonical designation.** Root `schemas/` and `contracts/schemas/` contain overlapping schema coverage with no formal documentation of which is authoritative, which is legacy, or what the migration path is.

5. **[F-5] The cross-repo compliance scanner is a file-presence check, not a governance validator.** It confirms that `README.md`, `CLAUDE.md`, and `docs/` exist; it cannot detect contract version drift, schema incompatibilities, or missing governance declarations.

**Maturity assessment:** The repository is at **Level 2 (Structured)** approaching **Level 3 (Governed)**. The conceptual framework is at Level 4 quality; the enforcement machinery is at Level 1–2. Closing the gap between declared governance and mechanical enforcement is the single most important architectural investment.

---

## 4. Maturity Assessment

**Current level:** 2 (Structured)

**Evidence:**
- Comprehensive contract definitions with machine-readable registry (18 contracts, versioned, with intended consumers)
- Schema-backed design-review artifact pipeline with automation bridge to GitHub Issues
- CI enforcement for data artifacts, review artifact validation, and project board automation
- Ecosystem registry with all 10 repositories
- System lifecycle model with nine gates and a status registry
- ADR framework with five initial decisions

**Unmet criteria for Level 3 (Governed):**
- Phase 1 enforcement is not active: no downstream repo has filed a machine-verifiable governance declaration
- Implementation code boundary is not enforced mechanically
- Cross-repo compliance scanner validates presence, not governance
- Schema authority is ambiguous (dual-track)
- Governance conformance checklist is missing key items

**Next-level blockers:**
1. `contracts/governance-declaration.template.json` must exist and be referenced by `docs/governance-conformance-checklist.md`
2. Phase 1 must be formally initiated in `docs/governance-enforcement-roadmap.md`
3. Artifact boundary CI must be extended to enforce the implementation code boundary
4. Schema dual-track must be resolved with a designated canonical source

---

## 5. Strengths

### S-1: Design Review Artifact System Is Production-Grade
The dual-artifact review system (markdown + `.actions.json`) with schema-backed validation is the most mature governance mechanism in the repo. `claude-review.schema.json` enforces deterministic IDs, `ingest-claude-review.js` bridges findings to GitHub issues, and `review-artifact-validation.yml` runs on every push to `design-reviews/`. This is ecosystem-grade review infrastructure.

### S-2: Contract System Is Comprehensive and Machine-Operable
Eighteen artifact contracts with JSON schemas, example payloads, and a machine-readable standards manifest. Versioning policy defines semver semantics with concrete breaking-change criteria. `test_contracts.py` validates all example payloads against their schemas in CI.

### S-3: Ecosystem Registry Now Covers All Ten Repositories
`ecosystem/ecosystem-registry.json` enumerates all ten repos with `repo_type`, `layer`, `status`, `system_id`, `manifest_required`, and `contracts` arrays. This is the authoritative machine-readable roster for the ecosystem.

### S-4: CI Has Real Enforcement Depth
Five workflows enforce artifact boundary, review artifact validation, review ingestion, project automation, and cross-repo compliance scanning. The artifact boundary CI runs on push and PR to main, release/**, and codex/** branches.

### S-5: System Design Coverage Is Comprehensive
All nine systems have five-document packages under `systems/<system>/`. The `spectrum-pipeline-engine` — the highest-risk unmodeled system identified in the 2026-03-14 review — now has a full design package.

### S-6: Review Culture Is Institutionalized
Seven reviews in four days, all recorded in the registry with JSON entries, action trackers, and follow-up triggers. The review-to-action standard, registry format, and action tracker template create a repeatable review pipeline.

### S-7: Governance Policy Engine Is Present
`governance/policies/run-policy-engine.py` evaluates governance manifests against four policies (GOV-001 through GOV-004) and produces machine-readable pass/fail results. This is the kernel of a real enforcement mechanism.

### S-8: ADR Framework Provides Decision History
Five ADRs covering the operating model, maturity model, operational evidence standard, run evidence correlation, and review protocol. These form a navigable decision history that new contributors can follow.

---

## 6. Structural Gaps

### [G1] Phase 1 Enforcement Has No Concrete Artifact

`docs/governance-enforcement-roadmap.md` describes Phase 1 (declared identity and contract pins) and `docs/reviews/2026-03-14-governance-architecture-review.md` includes an explicit Codex prompt (GA-007) to create `contracts/governance-declaration.template.json`. This template does not exist. Without it:
- Downstream repos have no machine-readable format for declaring governance obligations
- `system-factory` cannot scaffold governance declarations automatically
- Phase 1 remains permanently aspirational

### [G2] Implementation Code Boundary Not Mechanically Enforced

`scripts/check_artifact_boundary.py` enforces data artifact rules (extensions: `.pdf`, `.docx`, binary blobs; size threshold: 2 MB). It does not enforce the architecture boundary stated in `CLAUDE.md` ("This repository should NOT contain production implementation code"). The `spectrum_systems/study_runner/` package and `run_study.py` root script pass CI unchallenged.

### [G3] Schema Authority Is Undesignated

Root `schemas/` has nine schemas covering comment, issue, provenance, assumption, study-output, precedent, compiler-manifest, artifact-bundle, and diagnostics. `contracts/schemas/` has fifteen schemas covering the full contract library with provenance fields and example payloads. `schemas/README.md` exists but does not state which location is canonical. Downstream repos cannot determine which path to import without consulting multiple documents.

### [G4] Cross-Repo Compliance Scanner Does Not Validate Governance

`governance/compliance-scans/run-cross-repo-compliance.js` checks for file presence (`README.md`, `CLAUDE.md`, `CODEX.md`, `SYSTEMS.md`, `docs/`, `tests/`) and README content matching. It does not verify:
- Contract version pins against `standards-manifest.json`
- Presence or schema validity of `system-manifest.json` or governance declaration files
- Schema compatibility claims
- Evaluation harness currency

### [G5] Governance Conformance Checklist Is Incomplete

`docs/governance-conformance-checklist.md` lists seven categories with 13 checklist items. It is missing:
- Machine-readable governance declaration file requirement (GA-007 explicit deliverable)
- Evaluation harness completion with pass/fail recorded
- ADR review for any architecture decision made in the repo
- CI-enforcement confirmation (boundary CI green, review artifact validation green)
- System lifecycle gate verification

### [G6] Prior Review Findings Have No Per-Finding Status Tracking

The review registry tracks reviews at a granular level (status: Open/In Progress/Blocked/Closed) but tracks individual findings only through `carried_forward_finding_ids`. There is no machine-readable mechanism to mark individual findings as resolved, escalated, or superseded across reviews. RC-1 (2026-03-15), A-1 (2026-03-15 audit), and GA-008 (2026-03-14) all identify the same production code issue; it remains unflagged in any registry as "carried forward unresolved."

### [G7] ADRs Do Not Cover Subsequent Architecture Decisions

Five ADRs cover decisions made in the initial phase. The subsequent 7-review sprint (2026-03-14 through 2026-03-16) produced significant architecture decisions — including the Phase 1 enforcement model, schema authority designation, and the governance manifest approach — that have not been formalized into ADRs. The decision record therefore ends at the initial build phase.

---

## 7. Risk Areas

### [R1] Governance Enforcement Remains Entirely Manual — High / High
All downstream repos can declare compliance without any mechanical verification. If `spectrum-pipeline-engine` is built while Phase 1 is still aspirational, it will consume eleven contracts with no verifiable governance commitment. Schema drift will be undetectable until runtime failures.
**Risk level: High severity / High likelihood if implementation proceeds now**

### [R2] Self-Governance Failure Undermines Constitutional Posture — High / High
A governance repository that does not enforce its own stated rules (no production code in CLAUDE.md; boundary CI passes production code) cannot credibly require compliance from others. The production package has been identified in three separate reviews without resolution. This is the single highest-priority credibility risk.
**Risk level: High severity / High likelihood of continued non-resolution without escalation**

### [R3] Schema Dual-Track Will Produce Import Conflicts at Scale — Medium / Medium
As the ecosystem grows to five or more implementation repos, each must choose which schema directory to import. If different repos choose different sources, schema drift will be undetectable. A breaking change in one location will not propagate to the other, creating split populations of schema consumers.
**Risk level: Medium severity / Medium likelihood as ecosystem scales**

### [R4] Design Review Findings Are Accumulating Faster Than Resolution — Medium / High
Seven reviews in four days have generated 80+ action items across multiple trackers. None of the reviews in the registry are "Closed." Without a closure mechanism and resolution workflow, the review culture generates institutional debt rather than driving resolution.
**Risk level: Medium severity / High likelihood without explicit closure gates**

### [R5] Policy Engine Is Present but Not Wired to CI — Medium / Medium
`governance/policies/run-policy-engine.py` can evaluate four governance policies against manifests. It is not called in any CI workflow. The cross-repo compliance workflow runs `run-cross-repo-compliance.js` (file-presence scan) but does not invoke the policy engine. The policy engine's enforcement value is therefore zero in practice.
**Risk level: Medium severity / Medium likelihood**

---

## 8. Recommendations

### REC-1: Create `contracts/governance-declaration.template.json` and Initiate Phase 1
Create the governance declaration template specified in GA-007. Define fields: `system_id`, `implementation_repo`, `architecture_source`, `contract_pins` (artifact_type → schema_version), `schema_pins` (schema file → version), `rule_version`, `prompt_set_hash`, `evaluation_manifest_path`, `last_evaluation_date`, `external_storage_policy`, `governance_declaration_version`. Include a complete SYS-001 example. Update `docs/governance-conformance-checklist.md` to add the machine-readable declaration requirement. Update `docs/governance-enforcement-roadmap.md` to mark Phase 1 as initiated.
**Expected outcome:** Phase 1 has a concrete template; downstream repos can file governance declarations; `system-factory` can scaffold declarations automatically.

### REC-2: Extend Artifact Boundary CI to Enforce Implementation Code Boundary
Add detection in `scripts/check_artifact_boundary.py` for: (1) Python packages under non-`scripts/` paths with `__init__.py` containing non-trivial logic, (2) root-level runnable scripts matching `run_*.py`, (3) any `src/` directory. Maintain an explicit allowlist for permitted narrow utilities (`scripts/`). Document the distinction in `docs/implementation-boundary.md`.
**Expected outcome:** The `spectrum_systems/` package would fail boundary CI; future production code additions are blocked automatically.

### REC-3: Designate Canonical Schema Authority
Add a "Schema Authority" section to `schemas/README.md` that: (1) declares `contracts/schemas/` as the canonical source for all governed contract schemas, (2) declares root `schemas/` as the supplemental store for non-contract structural schemas, (3) lists the migration path for any root schema that overlaps with a contracts schema. Update `CONTRACTS.md` to reference this designation.
**Expected outcome:** Downstream repos can resolve import ambiguity deterministically; schema drift detection becomes possible.

### REC-4: Wire Policy Engine to Cross-Repo Compliance CI
Add a step in `.github/workflows/cross-repo-compliance.yml` that runs `governance/policies/run-policy-engine.py --all` against available governance manifests and fails the workflow on policy violations. This converts the policy engine from a standalone script into a CI enforcement gate.
**Expected outcome:** The four GOV policies produce CI pass/fail signals; governance manifests that violate policy cannot merge.

### REC-5: Add Per-Finding Resolution Tracking to Review Registry
Extend `docs/reviews/review-registry.schema.json` to support `resolution_notes` and a `carried_forward_findings` array per entry. Populate `carried_forward_finding_ids` for the three reviews that carry forward the production code violation (RC-1, A-1, GA-008). Define a formal "closure" criterion: a review is Closed only when all of its findings are either resolved, formally deferred with a trigger, or superseded.
**Expected outcome:** Finding accumulation becomes visible; the review pipeline generates resolution pressure rather than institutional debt.

### REC-6: Expand Governance Conformance Checklist
Add the following items to `docs/governance-conformance-checklist.md`:
- Machine-readable governance declaration file present and pinned to current standards manifest versions
- Evaluation harness executed with pass/fail recorded (per eval/test-matrix.md)
- ADR review: every architecture decision is covered by an ADR or explicitly deferred
- CI-enforcement confirmation: artifact-boundary and review-artifact-validation workflows green
- System lifecycle gate: current gate status confirmed in system-status-registry
**Expected outcome:** The checklist becomes a complete pre-release gate; implementation repos have unambiguous compliance criteria.

### REC-7: Create ADRs for Subsequent Architecture Decisions
File ADRs for: (1) the governance manifest approach and policy engine model, (2) the Phase 1 enforcement strategy (declared identity + contract pins), (3) the schema authority designation (contracts/schemas/ canonical). Use `docs/adr/ADR-TEMPLATE.md`. Reference the specific review IDs and finding IDs that motivated each decision.
**Expected outcome:** The decision record covers the full development history; subsequent reviewers can trace the rationale for enforcement architecture choices.

---

## 9. Priority Classification

| Recommendation | Priority | Rationale |
| --- | --- | --- |
| REC-1: Governance declaration template + Phase 1 initiation | **Critical** | Prerequisite for all enforcement; blocks downstream repos from entering implementation in a governed state |
| REC-2: Extend boundary CI to cover implementation code | **Critical** | Repo cannot credibly require boundary compliance while its own boundary CI passes production code |
| REC-3: Designate canonical schema authority | **High** | Schema drift is the top identified cross-system failure mode; designation blocks divergent imports |
| REC-4: Wire policy engine to CI | **High** | Policy engine has zero enforcement value until wired; four policies are present but untriggered |
| REC-5: Per-finding resolution tracking | **Medium** | Review culture generates debt without closure; medium severity because enforcement is not blocked |
| REC-6: Expand conformance checklist | **Medium** | Checklist is the pre-release gate; incomplete gate allows releases that miss governance requirements |
| REC-7: Create ADRs for post-sprint decisions | **Low** | Decision record is incomplete but not blocking; decisions are traceable through review artifacts |

---

## 10. Extracted Action Items

### A-1: Create `contracts/governance-declaration.template.json`
- **Priority:** Critical
- **Source:** REC-1, G1
- **Owner:** Codex (Governance Execution Agent)
- **Expected artifact:** `contracts/governance-declaration.template.json` with complete field structure and SYS-001 example
- **Acceptance criteria:**
  - File exists at `contracts/governance-declaration.template.json`
  - Includes all required fields: `system_id`, `implementation_repo`, `architecture_source`, `contract_pins`, `schema_pins`, `rule_version`, `prompt_set_hash`, `evaluation_manifest_path`, `last_evaluation_date`, `external_storage_policy`, `governance_declaration_version`
  - SYS-001 example uses real contract versions from `contracts/standards-manifest.json`
  - `docs/governance-conformance-checklist.md` references the template in a new checklist item

### A-2: Update `docs/governance-enforcement-roadmap.md` to Mark Phase 1 Initiated
- **Priority:** Critical
- **Source:** REC-1, G1
- **Owner:** Codex
- **Expected artifact:** Updated `docs/governance-enforcement-roadmap.md` with Phase 1 marked as initiated
- **Acceptance criteria:**
  - Phase 1 section includes a "Status: Initiated" marker
  - References `contracts/governance-declaration.template.json` as the concrete template
  - Notes the date Phase 1 was initiated

### A-3: Extend `scripts/check_artifact_boundary.py` to Enforce Implementation Code Boundary
- **Priority:** Critical
- **Source:** REC-2, G2
- **Owner:** Codex
- **Expected artifact:** Updated `scripts/check_artifact_boundary.py` with implementation code detection
- **Acceptance criteria:**
  - Script flags Python packages outside `scripts/` with non-trivial `__init__.py`
  - Script flags root-level `run_*.py` scripts
  - `spectrum_systems/` would fail the updated check
  - Existing `scripts/` directory is in the allowlist and passes

### A-4: Designate Canonical Schema Authority in `schemas/README.md`
- **Priority:** High
- **Source:** REC-3, G3
- **Owner:** Codex
- **Expected artifact:** Updated `schemas/README.md` with canonical authority section; cross-reference in `CONTRACTS.md`
- **Acceptance criteria:**
  - `contracts/schemas/` is declared canonical for contract schemas
  - Root `schemas/` is declared supplemental for non-contract structural schemas
  - Migration path described for overlapping schemas
  - `CONTRACTS.md` references this designation

### A-5: Wire Policy Engine to Cross-Repo Compliance CI
- **Priority:** High
- **Source:** REC-4, R5
- **Owner:** Codex
- **Expected artifact:** Updated `.github/workflows/cross-repo-compliance.yml` invoking the policy engine
- **Acceptance criteria:**
  - Policy engine step runs against all example governance manifests
  - Workflow fails when any policy evaluation returns a non-pass result
  - Step output is human-readable (policy name, repo, pass/fail reason)

### A-6: Expand `docs/governance-conformance-checklist.md`
- **Priority:** Medium
- **Source:** REC-6, G5
- **Owner:** Codex
- **Expected artifact:** Updated `docs/governance-conformance-checklist.md` with five new items
- **Acceptance criteria:**
  - Machine-readable governance declaration item added
  - Evaluation harness completion item added
  - ADR review item added
  - CI-enforcement confirmation item added
  - System lifecycle gate item added

### A-7: Create ADRs for Post-Sprint Architecture Decisions
- **Priority:** Low
- **Source:** REC-7, G7
- **Owner:** Codex
- **Expected artifact:** Three new ADR files in `docs/adr/`
- **Acceptance criteria:**
  - ADR for governance manifest model and policy engine
  - ADR for Phase 1 enforcement strategy
  - ADR for schema authority designation
  - Each ADR follows `docs/adr/ADR-TEMPLATE.md` and references motivating review IDs

---

## 11. Blocking Items

1. **A-1 and A-2 are pre-conditions for Phase 1 activation.** No downstream implementation repo should begin governed implementation until the governance declaration template exists and Phase 1 is formally initiated.

2. **A-3 must be resolved before the self-governance credibility gap can close.** The production Python package cannot remain in the governance repo while Phase 1 enforcement is being activated; the contradiction would undermine the constitutional authority of the enforcement model.

---

## 12. Deferred Items

- **Compliance scanner deep upgrade (REC-4 full contract version validation):** Full Phase 2 enforcement (validating contract version pins against the registry) requires implementation repos to have filed governance declarations first. This is deferred until Phase 1 declarations exist in at least two implementation repos.
- **Per-finding resolution tracking schema extension (REC-5):** The review registry schema tests are comprehensive. Schema changes require test updates. Defer until Phase 1 and boundary CI actions are complete; the finding accumulation problem is tolerable at the current review cadence.

---

## 13. Top 5 Next Changes to Implement

1. **Create `contracts/governance-declaration.template.json`** — Initiates Phase 1; unblocks downstream compliance declarations; required by GA-007 from the 2026-03-14 governance review. This is the single highest-leverage artifact not yet created.

2. **Update `docs/governance-enforcement-roadmap.md`** — Mark Phase 1 as initiated and reference the template. Closes the gap between the declared roadmap and actual status.

3. **Update `docs/governance-conformance-checklist.md`** — Add the machine-readable governance declaration requirement and four other missing items. Gives implementation repos an unambiguous pre-release gate.

4. **Designate canonical schema authority in `schemas/README.md`** — Resolves the dual-track ambiguity that will cause import divergence at scale. Low effort, high prevention value.

5. **Add a "Carry-Forward Findings" ADR** — Document the production code boundary issue (RC-1/A-1/GA-008) as a formally tracked decision: either commit to removal with a date, or formally classify `spectrum_systems/` as an evaluation-only scaffold with explicit governance exemption.

---

## 14. What to Do Before the Next Review

- Complete A-1 (governance-declaration.template.json) and A-2 (Phase 1 roadmap update)
- Close at least two of the most recent review registry entries by resolving their blocking findings
- Confirm schema authority designation (A-4) in `schemas/README.md`
- Wire policy engine to CI (A-5) so GOV-001 through GOV-004 produce enforcement signals
- File ADR-006 documenting the governance manifest and policy engine architecture decision
- Resolve the production code situation (spectrum_systems/) or formally document the governance exemption

---

## 15. Signals That This Repo Is Ready for the Next Maturity Level

The following signals indicate advancement to **Level 3 (Governed)**:

- `contracts/governance-declaration.template.json` exists and at least one downstream repo has filed a declaration conforming to it
- Phase 1 is marked "Active" (not "Initiated") in `docs/governance-enforcement-roadmap.md`
- `scripts/check_artifact_boundary.py` detects and blocks production code additions
- `schemas/README.md` designates canonical schema authority
- Cross-repo compliance scanner invokes the policy engine (GOV-001 through GOV-004) in CI
- At least three open review registry entries are "Closed" with resolution notes
- `docs/governance-conformance-checklist.md` contains at least 15 items covering all governance domains

---

## 16. Tracked Artifact Follow-Through

The following findings should be converted into explicit design-review or governance artifacts to ensure advice becomes durable and actionable:

| Finding | Recommended Artifact | Target Path | Priority |
| --- | --- | --- | --- |
| F-1 (Phase 1 not initiated) | Governance declaration template | `contracts/governance-declaration.template.json` | Critical |
| F-1 (Phase 1 not initiated) | Enforcement roadmap update | `docs/governance-enforcement-roadmap.md` | Critical |
| F-2 (boundary CI gap) | Architecture Decision Record | `docs/adr/ADR-006-implementation-boundary-enforcement.md` | High |
| F-3 (production code violation) | Formal resolution in DECISIONS.md + implementation-boundary.md | `DECISIONS.md`, `docs/implementation-boundary.md` | High |
| F-4 (schema dual-track) | Schema authority designation | `schemas/README.md`, `CONTRACTS.md` | High |
| F-5 (compliance scanner gap) | CI workflow update | `.github/workflows/cross-repo-compliance.yml` | High |
| F-6 (finding accumulation) | Review registry schema extension with `carried_forward_findings` | `docs/reviews/review-registry.schema.json` | Medium |
| F-7 (incomplete checklist) | Conformance checklist expansion | `docs/governance-conformance-checklist.md` | Medium |
| G7 (ADR gaps) | Three new ADRs for post-sprint decisions | `docs/adr/ADR-006` through `ADR-008` | Low |

**Governance artifacts that must exist before the next review to maintain institutional continuity:**

1. `contracts/governance-declaration.template.json` — the artifact that converts Phase 1 from description to reality
2. An ADR for the governance manifest and policy engine model (GOV-001 through GOV-004) — these represent the most significant architectural decision not yet recorded
3. A formal resolution entry in `DECISIONS.md` for the `spectrum_systems/` production code question — three reviews have found the violation; the decision record should show the resolution intent

**Tracking recommendation:** Add these three artifacts to the `design-reviews/2026-03-16-governance-constitution-deep-review.actions.json` file so the CI ingest workflow creates GitHub issues for each, ensuring the follow-through is machine-tracked and not dependent on manual triage.

---

*Review complete. Actions registered in `docs/review-actions/2026-03-16-governance-constitution-deep-review-actions.json` and `design-reviews/2026-03-16-governance-constitution-deep-review.actions.json`.*
