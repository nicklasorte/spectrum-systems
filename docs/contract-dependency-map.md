# Contract Dependency Map

This map is derived from `contracts/standards-manifest.json` and links each canonical contract in `contracts/` to the systems that produce and consume it. Schema versions and artifact types come directly from the manifest to keep the table aligned with the authoritative definitions in `contracts/schemas/` and `contracts/examples/`.

## Contract Table

| Contract | Producer System | Consumer Systems | Artifact Type | Schema Version | Notes |
| --- | --- | --- | --- | --- | --- |
| working_paper_input | Upstream authors captured via working-paper-review-engine (SYS-007 intake) | working-paper-review-engine, system-factory | working_paper_input | 1.0.0 | Intake contract for draft submissions. **Multi-consumer.** |
| reviewer_comment_set | working-paper-review-engine (SYS-007) | comment-resolution-engine, spectrum-pipeline-engine, system-factory | reviewer_comment_set | 1.0.0 | Normalized reviewer feedback; shared across multiple downstream engines. |
| comment_resolution_matrix | working-paper-review-engine seeds; comment-resolution-engine (SYS-001) adjudicates | working-paper-review-engine, comment-resolution-engine, system-factory | comment_resolution_matrix | 1.0.0 | Structured mapping from comments to dispositions/actions. |
| meeting_agenda_contract | spectrum-pipeline-engine (SYS-009) | meeting-minutes-engine, comment-resolution-engine, spectrum-pipeline-engine, system-factory | meeting_agenda_contract | 1.0.0 | Agenda output/seed that bridges minutes and resolution workflows. **Multi-consumer.** |
| meeting_minutes | meeting-minutes-engine (SYS-006) | spectrum-pipeline-engine, spectrum-program-advisor, meeting-minutes-engine, system-factory | meeting_minutes | 1.0.0 | Contract-governed minutes with validation and provenance. **Multi-consumer.** |
| comment_resolution_matrix_spreadsheet_contract | working-paper-review-engine (seed), comment-resolution-engine (adjudicated), docx-comment-injection-engine (status updates) | comment-resolution-engine, docx-comment-injection-engine, spectrum-pipeline-engine, system-factory | comment_resolution_matrix_spreadsheet_contract | 1.0.0 | Human-facing matrix; must preserve canonical headers/order. **Multi-consumer.** |
| pdf_anchored_docx_comment_injection_contract | docx-comment-injection-engine (SYS-008) | working-paper-review-engine, comment-resolution-engine, docx-comment-injection-engine, system-factory | pdf_anchored_docx_comment_injection_contract | 1.0.1 | Anchored DOCX/PDF insertion payload with audit requirements. **Multi-consumer.** |
| standards_manifest | spectrum-systems (governance control plane) | system-factory, downstream schema loaders | standards_manifest | 1.0.0 | Registry of pinned contract versions; consumed by every implementation repo. |
| provenance_record | All engines emitting provenance sidecars | working-paper-review-engine, comment-resolution-engine, system-factory | provenance_record | 1.0.0 | Shared provenance envelope for traceability; reused across systems. |
| program_brief | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | program_brief | 1.0.0 | Advisor-ready brief within readiness bundles. |
| study_readiness_assessment | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | study_readiness_assessment | 1.0.0 | Readiness gate assessment artifact. |
| next_best_action_memo | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | next_best_action_memo | 1.0.0 | Prioritized actions downstream of readiness signals. |
| decision_log | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | decision_log | 1.0.0 | Structured decision register with options and evidence links. |
| risk_register | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | risk_register | 1.0.0 | Risk catalog aligned to readiness gates. |
| assumption_register | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | assumption_register | 1.0.0 | Assumption tracking with validation plans. |
| milestone_plan | spectrum-program-advisor (SYS-005) | spectrum-program-advisor, spectrum-pipeline-engine | milestone_plan | 1.0.0 | Decision-aware milestone schedule. |
| external_artifact_manifest | spectrum-pipeline-engine and study-artifact-generator when publishing off-repo artifacts | spectrum-pipeline-engine, study-artifact-generator, comment-resolution-engine | external_artifact_manifest | 1.0.0 | Boundary contract for non-GitHub storage; enforces checksums/lineage. **Multi-consumer.** |

## Multi-System Dependencies

- Cross-boundary contracts with the widest fan-out: `comment_resolution_matrix_spreadsheet_contract`, `meeting_minutes`, `meeting_agenda_contract`, `pdf_anchored_docx_comment_injection_contract`, `external_artifact_manifest`, and `reviewer_comment_set`. These require version pins from the standards manifest to avoid drift.
- Control-plane contracts (`standards_manifest`, `provenance_record`) underpin every engine; downstream repos must reference `contracts/` directly instead of redefining schemas.

## Contract Flow Diagram

```mermaid
flowchart LR
    subgraph Intake & Review
        WPR[SYS-007\nworking-paper-review-engine]
        CRE[SYS-001\ncomment-resolution-engine]
        DCI[SYS-008\ndocx-comment-injection-engine]
    end
    subgraph Minutes & Orchestration
        MME[SYS-006\nmeeting-minutes-engine]
        SPE[SYS-009\nspectrum-pipeline-engine]
    end
    SPA[SYS-005\nspectrum-program-advisor]

    WPR -- reviewer_comment_set,\ncomment_resolution_matrix_spreadsheet_contract --> CRE
    CRE -- adjudicated matrices --> DCI
    DCI -- pdf_anchored_docx_comment_injection_contract,\nupdated matrices --> SPE
    MME -- meeting_minutes --> SPE
    SPE -- meeting_agenda_contract --> MME
    SPE -- readiness bundle\n(program_brief + readiness artifacts) --> SPA
    SPA -- advisory outputs --> SPE

    SS[standards_manifest + provenance_record\n(control plane)] --> WPR
    SS --> CRE
    SS --> MME
    SS --> DCI
    SS --> SPE
    SS --> SPA
```

All arrows reflect contract exchanges governed by the schemas in `contracts/` and pinned via `contracts/standards-manifest.json`.
