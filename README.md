# spectrum-systems

Design and planning lab notebook for spectrum automation systems. Implementation code lives in separate repositories; this repo holds architecture, schemas, prompts, workflows, and evaluation plans. This is the governance/control-plane repo for SSOS GitHub operations across the czar organization.

## Why This Exists
This repository is building a policy-engineering operating system for spectrum studies—a system-first alternative to document-only workflows.

Most policy work is still done through documents, meetings, and iterative rewrites.

The typical pattern looks like this:
```text
documents → meetings → confusion → rewrite → more meetings → more rewrite
```
That approach works for small efforts, but it breaks down when multiple agencies, technical studies, and regulatory processes are involved. Traceability disappears. Decisions become difficult to reconstruct. Analysis is repeatedly re-done.

This project takes a different approach.

Instead of managing spectrum studies through documents alone, the system treats every artifact as a structured object that flows through a governed pipeline.
```text
structured artifacts → governed contracts → automated pipelines
```
Working papers, comment matrices, meeting minutes, and adjudications become machine-readable artifacts with defined interfaces, not just files passed around in email.

The result is something unusual:

A policy-engineering operating system for spectrum studies.

Most engineering organizations build pipelines for software.
This system builds pipelines for policy analysis, technical consensus, and interagency coordination.

That shift enables:
- traceable decision histories
- reproducible technical analysis
- automated document workflows
- structured comment resolution
- durable institutional knowledge

Spectrum policy sits at the intersection of engineering, regulation, and multi-agency governance. This system is designed to make that complexity manageable by turning policy workflows into structured, auditable processes.

## Start Here (fast path)
1. `docs/vision.md` — the why.
2. `docs/bottleneck-map.md` — the problems worth solving.
3. `docs/ecosystem-map.md` — authoritative czar repo map and flows.
4. `SYSTEMS.md` and `docs/system-map.md` — what systems exist and where to find their docs.
5. `docs/system-philosophy.md` and `docs/system-interface-spec.md` — how systems must behave.
6. `docs/system-lifecycle.md` and `docs/system-status-registry.md` — lifecycle and current maturity.
7. `docs/data-provenance-standard.md` and `docs/reproducibility-standard.md` — lineage and rerun expectations.
8. `contracts/` and `schemas/` — authoritative artifact contracts and schema registry, plus `prompts/` for prompt standards.

## Ecosystem Map
See `docs/ecosystem-map.md` for the authoritative czar repo map, contract relationships, and artifact flow across the organization.

## Security Model
- Operational data and generated artifacts stay off GitHub; only schemas, prompts, workflows, and lightweight synthetic fixtures live here.
- GitHub is the control plane with rules and contracts; the data plane is local or approved network storage referenced via manifests.
- Production workflows must accept external paths and emit manifests instead of writing artifacts into the repo.
- Do not use GitHub Releases or Git LFS for protected or operational artifacts; keep them in external storage with manifest coverage.

## GitHub Operating Layer
- `.github/ISSUE_TEMPLATE/` — deterministic issue intake aligned to SSOS contracts.
- `.github/workflows/` — GitHub Project automation for SSOS boards.
- `scripts/setup-labels.sh` — reusable label bootstrapper for SSOS repos.
- `docs/project-automation-setup.md` — script-driven setup for SSOS project automation variables and secret.
- `docs/github-operations.md` — governance guide and manual UI setup requirements.
- Data boundary: GitHub holds the machinery (schemas, prompts, workflows, docs); operational data and generated artifacts stay on approved local or network storage. See `docs/data-boundary-governance.md` and `docs/external-storage-implementation-guide.md`.

## Navigation
- `systems/` — per-system overview/interface/design/evaluation/prompts (see `systems/README.md`).
- `schemas/` — authoritative data contracts; see `schemas/README.md` for inventory.
- `contracts/` — canonical artifact contracts, examples, and standards manifest (`CONTRACTS.md` for guidance).
- `prompts/` — prompt registry aligned to schemas and systems.
- `eval/` — evaluation harness scaffolds and `eval/test-matrix.md`.
- `evals/` — shared evaluation datasets (fixtures + rubrics) for text-producing engines with run guidance in `evals/evals-framework.md`.
- `docs/` — architecture standards, lifecycle, governance, and bottleneck analysis.
- `workflows/` — stepwise automation blueprints.
- `examples/` — illustrative artifacts.
- `issues/` — backlog and research questions.
- Comment resolution matrix spreadsheet contract (authoritative headers/order for the czar org): `docs/comment-resolution-matrix-spreadsheet-contract.md` with schema in `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`.
- PDF-anchored DOCX comment injection contract (authoritative PDF line-anchor insertion rules and audit requirements): schema in `contracts/schemas/pdf_anchored_docx_comment_injection_contract.schema.json` with fixtures in `contracts/examples/`.
- Meeting agenda contract (canonical next-meeting agenda generator from minutes + resolution matrix + optional comments/context): `contracts/docs/meeting-agenda-contract.md` with schema in `contracts/schemas/meeting_agenda_contract.schema.json` and examples in `contracts/examples/`.
- Meeting minutes contract (canonical transcript-to-minutes artifact; JSON + DOCX + validation report required): `contracts/meeting_minutes_contract.yaml` with contract entry in `contracts/standards-manifest.json`; downstream engines must not add unsupported fields.

## Repository Philosophy
- Schema-led, deterministic systems with explicit human review gates.
- Prompts and rules are versioned; evaluation must precede implementation changes.
- Provenance and reproducibility metadata are mandatory for material artifacts.
- Implementation code belongs in downstream repos; this repo stays documentation-first.
- Operational data never lives in GitHub; this control plane links to external storage and uses manifests instead of embedding artifacts.

## Current Systems
- SYS-001 Comment Resolution Engine — `systems/comment-resolution/`
- SYS-002 Transcript-to-Issue Engine — `systems/transcript-to-issue/`
- SYS-003 Study Artifact Generator — `systems/study-artifact-generator/`
- SYS-004 Spectrum Study Compiler — `systems/spectrum-study-compiler/`
- SYS-005 Spectrum Program Advisor — `systems/spectrum-program-advisor/`
- SYS-006 Meeting Minutes Engine — `systems/meeting-minutes-engine/`
- SYS-007 Working Paper Review Engine — `systems/working-paper-review-engine/`
- SYS-008 DOCX Comment Injection Engine — `systems/docx-comment-injection-engine/`
- SYS-009 Spectrum Pipeline Engine — `systems/spectrum-pipeline-engine/`
See `SYSTEMS.md` and `docs/system-status-registry.md` for details.

## Governance & Standards
- Contribution and decision history: `CONTRIBUTING.md`, `CHANGELOG.md`, `DECISIONS.md`.
- Terminology: `GLOSSARY.md`, `docs/terminology.md`.
- Validation expectations: `VALIDATION.md`, `docs/system-failure-modes.md`.
- Maintenance: `docs/repo-maintenance-checklist.md`, `docs/doc-governance.md`.
- Conformance readiness: `docs/governance-conformance-checklist.md`.
- Comment resolution matrix authority: this repo governs the spreadsheet contract consumed by `working-paper-review-engine` and `comment-resolution-engine`; column names and order live in `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` and must not be redefined elsewhere.
- PDF-anchored DOCX comment injection authority: PDF page + line anchors with excerpt verification are required for Word comment insertion; engines must follow `contracts/schemas/pdf_anchored_docx_comment_injection_contract.schema.json` and emit the required audit report when generating commented DOCX outputs.
- Prompt governance: see `prompts/prompt-governance.md`, `prompts/prompt-versioning.md`, and the drafting scaffold in `prompts/prompt-template.md`.
- Repository metadata contract: `schemas/repository-metadata.schema.json` with guidance in `docs/repository-metadata.md`; operational repos must ship a root-level `repository-metadata.json` that conforms to the schema (template in `docs/repository-metadata-template.json`).

## Design Review Framework
- Canonical format: `docs/design-review-standard.md`
- Review-to-action flow: `docs/review-to-action-standard.md`
- Immutable artifacts directory: `docs/reviews/`
- Action trackers and template: `docs/review-actions/` and `docs/review-actions/action-tracker-template.md`
- Registry of reviews: `docs/review-registry.md`
- Culture and rationale: `docs/design-review-culture.md`

<!-- SSOS_MENTAL_MAP_START -->
## Mental Map System View

```text
                           ┌──────────────────────┐
                           │    system-factory    │
                           │ repo scaffolding     │
                           └──────────┬───────────┘
                                      │
                                      v
                           ┌──────────────────────┐
                           │   spectrum-systems   │
                           │ constitution / law   │
                           │ schemas, rules,      │
                           │ prompts, workflows   │
                           └──────────┬───────────┘
                                      │ governs
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        v                             v                             v
┌──────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│ spectrum-data-   │       │ spectrum-pipeline-   │       │ spectrum-program-    │
│ lake             │<----->│ engine               │<---   │ engine               │<----->│ advisor              │
│ raw + normalized │       │ orchestration        │       │ PM / risk / cadence  │
│ artifact store   │       │ runs workflows       │       │ guidance             │
└────────┬─────────┘       └──────────┬───────────┘       └──────────────────────┘
         │                             │
         │ feeds                       │ invokes
         │                             │
         v                             v
┌──────────────────┐       ┌──────────────────────┐
│ meeting-minutes- │       │ meeting-agenda-      │
│ engine           │       │ engine               │
│ transcript ->    │       │ minutes/comments/    │
│ notes/decisions  │       │ open issues -> agenda│
└────────┬─────────┘       └──────────────────────┘
         │
         │ derives
         v
┌──────────────────┐
│ FAQ / knowledge  │
│ engine           │
│ transcript +     │
│ comments + notes │
│ -> report-ready  │
│ Q/A + claims     │
└────────┬─────────┘
         │
         │ informs
         v
┌─────────────────────────┐      ┌────────────────────────┐
│ working-paper-review-   │ - report-ready  │
│ Q/A + claims     │
└────────┬─────────┘
         │
         │ informs
         v
┌─────────────────────────┐      ┌────────────────────────┐
│ working-paper-review-   │ ---> │ comment-resolution-    │
│ engine                  │      │ engine                 │
│ PDF -> reviewer matrix  │      │ resolve/adjudicate     │
└──────────┬──────────────┘      └──────────┬─────────────┘
           │                                 │
           │ resolved comments               │ approved changes
           v                                 v
      ┌─────────────────────────────────────────────────────┐
      │        docx-comment-injection-engine                │
      │      matrix + line refs -> Word comments            │
      └──────────────────────┬──────────────────────────────┘
                             │
                             v
                  ┌──────────────────────────┐
                  │ report-compiler          │
                  │ approved text blocks,    │
                  │ FAQs, decisions, notes,  │
                  │ adjudications -> report  │
                  └──────────────────────────┘
```
<!-- SSOS_MENTAL_MAP_END -->

## Architecture Reviews
- [docs/reviews/](docs/reviews/)
- [docs/architecture-actions.md](docs/architecture-actions.md)
