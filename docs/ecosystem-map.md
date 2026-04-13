# Ecosystem Map

## Purpose
Companion overview of the spectrum-systems ecosystem and how repositories relate. This repository (`spectrum-systems`) is the governance/constitution layer that defines contracts, schemas, and rules every downstream repo must follow.

## Ecosystem Repository Table
| Repository | Role | System ID (if applicable) | Produces Contracts | Consumes Contracts | Upstream Dependencies | Downstream Consumers | Implementation Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| system-factory | Repo scaffolder that mirrors governance defaults into new system repos. | N/A (scaffolding) | Template manifests and starter contracts from `SYSTEM_TEMPLATE.md`. | `contracts/standards-manifest.json` and governance docs from `spectrum-systems`. | spectrum-systems | All repos it scaffolds. | Operational scaffolding. |
| spectrum-systems | Governance/control plane for schemas, contracts, prompts, and workflows. | N/A (governance) | Canonical contracts under `contracts/`, schemas under `schemas/`, standards manifest, governance docs. | None; source of truth. | None | All downstream system repos and system-factory. | Operational governance. |
| working-paper-review-engine | Normalizes working papers into reviewer_comment_set and seeded matrices. | SYS-007 | reviewer_comment_set; initial `comment_resolution_matrix_spreadsheet_contract`. | working_paper_input; standards mirrored from `spectrum-systems`. | spectrum-systems; system-factory | comment-resolution-engine; docx-comment-injection-engine; spectrum-pipeline-engine. | Design drafted. |
| comment-resolution-engine | Adjudicates comments and updates matrices with dispositions. | SYS-001 | Updated `comment_resolution_matrix_spreadsheet_contract`; issue records. | reviewer_comment_set; `comment_resolution_matrix_spreadsheet_contract`. | working-paper-review-engine; spectrum-systems | docx-comment-injection-engine; spectrum-pipeline-engine. | Design complete; evaluation scaffolding in place. |
| docx-comment-injection-engine | Injects anchored comments into DOCX with audit manifests. | SYS-008 | `pdf_anchored_docx_comment_injection_contract` outputs; annotated DOCX + manifests. | `comment_resolution_matrix_spreadsheet_contract` (anchored). | comment-resolution-engine | spectrum-pipeline-engine; report/compilation flows. | Design drafted; injection rules defined. |
| spectrum-pipeline-engine | Orchestrates upstream artifacts into agendas and readiness bundles. | SYS-009 | `meeting_agenda_contract` outputs; readiness bundles; pipeline run manifest. | `meeting_minutes_contract`; `comment_resolution_matrix_spreadsheet_contract`; readiness schemas; `external_artifact_manifest`. | meeting-minutes-engine; comment-resolution-engine; docx-comment-injection-engine; working-paper-review-engine | spectrum-program-advisor; governance reviewers. | Design drafted; governance coverage added. |
| meeting-minutes-engine | Converts transcripts into contract-governed minutes with validation. | SYS-006 | `meeting_minutes_contract` (JSON + DOCX) and validation report. | Transcript manifests and agenda seeds defined in `spectrum-systems`. | spectrum-systems | spectrum-pipeline-engine; agenda production. | Design drafted; contract defined. |
| spectrum-program-advisor | Normalizes readiness artifacts into program advisory outputs. | SYS-005 | `program_brief`; `study_readiness_assessment`; `next_best_action_memo`; `decision_log`; `risk_register`; `assumption_register`; `milestone_plan`. | Readiness bundle and run manifest from `spectrum-pipeline-engine`. | spectrum-pipeline-engine | Program governance boards and managers. | Design drafted; fixtures scaffolded. |

## Architecture Diagram
```mermaid
flowchart TB
    SF[system-factory]
    SS[spectrum-systems\n(governance / contract czar)]

    subgraph OE["operational engines"]
        WPR[working-paper-review-engine (SYS-007)]
        CRE[comment-resolution-engine (SYS-001)]
        DCI[docx-comment-injection-engine (SYS-008)]
        MME[meeting-minutes-engine (SYS-006)]
    end

    SPE[spectrum-pipeline-engine (SYS-009)]
    SPA[spectrum-program-advisor (SYS-005)]

    SF --> SS
    SS --> OE
    OE --> SPE
    SPE --> SPA
```

## Data Flow Overview
```text
working paper
    ↓
working-paper-review-engine
    ↓
comment-resolution-engine
    ↓
docx-comment-injection-engine
    ↓
meeting-minutes-engine
    ↓
spectrum-pipeline-engine
    ↓
spectrum-program-advisor
```

## Governance Note
All repositories in this ecosystem must honor the contracts, schemas, and rules published in `spectrum-systems` before emitting or consuming artifacts. Changes to contracts originate here and propagate deterministically to downstream repos.

Ownership authority note: canonical subsystem ownership, acronyms, and placeholder status are defined only in `docs/architecture/system_registry.md`.

## Cross-links
- `SYSTEMS.md`
- `docs/system-map.md`
- `contracts/standards-manifest.json`
- `docs/system-status-registry.md`
