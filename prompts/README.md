# Prompt Catalog

This catalog tracks prompts used across automation systems so that inputs, outputs, and expected schemas remain explicit and reviewable.

## Prompt Categories

- **Extraction Prompts**: Convert documents, transcripts, or spreadsheets into structured records (e.g., comment and issue extraction).
- **Transformation Prompts**: Convert technical outputs into structured artifacts or report-ready language.
- **Analysis Prompts**: Identify issues, assumptions, or risks within engineering and policy materials.

## Prompt Registry

| Prompt Name | System | Input Type | Output Schema | Version | Notes |
| --- | --- | --- | --- | --- | --- |
| prompts/comment-resolution.md | SYS-001 Comment Resolution Engine | Comment spreadsheets and report excerpts | comment-schema.json, issue-schema.json | v1.0 | Clusters comments, aligns to sections, drafts dispositions with provenance |
| prompts/transcript-extraction.md | SYS-002 Transcript-to-Issue Engine | Meeting transcripts with speaker metadata | issue-schema.json | v1.0 | Extracts issues, actions, and uncertainties for backlog intake |
| prompts/report-drafting.md | SYS-003 Study Artifact Generator | Simulation outputs and study templates | study-output-schema.json, provenance-schema.json | v1.0 | Generates tables and narrative with embedded provenance fields |
