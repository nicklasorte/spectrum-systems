# Governance Architecture Review: spectrum-systems

**Date:** 2026-03-15
**Reviewer:** Claude (Principal Systems Architect — Opus 4.6)
**Scope:** Full governance and architecture audit — does this repository function as a constitutional governance layer for a multi-repository ecosystem, or does it merely document rules without effectively enforcing them?
**Review Type:** Constitutional governance effectiveness audit
**Finding IDs:** [F-1], [F-2], [F-3], [F-4], [F-5], [F-6], [F-7], [F-8], [F-9], [F-10], [F-11], [F-12]

---

## Executive Summary

**Does this repository function as a real constitutional governance layer?**

Partially. spectrum-systems has made significant progress toward constitutional governance — it has strong contract definitions, a well-designed review artifact system with schema validation, CI-enforced artifact integrity checks, and a clear layered architecture model. The conceptual governance design is substantially ahead of most repositories at this scale.

However, the governance model has a fundamental structural asymmetry: **it governs itself more effectively than it governs the ecosystem it claims authority over.** The CI pipelines, pytest suites, and artifact validation scripts all operate within spectrum-systems itself. Cross-repo governance exists only as a manually-invoked scanner that checks for file presence — it cannot detect contract drift, schema version mismatches, or architectural violations in downstream engines.

The repository is at **maturity level 2.5 (Structured, approaching Governed)**. It has the vocabulary, schemas, and design-review discipline of a level-3 system, but the enforcement machinery to actually prevent downstream deviation does not yet exist. The gap between documented governance and enforced governance is the single most important architectural risk.

Three findings define the current state:

1. **[F-1] The compliance scanner is structurally insufficient.** It checks for file existence (`README.md`, `CLAUDE.md`, `CODEX.md`, `SYSTEMS.md`, `docs/`, `tests/`) but cannot validate contract version pins, schema compatibility, or governance rule adherence. This is a presence check, not a compliance check.

2. **[F-2] The ecosystem registry is incomplete.** Only 4 of 8 governed repositories appear in `ecosystem/ecosystem-registry.json`. The four Layer 3 operational engines — `comment-resolution-engine`, `working-paper-review-engine`, `meeting-minutes-engine`, `docx-comment-injection-engine` — are absent from the authoritative registry.

3. **[F-3] The repository violates its own boundary rule.** `spectrum_systems/study_runner/` contains production pipeline code (`pipeline.py`, `run_study.py`, `artifact_writer.py`, `load_config.py`) in a repository whose CLAUDE.md states "This repository should NOT contain production implementation code." This is a previously-identified finding (RC-1 in the 2026-03-15 constitution audit) that remains unresolved.

---

## Architectural Strengths

### 1. Design Review Artifact System — Well Architected
The dual-artifact review system (paired markdown + `.actions.json`) is the strongest governance mechanism in the repository. Key properties:

- **Schema-backed validation**: `claude-review.schema.json` enforces structure on findings, recommendations, actions, gaps, and risks with deterministic ID patterns (`F-#`, `G#`, `R#`, `REC-#`, `A-#`).
- **Cross-artifact integrity**: CI and validation scripts (`validate-review-artifacts.js`) enforce ID alignment between markdown and JSON artifacts, prevent duplicates, and validate date formats.
- **Automation bridge**: `ingest-claude-review.js` can translate `create_issue: true` findings into GitHub issues with labels, target repos, and structured bodies — connecting review findings to the issue tracker.
- **Follow-up scheduling**: Actions carry `due_date` and `follow_up_trigger` fields that mirror into the review registry for checkpoint tracking.

This is ecosystem-grade design review infrastructure. The schema is strict (`additionalProperties: false`), IDs are deterministic, and the automation pipeline from review to issue creation is complete.

### 2. Contract System — Comprehensive and Machine-Operable
- 16 artifact contracts with JSON schemas, example payloads, and programmatic validation via `spectrum_systems.contracts`.
- Standards manifest (`contracts/standards-manifest.json`) tracks versions, intended consumers, status, and introduction history.
- Versioning policy (`CONTRACT_VERSIONING.md`) defines semver semantics with clear breaking-change criteria.
- Test coverage: `test_contracts.py` validates all 15 example payloads against schemas, checks required version fields, and verifies contract registry completeness.

### 3. CI Enforcement — Present and Effective Where Deployed
Four CI workflows provide real enforcement:

- **`artifact-boundary.yml`**: Blocks prohibited binary artifacts and oversized files on push/PR to `main`, `release/**`, `codex/**`. Also runs pytest.
- **`review-artifact-validation.yml`**: Validates design review artifact pairs on changes to `design-reviews/`.
- **`claude-review-ingest.yml`**: Validates and ingests `.actions.json` files, creating GitHub issues for marked findings.
- **`ssos-project-automation.yml`**: Syncs issues to project boards with lifecycle state tracking.

### 4. Architectural Documentation — High Quality
- Ecosystem architecture is clearly documented with layer definitions, Mermaid diagrams, and governance flow descriptions.
- Per-system design documents in `systems/` provide consistent structure (overview, design, interface, evaluation, prompts) for all 9 systems.
- ADR framework exists with a template and initial decision record.
- Review registry provides a central ledger with follow-up scheduling.

### 5. Governance Triage System — Thoughtful
The triage rule (`docs/governance-triage-rule.md`) prevents issue fragmentation by defining criteria for standalone issues vs. merging into workstream buckets. This is a mature governance practice rarely seen at this scale.

---

## Structural Weaknesses

### [F-1] Cross-Repo Compliance Scanner Is a File-Presence Check, Not a Governance Validator
**Severity: High**

The compliance scanner (`governance/compliance-scans/run-cross-repo-compliance.js`) checks for:
- Required files: `README.md`, `CLAUDE.md`, `CODEX.md`, `SYSTEMS.md`
- Required directories: `docs/`, `tests/`
- README content containing "spectrum-systems"
- Presence of GitHub workflow files

It does **not** check:
- Whether the repo pins to a specific contract version from `standards-manifest.json`
- Whether schemas consumed by the repo are compatible with the published versions
- Whether required CI workflows match the governance templates
- Whether CLAUDE.md/CODEX.md contain required governance sections
- Whether the repo's declared `system_id` matches the ecosystem registry
- Whether evaluation harnesses exist for the declared system

This means a downstream repo can have all the right filenames while implementing entirely incompatible contracts. The scanner provides compliance theater, not compliance assurance.

### [F-2] Ecosystem Registry Is Incomplete
**Severity: High**

`ecosystem/ecosystem-registry.json` lists 4 repositories:
1. `spectrum-systems` (governance)
2. `system-factory` (template)
3. `spectrum-pipeline-engine` (operational_engine, planned)
4. `spectrum-program-advisor` (advisory, experimental)

Missing from the registry:
- `comment-resolution-engine`
- `working-paper-review-engine`
- `meeting-minutes-engine`
- `docx-comment-injection-engine`

These are the four core Layer 3 operational engines — the primary consumers of governed contracts. A constitution that does not enumerate its governed entities in its authoritative registry has a fundamental data integrity problem.

### [F-3] Self-Governance Boundary Violation (Previously Identified, Unresolved)
**Severity: Critical**

`spectrum_systems/study_runner/` contains production code:
- `pipeline.py`, `run_study.py`, `artifact_writer.py`, `load_config.py`
- `run_study.py` also exists at the repo root

The artifact boundary check (`scripts/check_artifact_boundary.py`) only bans binary file extensions (`.pdf`, `.docx`, etc.) and oversized files. It has no mechanism to detect Python production code. This finding was already identified as RC-1 in the prior constitution audit but remains open.

### [F-4] Dual Schema Authority Creates Confusion
**Severity: Medium**

Schemas exist in two locations:
- `schemas/` — Contains 12 schemas: `study-output-schema.json`, `issue-schema.json`, `diagnostics.schema.json`, `compiler-manifest.schema.json`, `assumption-schema.json`, `repository-metadata.schema.json`, `artifact-bundle.schema.json`, `provenance-schema.json`, `comment-schema.json`, `precedent-schema.json`, plus 5 data-lake schemas.
- `contracts/schemas/` — Contains 16 contract schemas that are validated by `test_contracts.py` and tracked in `standards-manifest.json`.

The `schemas/` directory schemas are **not** registered in the standards manifest, are **not** validated by tests, and have **no** version tracking. It is unclear which schemas are authoritative for downstream consumption and which are internal/draft artifacts.

### [F-5] No Automated Contract Consumer Tracking
**Severity: Medium**

The standards manifest declares `intended_consumers` for each contract (e.g., `working-paper-review-engine`, `comment-resolution-engine`), but there is no mechanism to verify that those consumers:
1. Actually import and use the declared contract version
2. Haven't forked or redefined the schema locally
3. Pass validation against the canonical schema

This is a declaration without verification — a governance IOU.

---

## Enforcement Gaps

### [F-6] Governance Enforcement Roadmap Is Entirely Unstarted
**Severity: High**

`docs/governance-enforcement-roadmap.md` describes a 4-phase enforcement model:
- Phase 1: Declared identity and contract pins
- Phase 2: Automated validation of schema/contract versions
- Phase 3: CI-based conformance checks across repos
- Phase 4: Ecosystem-level contract compatibility validation

All four phases are documented but zero are implemented. The gap between "governance is documented" and "governance is enforced" is the single largest structural risk in the ecosystem.

### [F-7] No Cross-Repo CI
**Severity: High**

All CI workflows run exclusively within spectrum-systems. No CI workflow triggers on changes in downstream repos to validate governance compliance. Downstream repos can:
- Remove governance files
- Modify schemas without updating versions
- Implement contracts incorrectly
- Skip evaluation harnesses

All of these violations will be invisible to spectrum-systems until someone manually runs the compliance scanner.

### [F-8] Artifact Boundary Check Cannot Detect Code Violations
**Severity: Medium**

`scripts/check_artifact_boundary.py` bans binary extensions and enforces file size limits but cannot detect:
- Python source files that constitute production code
- JavaScript modules that should live in implementation repos
- Any content-based boundary violation

The check is structurally incapable of enforcing the repository's stated "no production code" rule.

### [F-9] Review-to-Issue Pipeline Requires Manual Triggering for Cross-Repo Issues
**Severity: Medium**

`ingest-claude-review.js` can create issues in target repos via `target_repo` fields, but this requires:
- `GITHUB_TOKEN` with cross-repo issue creation permissions
- Manual configuration of the correct `target_repo` in each finding
- No deduplication logic for previously created issues

The pipeline works for self-repo issue creation but lacks robustness for ecosystem-scale issue management.

---

## Cross-Repo Governance Assessment

### What Works
- **Contract definitions** are centralized and comprehensive. Downstream repos have a single authoritative source for schemas.
- **Standards manifest** provides a machine-readable contract registry with version tracking and consumer declarations.
- **system-factory** is designed to scaffold governance primitives into new repos, providing governance-by-default for greenfield repositories.
- **Design review system** produces actionable artifacts that can route findings to the correct downstream repo.

### What Does Not Work
- **No pull-based governance**: Downstream repos are not required to pull or validate their governance baseline from spectrum-systems. Governance propagation is push-only through system-factory scaffolding, which is a one-time event.
- **No continuous compliance**: After initial scaffolding, there is no mechanism to detect or prevent governance drift. A downstream repo that modifies its CLAUDE.md, removes its CODEX.md, or redefines schemas locally will not be flagged.
- **No contract consumption verification**: The manifest declares intended consumers but cannot verify actual consumption.
- **Incomplete registry**: 50% of operational engines are missing from the ecosystem registry, making the registry unreliable as a source of truth.

### Assessment
The cross-repo governance model is **aspirational but not yet operational**. The architecture for cross-repo governance is well-designed on paper (enforcement roadmap, compliance scanner concept, system-factory propagation), but the implementation has not progressed beyond file-presence checks and one-time scaffolding.

---

## Scalability Risks

### [F-10] Manual Compliance Scanning Cannot Scale Beyond 5-7 Repos
**Severity: High**

The compliance scanner requires:
- Local checkouts of all repos in adjacent directories
- Manual invocation via CLI
- Manual review of JSON output

At 15-30 repositories, this process will be abandoned. The scanner must be automated in CI with scheduled runs and notification on drift.

### [F-11] Schema Dual-Track Will Create Version Confusion at Scale
**Severity: Medium**

With `schemas/` and `contracts/schemas/` coexisting, new team members and AI agents will inevitably reference the wrong schema source. As the ecosystem grows, this ambiguity will compound into schema version mismatches across repos.

### [F-12] Review Registry Is a Flat Markdown Table
**Severity: Medium**

The review registry (`docs/review-registry.md`) tracks reviews in a markdown table. At 15-30 repos with quarterly reviews, this table will contain 60-120 rows within two years. Markdown tables do not support:
- Filtering by status, repo, or date
- Automated status updates
- Overdue item detection
- Integration with issue trackers

The registry should evolve into a machine-readable format (JSON) with CI-driven status checks.

---

## Recommended Structural Improvements

### Priority 1 — Close the Self-Governance Gap
1. **Resolve the production code boundary violation** (RC-1): Relocate `spectrum_systems/study_runner/` to a dedicated engine repo. Keep `spectrum_systems/contracts/` only if it's reframed as a governance SDK, or inline the schema-loading logic directly in tests.
2. **Extend artifact boundary checks** to detect Python source files that violate the "no production code" rule.

### Priority 2 — Make the Ecosystem Registry Authoritative
3. **Add all 8 governed repositories** to `ecosystem/ecosystem-registry.json` with accurate `repo_type`, `status`, and `contracts` fields.
4. **Add a `contracts` field** to each registry entry listing the contract names consumed by that repo — this creates a machine-readable dependency graph.
5. **Add CI validation** that cross-references the ecosystem registry against `contracts/standards-manifest.json` intended consumers.

### Priority 3 — Implement Phase 1 Enforcement
6. **Require downstream repos to declare contract pins** in a machine-readable manifest (e.g., `governance.json` or `.spectrum-systems.json`).
7. **Extend the compliance scanner** to validate contract pins against the standards manifest.
8. **Run the compliance scanner in CI on a schedule** (weekly or on-push to `main`) and fail on non-compliance.

### Priority 4 — Resolve Schema Authority
9. **Consolidate or clearly differentiate** `schemas/` and `contracts/schemas/`. Either move all authoritative schemas into `contracts/schemas/` with manifest tracking, or explicitly document `schemas/` as "internal/draft schemas not for downstream consumption."
10. **Add schema validation tests** for the `schemas/` directory if those schemas are intended for external use.

### Priority 5 — Evolve the Review Registry
11. **Create a machine-readable review registry** (`docs/reviews/review-registry.json`) alongside the markdown table, with CI validation of status and due dates.
12. **Add CI to flag overdue review actions** by comparing `due_date` fields against the current date.

---

## Ecosystem Maturity Assessment

**Rating: 2.5 — Structured (approaching Governed)**

| Level | Label | Description | Status |
|-------|-------|-------------|--------|
| 1 | Ad hoc | No governance structure | Passed |
| 2 | Organized | Governance documented, contracts defined, reviews conducted | **Current** |
| 3 | Governed | Governance enforced via automation, drift detected, compliance verified | **Not yet reached** |
| 4 | Ecosystem-grade | Cross-repo contract compatibility validation, automated compliance | Future |
| 5 | Platform-grade | Self-healing governance, automated migration, policy-as-code | Aspirational |

**Rationale for 2.5:**
- The repository has clearly surpassed level 2: contracts are comprehensive, versioned, and tested; design reviews are schema-validated with paired artifacts; CI enforces artifact integrity within the repo.
- However, it has not reached level 3: cross-repo enforcement does not exist; the compliance scanner is superficial; the governance enforcement roadmap is entirely unstarted; the ecosystem registry is incomplete; the repo violates its own boundary rule.
- The half-point reflects that the infrastructure for level 3 is partially built (review-to-issue pipeline, compliance scanner skeleton, enforcement roadmap design) but not operational.

---

## Next Architectural Moves

To advance from level 2.5 to level 3 (Governed):

1. **Resolve self-governance violations** — Remove production code, extend boundary checks. This is a credibility prerequisite.
2. **Complete the ecosystem registry** — All 8 repos must appear with accurate metadata and contract consumption declarations.
3. **Implement Phase 1 of the enforcement roadmap** — Require downstream repos to declare contract pins; validate them against the standards manifest.
4. **Automate compliance scanning** — Run the (enhanced) scanner in CI on a schedule; publish compliance reports as artifacts.
5. **Consolidate schema authority** — Eliminate the dual-track schema ambiguity.
6. **Machine-readable review registry** — Replace or supplement the markdown table with a JSON registry that CI can validate.

These six moves would credibly advance the ecosystem to maturity level 3 (Governed). Levels 4 and 5 require cross-repo CI integration and contract compatibility validation, which are Phase 3 and Phase 4 of the existing enforcement roadmap.

---

## Prior Review Reconciliation

This audit identifies overlap with the 2026-03-15 constitution audit. Key prior findings and their current status:

| Prior Finding | Status | This Review |
|---|---|---|
| RC-1: Production code in governance repo | Open/Unresolved | Reaffirmed as [F-3] |
| RC-4: Phase 1 enforcement unstarted | Open/Unresolved | Reaffirmed as [F-6] |
| Ecosystem registry incomplete | Open/Unresolved | Reaffirmed as [F-2] |
| Dual schema authority | Previously noted | Elevated to [F-4] |

New findings in this review: [F-1] (scanner insufficiency), [F-5] (consumer tracking), [F-7] (no cross-repo CI), [F-8] (boundary check limitation), [F-9] (review-to-issue pipeline gaps), [F-10] (scanner scalability), [F-11] (schema dual-track at scale), [F-12] (registry format).
