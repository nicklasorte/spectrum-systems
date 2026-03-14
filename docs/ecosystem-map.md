# Ecosystem Map (czar organization)

Authoritative map of repos in the czar organization and the governed control/contract flows between them.

## Repository Roles

| Repo | Role | System ID | Contracts Produced | Contracts Consumed | Implementation Status | Upstream Dependencies | Downstream Dependencies |
| --- | --- | --- | --- | --- | --- | --- | --- |
| system-factory | Scaffold generator for new system repos; seeds interface/design/eval skeletons. | N/A (scaffolding) | Template manifests and starter contracts from `SYSTEM_TEMPLATE.md`. | Governance docs from `spectrum-systems`. | Template operational for new repos. | spectrum-systems (architecture) | All implementation repos it scaffolds. |
| spectrum-systems | Control plane for schemas, contracts, prompts, workflows, and governance. | N/A (governance) | `contracts/` schemas, `schemas/` registry, standards manifest, prompts, workflows. | Architecture reviews and bottleneck inputs. | Design-first; authoritative and operational. | None | All downstream system repos. |
| working-paper-review-engine | Normalizes working papers into reviewer_comment_set and comment_resolution_matrix_spreadsheet_contract. | SYS-007 | reviewer_comment_set, comment_resolution_matrix_spreadsheet_contract (initial). | working_paper_input contract, system-factory scaffold. | Design drafted; contract alignment captured. | spectrum-systems, system-factory | comment-resolution-engine; docx-comment-injection-engine; spectrum-pipeline-engine (via matrices). |
| comment-resolution-engine | Adjudicates comments, drafts dispositions, and updates matrices. | SYS-001 | Updated comment_resolution_matrix_spreadsheet_contract; issue records. | reviewer_comment_set, comment_resolution_matrix_spreadsheet_contract. | Design complete; evaluation scaffolding in place. | working-paper-review-engine | docx-comment-injection-engine; spectrum-pipeline-engine. |
| docx-comment-injection-engine | Injects anchored comments into DOCX with audit manifest. | SYS-008 | pdf_anchored_docx_comment_injection_contract outputs; annotated DOCX + manifest. | comment_resolution_matrix_spreadsheet_contract with anchors. | Design drafted; injection rules defined. | comment-resolution-engine | spectrum-pipeline-engine; report/compilation flows. |
| spectrum-pipeline-engine | Orchestrates upstream artifacts into agenda packages and readiness bundles. | SYS-009 | meeting_agenda_contract outputs, readiness bundle artifacts, pipeline run manifest. | meeting_minutes_contract, comment_resolution_matrix_spreadsheet_contract, readiness schemas, external_artifact_manifest. | Design drafted; governance coverage added. | meeting-minutes-engine; comment-resolution-engine; docx-comment-injection-engine; working-paper-review-engine | spectrum-program-advisor; governance reviewers. |
| meeting-minutes-engine | Converts transcripts into contract-governed minutes with validation. | SYS-006 | meeting_minutes_contract (JSON + DOCX) + validation report. | Transcripts, agenda seeds, templates. | Design drafted; contract defined. | spectrum-systems guidance | spectrum-pipeline-engine; agenda production. |
| spectrum-program-advisor | Normalizes readiness artifacts into program briefs and advisory outputs. | SYS-005 | program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan. | Readiness bundle + run manifest from spectrum-pipeline-engine. | Design drafted; fixtures scaffolded. | spectrum-pipeline-engine | Governance boards, program managers. |

## Control and Artifact Flow

```mermaid
flowchart LR
    SS[spectrum-systems\n(control plane)] --> SF[system-factory\n(scaffolds)]
    SS --> WPR[working-paper-review-engine\nSYS-007]
    SS --> CRE[comment-resolution-engine\nSYS-001]
    SS --> MME[meeting-minutes-engine\nSYS-006]
    SS --> SPE[spectrum-pipeline-engine\nSYS-009]
    SS --> SPA[spectrum-program-advisor\nSYS-005]

    SF -- scaffolds --> WPR
    SF -- scaffolds --> CRE
    SF -- scaffolds --> MME

    WPR -- reviewer_comment_set + matrices --> CRE
    CRE -- resolved matrices --> DCI[docx-comment-injection-engine\nSYS-008]
    MME -- meeting_minutes --> SPE
    CRE -- comment matrices --> SPE
    DCI -- annotated DOCX + manifests --> SPE
    SPE -- agendas + readiness bundles + run manifests --> SPA
    SPA -- program briefs / readiness advisories --> Governance[(program governance)]
```
