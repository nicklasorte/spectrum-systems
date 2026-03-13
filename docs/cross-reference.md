# Cross-Reference Map

This document is the traceability map for the architecture. It links bottlenecks to the systems that address them, and maps each system to the schemas, prompts, and evaluation harnesses that enforce deterministic, reviewable outputs.

## Bottlenecks → Systems

| Bottleneck ID | Description | Systems Addressing It |
| --- | --- | --- |
| BN-001 | Comment resolution workflow delays caused by manual reconciliation and disposition drafting. | SYS-001 Comment Resolution Engine |
| BN-002 | Transcript-to-issue gaps that leave actions and blockers untracked after meetings. | SYS-002 Transcript-to-Issue Engine |
| BN-003 | Simulation output-to-report translation bottlenecks that slow report-ready artifact production. | SYS-003 Study Artifact Generator |

## Systems → Schemas

| System | Schemas Used | Data Classes |
| --- | --- | --- |
| SYS-001 Comment Resolution Engine | comment-schema.json, issue-schema.json, provenance-schema.json | Comment records, issue follow-ups, review metadata |
| SYS-002 Transcript-to-Issue Engine | issue-schema.json, provenance-schema.json | Issue records, action items, meeting provenance |
| SYS-003 Study Artifact Generator | study-output-schema.json, assumption-schema.json, provenance-schema.json | Study outputs, assumptions, artifact provenance |

## Systems → Prompts

| System | Prompt Files | Output Schema |
| --- | --- | --- |
| SYS-001 Comment Resolution Engine | prompts/comment-resolution.md | comment-schema.json, issue-schema.json |
| SYS-002 Transcript-to-Issue Engine | prompts/transcript-extraction.md | issue-schema.json |
| SYS-003 Study Artifact Generator | prompts/report-drafting.md | study-output-schema.json, provenance-schema.json |

## Systems → Evaluation

| System | Evaluation Dataset | Validation Method |
| --- | --- | --- |
| SYS-001 Comment Resolution Engine | eval/comment-resolution | Deterministic prompt harness with disposition accuracy checks |
| SYS-002 Transcript-to-Issue Engine | eval/transcript-to-issue | Extraction accuracy and coverage tests against tagged transcripts |
| SYS-003 Study Artifact Generator | eval/study-artifacts | Artifact rendering checks with schema and provenance validation |
