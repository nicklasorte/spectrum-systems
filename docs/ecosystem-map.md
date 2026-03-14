# Ecosystem Map

Authoritative view of the current repos, their roles, contract responsibilities, and dependencies. Spectrum Systems remains the czar; all implementation repos must align to the contracts and system interfaces defined here.

## Repository Table

| Repo | Role | System ID | Contracts Produced | Contracts Consumed | Implementation Status | Upstream / Downstream |
| --- | --- | --- | --- | --- | --- | --- |
| system-factory | Scaffold generator that mirrors czar contracts into new implementation repos with pinned versions. | N/A (governance tool) | standards_manifest (mirrors), repo scaffolds | standards_manifest, all published contracts for mirroring | Operational scaffolding | Upstream: spectrum-systems. Downstream: all generated repos. |
| spectrum-systems | Governance czar defining contracts, interfaces, lifecycle rules, and evaluation expectations. | N/A (czar) | All canonical contracts, standards_manifest, system specs | Bottleneck definitions, provenance/data standards | Operational governance | Upstream: bottleneck analysis. Downstream: every implementation repo. |
| working-paper-review-engine | Transforms working paper drafts into normalized reviewer comment sets and canonical comment resolution matrices. | SYS-007 | reviewer_comment_set, comment_resolution_matrix_spreadsheet_contract, run manifests | working_paper_input, provenance_record, docx templates | Design drafted (czar coverage added; implementation TBD) | Upstream: working paper authorship. Downstream: comment-resolution-engine, docx-comment-injection-engine, spectrum-pipeline-engine. |
| comment-resolution-engine | Clusters, routes, and drafts dispositions for agency comments with traceability. | SYS-001 | comment_resolution_matrix, disposition outputs, validation reports | reviewer_comment_set, comment_resolution_matrix_spreadsheet_contract, provenance_record | Design complete (implementation external) | Upstream: working-paper-review-engine. Downstream: docx-comment-injection-engine, spectrum-pipeline-engine, spectrum-program-advisor. |
| docx-comment-injection-engine | Applies PDF/DOCX anchored comments and dispositions into governed DOCX deliverables. | SYS-008 | annotated DOCX per pdf_anchored_docx_comment_injection_contract, manifests | comment_resolution_matrix_spreadsheet_contract, pdf_anchored_docx_comment_injection_contract, provenance_record | Design drafted (czar coverage added; implementation TBD) | Upstream: working-paper-review-engine, comment-resolution-engine. Downstream: publication pipelines, spectrum-pipeline-engine. |
| spectrum-pipeline-engine | Orchestrates upstream engines, sequencing canonical contracts into advisory/program artifacts. | SYS-009 | pipeline run manifests, agenda packages, readiness bundles aligned to advisor contracts | meeting_minutes, meeting_agenda_contract, comment_resolution_matrix_spreadsheet_contract, program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan, external_artifact_manifest | Design drafted; workflow spec added; implementation pending | Upstream: meeting-minutes-engine, working-paper-review-engine, comment-resolution-engine, study pipelines. Downstream: spectrum-program-advisor, governance reviewers. |
| meeting-minutes-engine | Generates contract-governed minutes with transcript traceability. | SYS-006 | meeting_minutes, validation reports | meeting_minutes inputs (transcripts, templates), meeting_agenda_contract | Design drafted; evaluation harness pending | Upstream: transcript capture. Downstream: spectrum-pipeline-engine, agenda generation, program-advisor. |
| spectrum-program-advisor | Normalizes canonical artifacts into decision-readiness briefs and action memos. | SYS-005 | program_brief, study_readiness_assessment, next_best_action_memo, decision_log, risk_register, assumption_register, milestone_plan | meeting_minutes, meeting_agenda_contract, comment_resolution_matrix_spreadsheet_contract, readiness and risk/decision/assumption/milestone contracts | Design drafted; fixtures scaffolded | Upstream: spectrum-pipeline-engine and upstream engines; Downstream: program governance stakeholders. |

## Data / Control Flow (Mermaid)

```mermaid
flowchart LR
    SF[system-factory\n(scaffolds)] -->|mirrors contracts| WPR[working-paper-review-engine\nSYS-007]
    SF --> CRE[comment-resolution-engine\nSYS-001]
    SF --> DCI[docx-comment-injection-engine\nSYS-008]
    SF --> MME[meeting-minutes-engine\nSYS-006]
    SF --> SPE[spectrum-pipeline-engine\nSYS-009]
    SF --> SPA[spectrum-program-advisor\nSYS-005]

    WPR -->|comment_resolution_matrix + reviewer_comment_set| CRE
    WPR -->|comment matrices + anchored references| DCI
    CRE -->|adjudicated matrices + dispositions| DCI
    DCI -->|annotated DOCX| SPE

    MME -->|meeting_minutes + validation| SPE
    CRE -->|resolution outputs| SPE
    SPE -->|agenda packages + readiness bundle| SPA
    SPE -->|program_brief + risk/decision/assumption/milestone plans| SPA
    SPA -->|governance outputs| Stakeholders[(program governance)]
```
