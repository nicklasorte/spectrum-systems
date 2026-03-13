# System Status Registry

Tracks lifecycle status for each system and where to find its interface, prompts, schemas, and evaluation assets.

| System | ID | Status | Interface | Design | Prompts | Schemas | Eval | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Comment Resolution Engine | SYS-001 | Design complete; evaluation scaffolding in place | systems/comment-resolution/interface.md | systems/comment-resolution/design.md | prompts/comment-resolution.md | schemas/comment-schema.json, schemas/issue-schema.json, schemas/provenance-schema.json | eval/comment-resolution | Requires working paper PDFs with revision lineage and strict validation |
| Transcript-to-Issue Engine | SYS-002 | Design complete; prompts to be hardened | systems/transcript-to-issue/interface.md | systems/transcript-to-issue/design.md | prompts/transcript-to-issue.md | schemas/issue-schema.json, schemas/provenance-schema.json | eval/transcript-to-issue | Speaker metadata and meeting context required for provenance |
| Study Artifact Generator | SYS-003 | Design complete; evaluation cases in progress | systems/study-artifact-generator/interface.md | systems/study-artifact-generator/design.md | prompts/report-drafting.md | schemas/study-output-schema.json, schemas/assumption-schema.json, schemas/provenance-schema.json | eval/study-artifacts | Must attach assumptions and simulation lineage to every artifact |
| Spectrum Study Compiler | SYS-004 | Drafting interfaces and compiler passes | systems/spectrum-study-compiler/interface.md | systems/spectrum-study-compiler/design.md | prompts/report-drafting.md (compiler-aware) | schemas/study-output-schema.json, schemas/provenance-schema.json | eval/study-artifacts | Coordinates ingestion, validation, and packaging of study artifacts |

Status values: ideation, design, evaluation, pilot, operational. Update this table alongside `docs/system-map.md` when systems change state.
