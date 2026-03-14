# Systems Architecture Review: Spectrum Systems as Ecosystem Constitution

**Date:** 2026-03-14
**Reviewer:** Claude (Reasoning Agent)
**Scope:** Full repository evaluated as the governing constitution for a multi-repo ecosystem comprising `system-factory`, `spectrum-systems`, `working-paper-review-engine`, `comment-resolution-engine`, `docx-comment-injection-engine`, `spectrum-pipeline-engine`, `meeting-minutes-engine`, and `spectrum-program-advisor`.

---

## Executive Summary

`spectrum-systems` is architecturally well-founded: the contract czar model is sound, the versioning policy is specific, and the per-system documentation pattern is consistent. The repo earns its role as a governance layer. However, it governs only the systems it has explicitly modeled — and four of the eight ecosystem repos have no corresponding design coverage here. The most critical gap is `spectrum-pipeline-engine`, which appears as an intended consumer of nine contracts but is completely unmodeled. Until the governance layer covers the full ecosystem, downstream repos cannot reliably derive their obligations from this repo alone.

---

## 1. Strengths

### S-1: Contract Czar Model Is Explicit and Enforceable

`CONTRACTS.md` clearly declares `spectrum-systems` as the czar repo: contracts must be published here before `system-factory` scaffolds them elsewhere; downstream engines must import rather than redefine. The `pdf_anchored_docx_comment_injection_contract` section even uses precise normative language ("Engines must verify PDF anchors… fail loudly on ambiguity… preserve the source DOCX"). This level of specificity makes the contract enforceable in downstream implementation reviews.

### S-2: Machine-Readable Contract Registry

`contracts/standards-manifest.json` is a proper machine-readable registry with 16 contracts, each carrying `schema_version`, `status`, `intended_consumers`, `introduced_in`, `last_updated_in`, `example_path`, and `notes`. `system-factory` can mirror these into scaffolded repos deterministically. This is the right structural foundation for a governance layer.

### S-3: Versioning Policy Is Specific and Actionable

`CONTRACT_VERSIONING.md` defines semver (`MAJOR.MINOR.PATCH`) semantics, distinguishes breaking from non-breaking changes with concrete examples, and specifies publication rules (manifest + changelog + docs must update together). Downstream repos have unambiguous guidance on pinning strategy.

### S-4: System Lifecycle Gate Model

`docs/system-lifecycle.md` defines a nine-stage gate from problem definition through operationalization. Each gate has a defined artifact requirement. The status registry (`docs/system-status-registry.md`) tracks all six systems against this lifecycle. This prevents systems from entering implementation without governance coverage.

### S-5: Per-System Documentation Pattern Is Consistent

All six defined systems carry `overview.md`, `interface.md`, `design.md`, `evaluation.md`, and `prompts.md` under `systems/<system>/`. The five-document structure is a real composability advantage: implementation engineers can read `interface.md` alone to understand what to build without reading the entire repo.

### S-6: Bottleneck-Driven Design Traceability

BN-001 through BN-005 map explicitly to SYS-001 through SYS-006 across `bottleneck-map.md`, `system-map.md`, and `SYSTEMS.md`. The system-map table also records upstream/downstream workflow relationships. This is the kind of explicit rationale linking that makes a governance repo defensible when scope questions arise.

### S-7: Implementation Boundary Is Formalized

`docs/implementation-boundary.md` correctly separates what this repo owns (specs, schemas, error taxonomy, prompts, rule packs) from what implementation repos own (code, runtime config, connectors). The requirement that implementation repos declare their `system_id` and targeted spec/schema versions is the right mechanism for traceability across the boundary.

### S-8: Error Taxonomy and Rule Packs Are Present

`docs/error-taxonomy.md` and `rules/comment-resolution/` (canonical terms, disposition rules, drafting rules, issue patterns, validation rules, profiles) are architecture-level assets that implementation repos can inherit directly. These reduce per-repo divergence in error handling and rule application, which is a durable governance benefit.

### S-9: Prior Review Findings Are Partially Addressed

The 2026-03-13 review identified seven missing architectural components (MAC-1 through MAC-7). Several have since been resolved: `CONTRACT_VERSIONING.md` addresses MAC-3 (schema versioning), `docs/error-taxonomy.md` addresses MAC-4, `docs/system-interface-spec.md` addresses MAC-5, and `docs/schema-governance.md` provides additional coverage. The repo is actively incorporating review feedback.

---

## 2. Structural Gaps

### G-1: Four Ecosystem Repos Have No Governance Coverage (Critical)

The following repos appear in contract `intended_consumers` or are referenced in governance docs but have no corresponding system design, bottleneck mapping, or lifecycle status in this repo:

| Repo | Referenced In | Missing |
|---|---|---|
| `spectrum-pipeline-engine` | 9 contract `intended_consumers`; `SYSTEMS.md` contract layer note; `system-map.md` SYS-006 workflow note | System design, BN-link, workflow spec, interface, eval, failure modes |
| `working-paper-review-engine` | `CONTRACTS.md` (czar-governed); 3 contract `intended_consumers` | System design, BN-link, interface, schemas, eval |
| `docx-comment-injection-engine` | `pdf_anchored_docx_comment_injection_contract` intended_consumers | System design, interface, schemas, eval |
| `system-factory` | `CONTRACT_VERSIONING.md`; `new-repo-checklist.md`; all contract intended_consumers | System design, interface, governance spec |

None of these repos can determine their governance obligations from this repo — they are not modeled here. A downstream team reading `spectrum-systems` would not know that `spectrum-pipeline-engine` is expected to consume nine contracts, or that `working-paper-review-engine` is the upstream producer of comment matrices.

### G-2: `spectrum-pipeline-engine` Is the Invisible Critical Path (Critical)

`spectrum-pipeline-engine` is named as an `intended_consumer` for: `meeting_agenda_contract`, `meeting_minutes`, `comment_resolution_matrix_spreadsheet_contract`, `program_brief`, `study_readiness_assessment`, `next_best_action_memo`, `decision_log`, `risk_register`, `assumption_register`, and `milestone_plan`. That is ten contracts. It appears to be the orchestration layer that sequences upstream engines into downstream briefs — the most cross-cutting component in the ecosystem. Yet there is no bottleneck for it, no system ID, no interface, no workflow spec, and no failure mode analysis. If this engine fails or diverges from contracts, it propagates errors across the entire pipeline. The governance layer must model it.

### G-3: SYS-006 Has No Workflow Spec

`docs/system-map.md` explicitly marks Meeting Minutes Engine's workflow spec as "(workflow spec forthcoming)". All other systems have workflow files under `workflows/`. This is an acknowledged gap that should be closed before `meeting-minutes-engine` implementation begins, since the workflow spec defines the processing pipeline that `spectrum-pipeline-engine` will orchestrate.

### G-4: Evaluation Test Matrix Only Covers SYS-001 Through SYS-004

`eval/test-matrix.md` has entries for SYS-001 through SYS-004 only. SYS-005 (Spectrum Program Advisor) and SYS-006 (Meeting Minutes Engine) are not in the matrix. Their evaluation content is embedded inside `systems/<system>/evaluation.md` rather than under `eval/`, which is inconsistent with the harness pattern. The eval directory has no `eval/spectrum-program-advisor/` or `eval/meeting-minutes-engine/` folders.

### G-5: `implementation-boundary.md` Only Maps SYS-001

The implementation boundary document introduces the right concept — implementation repos must declare their targeted `system_id`, spec, schema, provenance, error taxonomy, and rule versions — but only provides a concrete mapping for SYS-001 (Comment Resolution Engine). SYS-002 through SYS-006 have no boundary mapping. This means implementation repos for those systems have no formal declaration requirement and no canonical reference for what to consume.

### G-6: System Failure Modes Only Cover SYS-001 Through SYS-004

`docs/system-failure-modes.md` system-specific section covers SYS-001 through SYS-004. SYS-005 (Spectrum Program Advisor) and SYS-006 (Meeting Minutes Engine) have no documented failure modes. SYS-005 in particular has complex dependencies (seven canonical inputs) where failure propagation paths are non-trivial.

### G-7: Schema Dual-Track Creates Ambiguity

Root `schemas/` contains nine minimal schemas (comment, issue, provenance, assumption, study-output, precedent, compiler-manifest, artifact-bundle, diagnostics) with 10–13 fields. `contracts/schemas/` contains fifteen fuller schemas with provenance coverage and example payloads. There is no formal document explaining which schemas are the canonical source, which are legacy, which serve different consumers, or the intended migration path between the two locations. `schemas/README.md` exists but does not address this relationship.

### G-8: `AGENTS.md` Is Vestigial

`AGENTS.md` is 12 lines: five rules and a five-step development cycle. `CLAUDE.md` and `CODEX.md` are both comprehensive (100+ lines each) with specific responsibilities, task scopes, and interaction models. `AGENTS.md` provides no additional value over the two agent-specific files and does not reflect the ecosystem's actual agent architecture. It should either be significantly expanded or consolidated.

### G-9: Schema Versioning Format Is Inconsistent

`docs/schema-governance.md` defines versions as `MAJOR.MINOR`. `CONTRACT_VERSIONING.md` defines versions as `MAJOR.MINOR.PATCH`. Both documents govern the same schema assets. The two-part vs three-part version format creates ambiguity when downstream repos try to pin versions or automate compatibility checks.

### G-10: Roadmap Does Not Reflect Current State

`docs/roadmap.md` lists Phase 1 as "schemas + comment resolution engine + transcript extraction engine." Phase 2 lists "study artifact generator + automated spectrum study pipelines." But SYS-003 through SYS-006 are already designed. The roadmap is not synchronized with the systems registry and does not reflect the current phase. A new engineer reading the roadmap will form an incorrect picture of where the ecosystem is in its development.

---

## 3. Risk Areas

### R-1: No Governance Enforcement Mechanism

The entire governance model is enforced by documentation convention. There is no CI/CD check that validates downstream repos against contract versions, no automated schema validation harness that runs against the manifested contracts, and no conformance test suite that an engine repo can run against `spectrum-systems` to verify it is implementing contracts correctly. When `spectrum-pipeline-engine` is built, it will have consumed ten contracts with no mechanical check that it is doing so correctly.

**Risk level:** High — the governance regime is real but entirely manual.

### R-2: `spectrum-pipeline-engine` Has No Governance Anchor

Because `spectrum-pipeline-engine` is unmodeled, its builder has no system design to derive from, no bottleneck linkage to validate scope, and no interface spec to constrain implementation. It will be built against individual contract docs rather than against a system-level governance document, creating a high risk of scope creep, incorrect contract interpretation, or missing failure modes.

**Risk level:** High — this is the highest-risk single gap in the ecosystem.

### R-3: No Cross-Repo Dependency Declaration Standard

`docs/implementation-boundary.md` requires implementation repos to declare `system_id`, spec, schema, and rule versions — but this standard is only applied to SYS-001. There is no enforcement mechanism, no registry of which implementation repos have filed these declarations, and no automated check that pins are current. Schema version drift (identified as the top cross-system failure mode in `docs/system-failure-modes.md`) is therefore undetectable until runtime.

**Risk level:** High — schema drift is a known failure mode with no detective control.

### R-4: No Change Request or Coordination Process for Breaking Changes

`CONTRACT_VERSIONING.md` states that "a new MAJOR requires coordinated updates to dependent schemas, prompts, workflows, and evaluators before adoption." But there is no defined process for how that coordination happens: no RFC template, no required review period, no registry of which engines would be affected, and no rollback plan. When the first breaking schema change occurs, coordination will be ad hoc.

**Risk level:** Medium — breaking changes have not yet occurred but are inevitable once implementation begins.

### R-5: Production Code Present in Design-First Repo

`spectrum_systems/` is a Python package containing a `study_runner/` subpackage with `pipeline.py`, `run_study.py`, `artifact_writer.py`, and `load_config.py`. `run_study.py` exists at the root level. `CLAUDE.md` explicitly states "This repository should NOT contain production implementation code." This creates a governance precedent gap: if this repo contains a Python runtime, the boundary between governance layer and implementation becomes ambiguous to downstream engineers.

**Risk level:** Medium — not blocking, but undermines the design-first philosophy and may invite scope creep.

### R-6: No Deprecation Timeline for Schemas

`CONTRACT_VERSIONING.md` states that "deprecated fields stay documented until the next MAJOR." But there is no policy governing when fields are marked deprecated, how long the deprecated-but-present window lasts in practice, or how downstream consumers are notified of upcoming removals. Without a deprecation calendar, consumers cannot plan migrations.

**Risk level:** Medium — not yet active since all schemas are at 1.0.x, but will matter on first deprecation.

### R-7: Eval Harnesses Lack Concrete Test Data for SYS-001 Through SYS-003

The 2026-03-13 review identified this (SRI-4): each `eval/*/README.md` defines criteria but contains minimal labeled test data. `eval/comment-resolution/fixtures/fixtures.yaml` exists but the broader `eval/study-artifacts/` and `eval/transcript-to-issue/` directories are scaffold-only. Without labeled fixtures, the evaluation harnesses cannot block regressions and the "blocking failures" in `eval/test-matrix.md` are aspirational rather than enforced.

**Risk level:** Medium — evaluation rigor is the stated foundation of the governance model; empty harnesses hollow it out.

---

## 4. Recommended Additions to the Repository

The following additions would materially advance `spectrum-systems`' role as a stable ecosystem constitution. Recommendations are ordered by impact.

---

### REC-1: Add a `docs/ecosystem-map.md` (Priority: Critical)

Create a single authoritative document showing every repo in the ecosystem, its role, the contracts it produces, the contracts it consumes, and its current implementation status. Include a simple diagram (ASCII or Mermaid) showing data flow between repos. This document does not need to duplicate system designs; its purpose is to make the full ecosystem legible at a glance so that any engineer can determine where their repo sits in the dependency graph.

Minimum table structure:
```
| Repo | Role | Produces Contracts | Consumes Contracts | System ID | Implementation Status |
```

---

### REC-2: Add `systems/spectrum-pipeline-engine/` Design (Priority: Critical)

Create a system design entry for `spectrum-pipeline-engine` covering: bottleneck addressed, interface spec (inputs from upstream engines, outputs to program advisors and agenda generators), workflow spec under `workflows/spectrum-pipeline-engine.md`, failure modes, and evaluation plan. This is the highest-priority single addition because this repo is already a consumer of 10 contracts with no governance anchor.

At minimum, add a stub to `SYSTEMS.md` with a system ID, link the repo in `contracts/standards-manifest.json`'s `intended_consumers` fields to a formal system entry, and add a row to `docs/system-status-registry.md`.

---

### REC-3: Model `working-paper-review-engine` and `docx-comment-injection-engine` as Systems (Priority: High)

Both repos are named in contract manifests as producers or consumers but have no system designs. Add entries for each:
- `working-paper-review-engine`: produces `working_paper_input`, `reviewer_comment_set`, `comment_resolution_matrix`; upstream of Comment Resolution Engine. Assign a system ID (SYS-007 suggested) and add `systems/working-paper-review-engine/` docs.
- `docx-comment-injection-engine`: consumes `pdf_anchored_docx_comment_injection_contract`; produces annotated DOCX outputs. Assign SYS-008 and add `systems/docx-comment-injection-engine/` docs.

---

### REC-4: Add `systems/system-factory/` Governance Spec (Priority: High)

`system-factory` is the repo generator that mirrors contracts into scaffolded repos. Its behavior directly determines whether downstream repos inherit correct governance. Add a governance spec defining: which files it must emit (CLAUDE.md, CODEX.md, contract stubs), which contract versions it mirrors, how it validates against `contracts/standards-manifest.json`, and what a new repo must declare to satisfy `docs/implementation-boundary.md`. This need not be a full system design — a governance spec under `docs/system-factory-governance.md` is sufficient.

---

### REC-5: Complete `docs/implementation-boundary.md` for SYS-002 Through SYS-006 (Priority: High)

Extend `docs/implementation-boundary.md` with explicit mapping sections for each system:
- Architecture source (always `spectrum-systems`)
- Implementation repo name
- Spec path (`systems/<system>/interface.md`)
- Canonical schemas consumed
- Rule pack (if any)
- Evaluation assets path

This is the governance layer's primary mechanism for telling implementation engineers what to consume. It is currently only operative for SYS-001.

---

### REC-6: Add `workflows/meeting-minutes-engine.md` (Priority: High)

The Meeting Minutes Engine (SYS-006) is the only system without a workflow spec. The spec should define the processing pipeline (transcript ingestion → speaker/timestamp parsing → structured minutes generation → validation against `meeting_minutes_contract.yaml` → DOCX rendering → validation report emission) and its interfaces to `spectrum-pipeline-engine` for downstream agenda generation.

---

### REC-7: Add SYS-005 and SYS-006 to `eval/test-matrix.md` and Create `eval/` Harness Directories (Priority: High)

Move SYS-005 and SYS-006 evaluation content from `systems/<system>/evaluation.md` into `eval/spectrum-program-advisor/README.md` and `eval/meeting-minutes-engine/README.md` respectively, and add rows to `eval/test-matrix.md`. Maintain `systems/<system>/evaluation.md` as a summary with a link to the `eval/` harness. This preserves the consistent evaluation pattern established for SYS-001 through SYS-004.

---

### REC-8: Add SYS-005 and SYS-006 to `docs/system-failure-modes.md` (Priority: High)

SYS-005 (Spectrum Program Advisor) takes seven inputs across program state. Key failure modes include: stale or missing input artifacts causing incorrect readiness scores; dependency graph cycles in milestone/decision/risk linkages; inconsistent field normalization across different canonical inputs. SYS-006 failure modes include: timestamp/speaker data absent from transcripts; template parity drift between contract and DOCX renderer; minutes fields added by downstream engines violating the "no extra fields" contract rule.

---

### REC-9: Add a `docs/change-request-process.md` (Priority: Medium)

Define the process for proposing contract changes:
1. Who can propose (any repo contributor; czar team reviews)
2. Required RFC content (affected contracts, breaking/non-breaking classification, migration path, affected downstream repos)
3. Review period (suggested minimum: 5 business days for MINOR, 10 for MAJOR)
4. Required updates before merge (manifest, examples, changelog, affected system docs)
5. Notification mechanism (GitHub issue label `contract-change`, consumers tagged)

Without this process, breaking changes will be coordinated informally, creating the risk of surprise breakage in implementation repos.

---

### REC-10: Resolve Schema Versioning Format Inconsistency (Priority: Medium)

Choose either `MAJOR.MINOR` or `MAJOR.MINOR.PATCH` uniformly across `docs/schema-governance.md` and `CONTRACT_VERSIONING.md`. Update all schema `$schema_version` fields and the standards manifest to use the chosen format. The manifest currently mixes formats implicitly (all at 1.0.0 which is valid in both, but the governing documents conflict). `MAJOR.MINOR.PATCH` from `CONTRACT_VERSIONING.md` is recommended — it provides a PATCH lane for documentation-only clarifications that do not require downstream repinning.

---

### REC-11: Significantly Expand `AGENTS.md` or Consolidate It (Priority: Medium)

Either expand `AGENTS.md` to serve as the universal agent entry point for the repo (covering: ecosystem context, repo navigation, agent-specific responsibilities for Claude/Codex/Copilot, common task patterns, links to CLAUDE.md and CODEX.md) — or consolidate its content into CLAUDE.md and remove the standalone file. As currently written (12 lines), it adds confusion rather than clarity because it implies a unified agent guide exists when CLAUDE.md and CODEX.md are the real references.

If expanded, `AGENTS.md` should specifically address: how agents should navigate the ecosystem (not just this repo), what agents must not do without a Claude reasoning step, and how agents should handle contract changes.

---

### REC-12: Update `docs/roadmap.md` to Reflect Current State (Priority: Medium)

The current roadmap shows SYS-001 and SYS-002 in Phase 1, SYS-003 in Phase 2, and Phase 3 as entirely future. Six systems are now designed. Update the roadmap to:
- Mark Phase 1 as complete (schemas, SYS-001, SYS-002 designed; implementation repos exist)
- Define the current phase (SYS-003 through SYS-006 designed; implementation of SYS-001 underway)
- Define Phase 2/3 milestones relative to the eight-repo ecosystem (pipeline orchestration, decision readiness production, institutional knowledge layer)

---

### REC-13: Add a Governance Conformance Checklist for Implementation Repos (Priority: Medium)

Create `docs/governance-conformance-checklist.md` that an implementation repo maintainer can run through before release:
- [ ] `system_id` declared in repo metadata
- [ ] Target spec version declared (pointing to `systems/<system>/interface.md` commit)
- [ ] All consumed schemas pinned to `contracts/standards-manifest.json` versions
- [ ] Rule pack version declared (or explicit statement that local defaults are active)
- [ ] No schema fields renamed or reordered relative to czar definitions
- [ ] Provenance fields present in all emitted artifacts
- [ ] Evaluation harness from `eval/<system>/` executed and pass/fail recorded

This is the enforcement document that makes governance tangible for implementation engineers.

---

### REC-14: Address Production Code in Design-First Repo (Priority: Low)

Either: (a) move `spectrum_systems/` and `run_study.py` to a dedicated `spectrum-pipeline-engine` implementation repo and remove them here, or (b) formally declare in `DECISIONS.md` and `docs/implementation-boundary.md` that this repo contains a reference implementation scaffold for evaluation purposes only, not for production use. Option (a) is preferred as it eliminates the philosophy tension. If (b) is chosen, add a prominent notice in `README.md` and `spectrum_systems/__init__.py` marking the code as evaluation-only.

---

## 5. Agents Architecture Assessment

### Current State

The three-agent model (Claude → reasoning, Codex → repository execution, Copilot → code implementation) is correctly described in `CLAUDE.md`, `CODEX.md`, and `docs/agent-selection-guide.md`. The separation of responsibilities is clean and the principle that Claude should produce structured instructions that Codex executes against is sound.

### Gap: No Agent Guidance for Implementation Repos

`docs/new-repo-checklist.md` requires CLAUDE.md and CODEX.md in all derived repos. However, there is no template or standard for what those files should contain. Implementation repos may write agent guidance that contradicts the governance layer's expectations (e.g., allowing Codex to invent schemas, or allowing Copilot to redefine contracts). `docs/agent-guidance-standard.md` exists but it does not provide a template CLAUDE.md or CODEX.md for implementation repos.

**Recommendation:** Add `docs/agent-guidance-standard.md` (or `examples/template-agent-files/`) with a template CLAUDE.md and CODEX.md that implementation repos should adapt, carrying pre-filled governance obligations (consume contracts from spectrum-systems, do not redefine schemas, require a Claude reasoning step before schema PRs).

### Gap: No AI Agent Guidance for `spectrum-pipeline-engine`

`spectrum-pipeline-engine` will be the most AI-intensive operational repo — it orchestrates multiple upstream engines and must coordinate contract versions, manage failure propagation, and produce downstream briefs. It will need explicit CLAUDE.md guidance about: which contracts it may not modify, how it should handle upstream contract version mismatches, and what human review gates are required. This guidance cannot be derived from the current agent guidance without a system design for the engine.

### Gap: `AGENTS.md` Development Cycle Is Incomplete

The development cycle in `AGENTS.md` is: Research → Plan → Implement → Test → Review. This misses the governance layer's own stage gate model from `docs/system-lifecycle.md` (9 stages). The development cycle in AGENTS.md should either reference or align with the system lifecycle, otherwise agents following AGENTS.md will skip the design, failure analysis, and evaluation plan stages before implementing.

---

## Summary Table

| Category | Count | Top Priority |
|---|---|---|
| Strengths confirmed | 9 | Contract czar model, machine-readable manifest, lifecycle gates |
| Structural gaps | 10 | Unmodeled ecosystem repos, missing workflow spec, eval coverage holes |
| Risk areas | 7 | No enforcement mechanism, `spectrum-pipeline-engine` unanchored, schema drift undetectable |
| Recommended additions | 14 | Ecosystem map, pipeline engine design, implementation boundary completions |

The repo is mature enough to govern the systems it has designed. The primary work ahead is extending governance coverage to the full ecosystem — particularly `spectrum-pipeline-engine` — and adding the lightweight process documents (change request, conformance checklist) that make governance enforceable rather than aspirational.
