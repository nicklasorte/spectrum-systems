# System Map

Traceability map for systems, bottlenecks, schemas, prompts, and evaluation assets.

## Bottlenecks → Systems

| Bottleneck ID | Description | Systems |
| --- | --- | --- |
| BN-001 | Comment resolution workflow delays from manual reconciliation and disposition drafting. | SYS-001 Comment Resolution Engine |
| BN-002 | Transcript-to-issue gaps that leave actions untracked after meetings. | SYS-002 Transcript-to-Issue Engine |
| BN-003 | Simulation output-to-report translation bottlenecks. | SYS-003 Study Artifact Generator, SYS-004 Spectrum Study Compiler |
| BN-004 | Decision readiness is unclear because program artifacts (risks, decisions, milestones, assumptions) are fragmented and stale. | SYS-005 Spectrum Program Advisor |
| BN-005 | Meeting output evaporates without canonical minutes, breaking traceability to transcripts and agenda items. | SYS-006 Meeting Minutes Engine |
| BN-006 | Orchestration gaps between upstream engines lead to contract drift, inconsistent sequencing, and missing readiness signals. | SYS-009 Spectrum Pipeline Engine |

## Systems → Key Assets

| System | ID | Overview | Interface | Design | Schemas | Prompts | Eval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Comment Resolution Engine | SYS-001 | systems/comment-resolution/overview.md | systems/comment-resolution/interface.md | systems/comment-resolution/design.md | schemas/comment-schema.json, schemas/issue-schema.json, schemas/provenance-schema.json | prompts/comment-resolution.md | eval/comment-resolution |
| Transcript-to-Issue Engine | SYS-002 | systems/transcript-to-issue/overview.md | systems/transcript-to-issue/interface.md | systems/transcript-to-issue/design.md | schemas/issue-schema.json, schemas/provenance-schema.json | prompts/transcript-to-issue.md | eval/transcript-to-issue |
| Study Artifact Generator | SYS-003 | systems/study-artifact-generator/overview.md | systems/study-artifact-generator/interface.md | systems/study-artifact-generator/design.md | schemas/study-output-schema.json, schemas/assumption-schema.json, schemas/provenance-schema.json | prompts/report-drafting.md | eval/study-artifacts |
| Spectrum Study Compiler | SYS-004 | systems/spectrum-study-compiler/overview.md | systems/spectrum-study-compiler/interface.md | systems/spectrum-study-compiler/design.md | schemas/compiler-manifest.schema.json, schemas/artifact-bundle.schema.json, schemas/diagnostics.schema.json, schemas/study-output-schema.json, schemas/provenance-schema.json | prompts/spectrum-study-compiler.md, prompts/report-drafting.md | eval/spectrum-study-compiler |
| Spectrum Program Advisor | SYS-005 | systems/spectrum-program-advisor/overview.md | systems/spectrum-program-advisor/interface.md | systems/spectrum-program-advisor/design.md | contracts/schemas/program_brief.schema.json, contracts/schemas/study_readiness_assessment.schema.json, contracts/schemas/next_best_action_memo.schema.json, contracts/schemas/decision_log.schema.json, contracts/schemas/risk_register.schema.json, contracts/schemas/assumption_register.schema.json, contracts/schemas/milestone_plan.schema.json | systems/spectrum-program-advisor/prompts.md | eval/spectrum-program-advisor |
| Meeting Minutes Engine | SYS-006 | systems/meeting-minutes-engine/overview.md | systems/meeting-minutes-engine/interface.md | systems/meeting-minutes-engine/design.md | contracts/meeting_minutes_contract.yaml | systems/meeting-minutes-engine/prompts.md | systems/meeting-minutes-engine/evaluation.md |
| Working Paper Review Engine | SYS-007 | systems/working-paper-review-engine/overview.md | systems/working-paper-review-engine/interface.md | systems/working-paper-review-engine/design.md | contracts/examples/reviewer_comment_set.json, contracts/examples/comment_resolution_matrix_spreadsheet_contract.json, contracts/examples/working_paper_input.json | systems/working-paper-review-engine/prompts.md | systems/working-paper-review-engine/evaluation.md |
| DOCX Comment Injection Engine | SYS-008 | systems/docx-comment-injection-engine/overview.md | systems/docx-comment-injection-engine/interface.md | systems/docx-comment-injection-engine/design.md | contracts/examples/pdf_anchored_docx_comment_injection_contract.json, docs/comment-resolution-matrix-spreadsheet-contract.md | systems/docx-comment-injection-engine/prompts.md | systems/docx-comment-injection-engine/evaluation.md |
| Spectrum Pipeline Engine | SYS-009 | systems/spectrum-pipeline-engine/overview.md | systems/spectrum-pipeline-engine/interface.md | systems/spectrum-pipeline-engine/design.md | contracts/standards-manifest.json | systems/spectrum-pipeline-engine/prompts.md | systems/spectrum-pipeline-engine/evaluation.md |

## Systems → Workflows

| System | Workflow Spec | Upstream | Downstream |
| --- | --- | --- | --- |
| SYS-001 | workflows/comment-resolution-engine.md | comment spreadsheets, working paper PDFs, section anchors | report drafting, issue backlogs |
| SYS-002 | workflows/transcript-to-issue-engine.md | meeting transcripts, speaker metadata | issue backlog, assumption registry |
| SYS-003 | workflows/study-artifact-generator.md | simulation outputs, assumptions, study templates | compiler-ready artifacts, report assembly, decision briefs |
| SYS-004 | workflows/spectrum-study-compiler.md | SYS-003 artifacts, manifests, provenance records | packaged study deliverables, decision artifacts, report assembly |
| SYS-005 | workflows/spectrum-program-advisor.md | canonical metadata for working papers, CRM, minutes, risk register, milestone plan, decision log, assumption register | program briefs, readiness assessments, next-best-action memos, risk/decision/missing-evidence summaries |
| SYS-006 | (workflow spec forthcoming) | meeting transcripts, meeting minutes template, prior minutes/agenda/resolution matrices (optional) | contract-governed minutes JSON/DOCX, validation report feeding agenda and advisor workflows |
| SYS-007 | workflows/working-paper-review-engine.md | working paper inputs, reviewer assignments, anchors | reviewer_comment_set, comment_resolution_matrix_spreadsheet_contract, anchored DOCX payloads |
| SYS-008 | workflows/docx-comment-injection-engine.md | comment_resolution_matrix_spreadsheet_contract, anchored payloads, DOCX/PDF | annotated DOCX, updated matrix, run manifest |
| SYS-009 | workflows/spectrum-pipeline-engine.md | meeting_minutes, comment matrices, agenda seeds, readiness artifacts, external manifests | agenda packages, readiness bundles, pipeline run manifest |

## Related Standards
- `docs/system-philosophy.md` — shared design beliefs and scope boundaries.
- `docs/system-interface-spec.md` — required interface sections for every system.
- `docs/system-lifecycle.md` — stage gates from problem definition to operations.
- `docs/system-failure-modes.md` — common risks and mitigations.
- `docs/system-status-registry.md` — current lifecycle state for each system.
