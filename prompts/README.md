# Prompt Catalog

Prompts are versioned, schema-aligned instructions for AI steps in each system. Every prompt must declare purpose, inputs, outputs, constraints, grounding rules, and version notes.

## Registry

| Prompt | System | Purpose | Inputs | Outputs | Schemas | Constraints / Grounding | Version |
| --- | --- | --- | --- | --- | --- | --- | --- |
| prompts/comment-resolution.md | SYS-001 Comment Resolution Engine | Draft deterministic dispositions with revision lineage | Comment records, working paper context, section anchors | Dispositions with status, section mapping, provenance | comment-schema.json, issue-schema.json, provenance-schema.json | Cite revisions and sections; use rule packs; flag missing anchors | v1.0 |
| prompts/transcript-to-issue.md | SYS-002 Transcript-to-Issue Engine | Extract issues/actions/questions from transcripts | Transcript segments with speaker/timestamp, meeting context | Issue records with category/priority/owner and provenance | issue-schema.json, provenance-schema.json | Preserve speaker intent; cite timecodes; flag ambiguity; deterministic params | v1.0 |
| prompts/report-drafting.md | SYS-003 Study Artifact Generator / SYS-004 Spectrum Study Compiler | Render tables/figures/narratives from normalized outputs | Simulation outputs, assumptions, templates, report anchors | Artifacts and narratives with provenance and manifest references | study-output-schema.json, assumption-schema.json, provenance-schema.json | No speculative values; cite assumptions; follow templates; deterministic formatting | v1.0 |
| prompts/spectrum-study-compiler.md | SYS-004 Spectrum Study Compiler | Validate bundles, detect missing dependencies, and assemble packages with diagnostics | Artifact bundles, manifests, provenance/run manifests, ordering rules | Diagnostics, ordered bundles, reviewer notes | compiler-manifest.schema.json, artifact-bundle.schema.json, diagnostics.schema.json, study-output-schema.json, provenance-schema.json | No fabricated content; deterministic ordering; errors block emission; warnings propagate | v1.0 |

See per-system prompt notes under `systems/<system>/prompts.md`. Update this table whenever prompt files, schemas, or versions change.
