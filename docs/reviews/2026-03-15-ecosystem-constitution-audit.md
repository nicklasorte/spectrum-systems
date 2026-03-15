# Systems Architecture Review: spectrum-systems as Ecosystem Constitution

**Date:** 2026-03-15
**Reviewer:** Claude (Principal Systems Architect stance)
**Scope:** Full audit of spectrum-systems as governing constitution for a distributed multi-repository ecosystem under growth pressure
**Review Type:** Constitutional governance audit — architecture, contracts, enforcement, scaling, failure modes

---

## Executive Summary

`spectrum-systems` demonstrates the structural vocabulary of a governing constitution — layered architecture documented in ADR-001, a contract czar model with a machine-readable manifest, schema registries, a 9-system lifecycle framework, and a 4-phase enforcement roadmap. The conceptual architecture is sound and the documentation density is high.

However, the repo does not yet **behave** like a governing constitution. It describes governance mechanisms more than it executes them. Three conditions disqualify it from that designation today:

1. **The repo violates its own most fundamental rule.** A production Python package (`spectrum_systems/`) implementing a full study runner pipeline lives inside a repository whose CLAUDE.md explicitly states "This repository should NOT contain production implementation code." The artifact boundary CI check does not catch Python code — it only bans binary file extensions. This is a governance constitution that cannot govern itself.

2. **Cross-repo enforcement does not exist.** The governance enforcement roadmap (Phase 1 through Phase 4) is entirely documented and entirely unstarted. Downstream engines can declare incompatible schema versions, bypass review protocols, or duplicate local standards with zero mechanical consequence. Compliance depends entirely on human goodwill and process memory.

3. **The ecosystem registry is materially incomplete.** Of the seven distinct operational repositories in the ecosystem, only four appear in `ecosystem/ecosystem-registry.json`. The four Layer 3 operational engines — working-paper-review-engine, comment-resolution-engine, meeting-minutes-engine, docx-comment-injection-engine — are absent. A constitution that does not enumerate the entities it governs cannot govern them.

Everything else in this audit operates below the severity of those three findings. They should be resolved before the ecosystem adds further engines.

**Current maturity rating: 2 (Structured).** Approaching 3 (Governed) but blocked by the enforcement gap and self-governance failure.

---

## System Strengths

**1. Contract czar model is explicit and machine-operable.**
`contracts/standards-manifest.json` is a real machine-readable registry with versioning, consumer declarations, status tracking (`stable`/`draft`), and example paths. `CONTRACT_VERSIONING.md` defines semantic versioning policy. `contracts/schemas/` holds 16 full JSON schemas. This is the strongest structural element in the repo.

**2. The 5-document system pattern is complete across all 9 systems.**
Every system has `overview.md`, `interface.md`, `design.md`, `evaluation.md`, and `prompts.md` under `systems/<system>/`. This enforces a consistent governance surface area for all systems regardless of implementation status. Coverage is not partial.

**3. ADR-001 records the foundational architectural decision with explicit rationale.**
The czar repo pattern, the separation of governance from execution, and the rejection of alternatives are on record with consequences listed. This is the right discipline. The architectural intent is not ambiguous.

**4. System lifecycle gates are defined (9-stage model in `docs/system-lifecycle.md`).**
Systems have explicit states from problem statement through operationalization. The status registry (`docs/system-status-registry.md`) tracks all 9 systems. This enables sequencing decisions and prevents premature implementation.

**5. Governance enforcement roadmap is structured (4-phase, `docs/governance-enforcement-roadmap.md`).**
The path from manual to machine enforcement is written. Phase 1 (declared identity and contract pins), Phase 2 (automated validation), Phase 3 (CI-based conformance), and Phase 4 (ecosystem-level compatibility) are distinct and sequenced. The problem is not that the path is missing — it is that no phase has been started.

**6. Artifact boundary CI exists and is wired to push/PR.**
`.github/workflows/artifact-boundary.yml` runs `scripts/check_artifact_boundary.py` on every push to main, release branches, and codex branches. This is enforcement in principle.

**7. Review protocol has a machine-readable schema.**
`design-reviews/claude-review.schema.json` and the ingestion workflow (`.github/workflows/claude-review-ingest.yml`) establish a path from review artifact to tracked data. The review registry (`docs/review-registry.md`) is populated with two entries. This is a working feedback loop in embryonic form.

**8. Bottleneck traceability is explicit.**
`docs/bottleneck-map.md` → `docs/systems-registry.md` → `systems/<system>/` creates a traceable chain from identified workflow bottleneck to system design. The `docs/system-map.md` traceability table is explicit. This is the correct design-first posture.

**9. Agent role separation is documented with governance files.**
CLAUDE.md, CODEX.md, and AGENTS.md establish distinct roles for reasoning, repository modification, and implementation. This reduces the risk of wrong-tool-for-wrong-task errors and makes agent behavior auditable.

**10. Error taxonomy and prompt governance are present.**
`docs/error-taxonomy.md`, `prompts/prompt-governance.md`, and `prompts/prompt-versioning.md` establish standards that downstream engines should inherit. These are the kinds of cross-cutting standards a constitution should define.

---

## Structural Risks

### Risk 1 (Critical): Production implementation code lives inside the constitution repo

**Files:** `spectrum_systems/`, `spectrum_systems/study_runner/pipeline.py`, `spectrum_systems/study_runner/run_study.py`, `spectrum_systems/study_runner/artifact_writer.py`, `spectrum_systems/contracts/__init__.py`, `run_study.py`

The `spectrum_systems/` Python package implements a full Spectrum Study Compiler pipeline: path loss calculations, interference modeling, protection zone computation, artifact writing, and config loading. This is production implementation code — the kind that CLAUDE.md explicitly states must not live in this repo.

The situation is worsened by coupling: `tests/test_contracts.py` imports `from spectrum_systems.contracts import ...` and `requirements-dev.txt` makes the package a dev dependency. The repo's own CI tests depend on the production code being present. Removing the package would break CI — which means the constitution is now structurally coupled to code it was never supposed to host.

The `check_artifact_boundary.py` CI script bans `.pdf`, `.docx`, and binary extensions. It does not flag Python source files. A governance constitution with a rule "no production code" that cannot detect production code is not enforcing that rule.

**Why this is critical:** It sets a precedent. Every downstream engine team that reads this repo and sees a working Python pipeline will reasonably conclude that hosting implementation code in governance repos is acceptable. The violation is also not flagged anywhere as a known risk to be remediated — it appears only in older review artifacts.

### Risk 2 (Critical): Cross-repo enforcement does not exist

**Files:** `docs/governance-enforcement-roadmap.md`, `.github/workflows/artifact-boundary.yml`

The 4-phase enforcement roadmap is a design document, not an operational system. No phase is active. Downstream engines can:
- Declare incompatible contract versions with no CI failure
- Skip `CLAUDE.md`/`CODEX.md` presence with no check
- Define local schemas that diverge from `contracts/schemas/` with no detection
- Ignore the provenance standard entirely

The CI in this repo does not run against downstream repos. There is no cross-repo compliance check, no manifest validation harness run against engine repos, and no automated signal when an engine violates a contract pin. The `system-factory` is described as the propagation path but is not yet wired to deliver enforcement primitives automatically.

**Why this is critical:** As more engines are added, governance divergence becomes harder to detect and more expensive to repair. The enforcement gap grows quadratically with ecosystem size.

### Risk 3 (High): Ecosystem registry misses four operational engines

**File:** `ecosystem/ecosystem-registry.json`

The registry lists 4 repos: spectrum-systems, system-factory, spectrum-pipeline-engine, spectrum-program-advisor. The following Layer 3 operational engines are absent:
- working-paper-review-engine
- comment-resolution-engine
- meeting-minutes-engine
- docx-comment-injection-engine

These four engines are the primary consumers of the contract czar model. Their absence from the registry means ecosystem-level health checks, compliance reports, and automated propagation have no enumeration to operate against. The registry is also missing a `compliance_status` field — there is no machine-readable record of which repos have been validated against which governance version.

### Risk 4 (High): Dual-track schema registries create ambiguous authority

**Directories:** `schemas/` (10 schemas, kebab-case, no `artifact_type`) vs. `contracts/schemas/` (16 schemas, snake_case, JSON Schema Draft 2020-12)

These are parallel schema authorities with different naming conventions, different structural depth, and different governance coverage. The root `schemas/` files (e.g., `comment-schema.json`, `issue-schema.json`) appear to be base data lake schemas. The `contracts/schemas/` files are the full contract schemas used by `test_contracts.py` and the manifest.

The relationship between these two tracks is documented in prose but not machine-enforced. There is nothing preventing a downstream engine from consuming `schemas/comment-schema.json` as its contract reference while the authoritative contract is `contracts/schemas/comment_resolution_matrix.schema.json`. Schema drift between the two tracks is a live risk.

### Risk 5 (High): Review-to-action loop breaks before GitHub issues

**Files:** `docs/review-registry.md`, `docs/review-actions/2026-03-14-architecture-actions.md`, `docs/review-actions/2026-03-14-governance-architecture-actions.md`

The review protocol produces markdown action trackers. Those trackers contain action items (GA-001 through GA-011, CR-1 through LI-2) but there is no automation converting them into GitHub issues. The `scripts/ingest-claude-review.js` ingests review artifacts but the ingestion output is not wired to issue creation. Action items live in markdown files that are not tracked by any project management system.

The review ingest workflow exists (`.github/workflows/claude-review-ingest.yml`) but its downstream effect — creating actionable tracked work — is absent. Reviews generate documents. Documents do not generate tickets. Tickets are what get done.

### Risk 6 (Medium): Single ADR recorded; subsequent decisions undocumented

**Directory:** `architecture-decisions/`

ADR-001 records the czar repo pattern. No subsequent ADRs exist. Significant decisions made since then — including the introduction of the Python package, the dual-track schema model, the evaluation coverage boundary (SYS-001–004 only), the 9-system lifecycle model, and the agent role assignments — are not recorded as ADRs. These are recoverable decisions for now, but as the ecosystem grows and original contributors rotate, the absence of ADR discipline becomes a liability.

### Risk 7 (Medium): SYS-007, SYS-008, SYS-009 governance coverage is incomplete

**Files:** `docs/implementation-boundary.md`, `docs/system-failure-modes.md`

Implementation boundary declarations and failure mode documentation for SYS-007 (working-paper-review-engine), SYS-008 (docx-comment-injection-engine), and SYS-009 (spectrum-pipeline-engine) are absent or incomplete. These are the three most recently designed systems and the ones most likely to reach implementation next. Governance gaps at the point of implementation are the highest-risk moment for contract drift.

### Risk 8 (Medium): `external_artifact_manifest` is `draft` but consumed as stable

**Files:** `contracts/standards-manifest.json`, `docs/contract-dependency-map.md`

The `external_artifact_manifest` contract carries `draft` status in the manifest but is referenced in the contract dependency map as a consumer-facing contract for artifact storage governance. Any engine implementing storage behavior against a draft contract is implementing against an unstable interface. The risk is not theoretical — it is already embedded in the dependency map.

### Risk 9 (Medium): No machine-readable contract consumer registry

**Files:** `docs/contract-dependency-map.md`, `contracts/standards-manifest.json`

The `intended_consumers` field in the standards manifest names consumers per contract (e.g., `working-paper-review-engine` for `working_paper_input`). However, there is no inverse registry: no machine-readable mapping from a given engine repo to the specific contract versions it has pinned. When `working_paper_input` bumps to `v1.1.0`, there is no automated way to identify which repos need migration. The dependency map exists in `docs/contract-dependency-map.md` as markdown prose, not as a queryable data structure.

### Risk 10 (Low-Medium): The artifact boundary CI check does not enforce the repo's own boundary

**File:** `scripts/check_artifact_boundary.py`

The CI check prohibits binary files and large blobs. It does not check for Python source modules implementing business logic, runnable scripts, or production pipeline code. The boundary rule stated in CLAUDE.md ("no production implementation code") is not reflected in the CI boundary check. The check enforces data boundary (no `.docx`, `.pdf`, `.xlsx`), not architecture boundary (no implementation code).

---

## Required Changes

These changes are required before the ecosystem onboards additional engines. They address governance failures, not style issues.

### RC-1: Remove or formally relocate the `spectrum_systems/` Python package

The production Python code in `spectrum_systems/` must leave this repo. Options:
- Move to a dedicated engine repo (e.g., `spectrum-study-compiler-engine`) with a link in the ecosystem registry
- If the contracts loading utility (`spectrum_systems/contracts/__init__.py`) genuinely belongs in the constitution layer, extract it into a narrow SDK package separate from the study runner

The test suite must be refactored to test contract schemas directly without importing from a production Python package. The `run_study.py` root-level script must be removed.

This change cannot be deferred. A constitution that violates its own foundational rule in the main branch with zero CI enforcement of that rule is not credible as a governing authority.

### RC-2: Extend the artifact boundary CI check to flag production implementation code

`scripts/check_artifact_boundary.py` must be extended to detect and reject:
- Python packages (directories containing `__init__.py` with business logic, not just utility imports)
- Runnable pipeline scripts at the root level

This closes the gap between the stated boundary rule and the enforced boundary rule. It also prevents future recurrence.

### RC-3: Populate the ecosystem registry with all operational engines

`ecosystem/ecosystem-registry.json` must include all known repos:
- working-paper-review-engine
- comment-resolution-engine
- meeting-minutes-engine
- docx-comment-injection-engine

Add a `compliance_status` field per entry indicating governance validation state. The registry is the enumeration that makes ecosystem-wide automation possible. It cannot be partial.

### RC-4: Start Phase 1 governance enforcement

The enforcement roadmap defines Phase 1 as "declared identity and contract pins." Implement it:
- Define the required `system-manifest.json` (or equivalent) schema for engine repos
- Wire `system-factory` scaffolding to generate this file automatically for new repos
- Add a CI check in this repo that validates ecosystem registry entries have accessible manifests

Phase 1 is the foundation all subsequent enforcement phases require. It cannot wait for Phase 4.

### RC-5: Complete SYS-007/008/009 governance coverage

- Add implementation boundary declarations for SYS-007, SYS-008, SYS-009 to `docs/implementation-boundary.md`
- Complete failure mode documentation for SYS-007, SYS-008, SYS-009 in `docs/system-failure-modes.md`
- Validate that all three systems have `interface.md` specifications at the required depth

These systems are next in line for implementation. Gaps now become drift later.

### RC-6: Resolve `external_artifact_manifest` draft status

Either:
- Promote to `stable` if the contract is ready
- Explicitly block consumers from depending on it until promoted
- Replace with an interim stable contract

The current state — `draft` in the manifest, referenced as stable in the dependency map — is a contradiction that downstream engines will resolve by guessing.

### RC-7: Wire the review-to-issue automation

Extend `scripts/ingest-claude-review.js` or the review ingest workflow to create GitHub issues from action tracker items. At minimum, implement a script that reads an action tracker markdown file and creates corresponding GitHub issues with appropriate labels. The review-registry-to-action-tracker-to-issue loop must be closed mechanically, not manually.

---

## Recommended Enhancements

These are valuable but not immediately required for the ecosystem to function safely.

### RE-1: Establish ADR discipline for all significant decisions

Create an ADR for every decision made since ADR-001: the dual-track schema model, evaluation coverage boundaries, Python package introduction (if retained in any form), agent role separation model, and governance enforcement phasing. Establish a policy that any decision affecting ecosystem interfaces requires a new ADR before merging.

### RE-2: Create a machine-readable contract consumer registry

Replace or augment `docs/contract-dependency-map.md` with a machine-readable JSON file mapping each engine repo to its pinned contract versions. This enables automated impact analysis when contracts evolve and is the prerequisite for Phase 4 (ecosystem-level compatibility validation).

### RE-3: Harden the evaluation harness coverage to all 9 systems

`eval/test-matrix.md` currently covers SYS-001 through SYS-004. Add evaluation harnesses, test fixtures, and rubrics for SYS-005 through SYS-009. Without evaluation coverage, systems cannot be validated before implementation repos consume their contracts.

### RE-4: Clarify and enforce the dual-track schema ownership model

Document explicitly which schemas belong in `schemas/` vs. `contracts/schemas/` and why. Add a CI check that validates no schema exists in both tracks with conflicting definitions. Cross-reference fields between the two tracks where overlap is intentional (e.g., `provenance-schema.json` vs `provenance_record.schema.json`).

### RE-5: Implement a constitutional release discipline

Tag a version (e.g., `governance-v1.0.0`) when the constitution reaches a stable state, and tag subsequent versions when MAJOR or MINOR contract changes are published. Engine repos should pin to a governance version, not just to individual contract versions. This enables safe ecosystem-wide rollouts.

### RE-6: Add an ecosystem health dashboard

Create a machine-readable `ecosystem-health.json` or equivalent that aggregates:
- Registry completeness (all repos present)
- Per-repo compliance status
- Open review action items
- Contract version pinning status per engine
- Evaluation harness coverage

This does not require a UI — a structured JSON file computed by a CI job is sufficient and enables external tooling.

### RE-7: Schema backward-compatibility CI test

Add tests that run against previous schema versions to verify backward compatibility claims in `CONTRACT_VERSIONING.md`. A MINOR bump should not break existing consumers. This should be tested, not only declared.

### RE-8: Formalize `system-factory` as the governance propagation mechanism

`system-factory` is described as the scaffolding layer but its relationship to propagating governance updates (new contract versions, updated prompts, schema changes) to existing repos is not specified. Document and implement the update propagation path. Without this, governance updates in `spectrum-systems` stay in `spectrum-systems`.

---

## Future Evolution Risks

If the current issues are not addressed, the following failure patterns are probable as the ecosystem grows:

**Contract drift.** As engines implement against contracts, they will discover ambiguities and add local schema fields to handle them. Without a machine-readable consumer registry and Phase 2/3 enforcement, these local extensions will become de facto contracts that diverge from the authoritative manifest. By the time the drift is detected, migration cost will be high.

**Dual-standard emergence.** Each engine that cannot easily access or parse the governance standards will create local copies. The `docs/` directory of each engine repo will accumulate documents that contradict `spectrum-systems` standards. This has already happened once (the Python package); without enforcement it will happen in every dimension.

**Governance bypass normalization.** If engineers observe that no compliance check catches violations, bypass becomes the path of least resistance. The production code in `spectrum_systems/` is a visible example that violations have no consequence. This is a cultural risk more than a technical one, but it begins with a technical failure.

**Review artifacts not becoming tracked work.** The review-to-action loop currently terminates at markdown files. If those files accumulate without becoming GitHub issues, the review process will be perceived as generating documentation rather than driving change. Engineers will stop taking reviews seriously. The 14 recommendations from the 2026-03-14 architecture review and 11 from the governance review have unknown completion rates.

**ADR vacuum creating revisitation cycles.** Without ADRs for major decisions, the same architectural questions will resurface as the team grows. "Why do we have two schema directories?" will be asked and re-debated. The cost of undocumented decisions compounds with team size.

**Orchestration layer invisible to governance.** `spectrum-pipeline-engine` (SYS-009, Layer 4) has the most cross-cutting system dependencies but is in `planned` status in the ecosystem registry and has the least governance coverage. When it is implemented, it will be the system most likely to discover contract incompatibilities across all upstream engines simultaneously.

---

## Architectural Maturity Assessment

**Rating: 2 — Structured (approaching 3)**

| Dimension | Rating | Rationale |
|-----------|--------|-----------|
| Architecture clarity | 3 | Layer model is clear; ADR-001 explicit; ecosystem map complete |
| Interface contracts | 2 | Machine-readable manifest exists; consumer registry absent; dual-track ambiguity |
| Governance model | 2 | Roadmap documented; zero phases active; self-governance violated |
| Ecosystem cohesion | 2 | Contracts well-defined; 4 engines unregistered; propagation path undeclared |
| Failure mode analysis | 2 | SYS-001–006 covered; SYS-007–009 gaps; no cross-repo failure detection |
| Automation readiness | 1 | Boundary CI exists for binaries; no contract compliance automation anywhere |
| Evolution strategy | 2 | Lifecycle gates defined; no pinning mechanism; no versioned releases |
| Observability | 1 | No ecosystem health signal; review registry is markdown; no dashboard primitive |
| Incentives/human factors | 2 | Agent guidance clear; production code violation unpunished by CI |
| ADR discipline | 1 | One ADR recorded; subsequent decisions untracked |

A rating of 3 (Governed) requires at minimum: active enforcement in at least one phase, complete ecosystem registry, and a closed review-to-issue loop. None of those conditions are met today. The repo is well-structured — it is not yet governed.

---

## Next-Step Architecture Moves to Reach Maturity Level 3

1. **Close the self-governance gap (RC-1, RC-2).** Remove or relocate `spectrum_systems/`. Extend the boundary CI check. This must come first — it is a credibility issue.

2. **Complete the ecosystem registry (RC-3).** Add all four missing engines with compliance status fields.

3. **Activate Phase 1 enforcement (RC-4).** Produce the `system-manifest.json` schema, wire it into `system-factory`, and add a CI validation step. This is the foundation for everything else in the enforcement roadmap.

4. **Close the review-to-issue loop (RC-7).** Even a simple script that reads action tracker markdown and creates labeled issues is sufficient. The loop must be mechanical.

5. **Resolve SYS-007/008/009 governance gaps (RC-5) and the draft contract status (RC-6).** These are pre-flight checks before any implementation repo begins work on those systems.

When those five moves are complete, the ecosystem will have: a self-consistent constitution, a complete repo enumeration, mechanical Phase 1 enforcement, traceable review outcomes, and no governance coverage gaps for active systems. That is the minimum viable governed state.

---

## Machine-Operable Actions Artifact

See paired file: `docs/review-actions/2026-03-15-constitution-audit-actions.json`
