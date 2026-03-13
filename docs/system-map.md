# System Map

Traceability map for systems, bottlenecks, schemas, prompts, and evaluation assets.

## Bottlenecks → Systems

| Bottleneck ID | Description | Systems |
| --- | --- | --- |
| BN-001 | Comment resolution workflow delays from manual reconciliation and disposition drafting. | SYS-001 Comment Resolution Engine |
| BN-002 | Transcript-to-issue gaps that leave actions untracked after meetings. | SYS-002 Transcript-to-Issue Engine |
| BN-003 | Simulation output-to-report translation bottlenecks. | SYS-003 Study Artifact Generator, SYS-004 Spectrum Study Compiler |

## Systems → Key Assets

| System | ID | Overview | Interface | Design | Schemas | Prompts | Eval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Comment Resolution Engine | SYS-001 | systems/comment-resolution/overview.md | systems/comment-resolution/interface.md | systems/comment-resolution/design.md | schemas/comment-schema.json, schemas/issue-schema.json, schemas/provenance-schema.json | prompts/comment-resolution.md | eval/comment-resolution |
| Transcript-to-Issue Engine | SYS-002 | systems/transcript-to-issue/overview.md | systems/transcript-to-issue/interface.md | systems/transcript-to-issue/design.md | schemas/issue-schema.json, schemas/provenance-schema.json | prompts/transcript-to-issue.md | eval/transcript-to-issue |
| Study Artifact Generator | SYS-003 | systems/study-artifact-generator/overview.md | systems/study-artifact-generator/interface.md | systems/study-artifact-generator/design.md | schemas/study-output-schema.json, schemas/assumption-schema.json, schemas/provenance-schema.json | prompts/report-drafting.md | eval/study-artifacts |
| Spectrum Study Compiler | SYS-004 | systems/spectrum-study-compiler/overview.md | systems/spectrum-study-compiler/interface.md | systems/spectrum-study-compiler/design.md | schemas/study-output-schema.json, schemas/provenance-schema.json | prompts/report-drafting.md | eval/study-artifacts |

## Systems → Workflows

| System | Workflow Spec | Upstream | Downstream |
| --- | --- | --- | --- |
| SYS-001 | workflows/comment-resolution-engine.md | comment spreadsheets, working paper PDFs, section anchors | report drafting, issue backlogs |
| SYS-002 | workflows/transcript-to-issue-engine.md | meeting transcripts, speaker metadata | issue backlog, assumption registry |
| SYS-003 | workflows/study-artifact-generator.md | simulation outputs, assumptions, study templates | report assembly, decision briefs |
| SYS-004 | workflows/spectrum-study-compiler.md | study artifacts, manifests, provenance records | packaged study deliverables, decision artifacts |

## Related Standards
- `docs/system-philosophy.md` — shared design beliefs and scope boundaries.
- `docs/system-interface-spec.md` — required interface sections for every system.
- `docs/system-lifecycle.md` — stage gates from problem definition to operations.
- `docs/system-failure-modes.md` — common risks and mitigations.
- `docs/system-status-registry.md` — current lifecycle state for each system.
