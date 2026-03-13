# Prompts — Transcript-to-Issue Engine

Primary prompt: `prompts/transcript-to-issue.md`.

- **Purpose**: Extract issues, actions, and questions from transcripts with backlog-ready structure.
- **Inputs**: Transcript segments with speaker/timestamp, meeting context, known categories/owners for grounding.
- **Outputs**: Issue records aligned to `schemas/issue-schema.json` with provenance fields.
- **Constraints**: Do not invent context; preserve speaker intent; flag ambiguity; use deterministic parameters.
- **Grounding Rules**: Cite transcript timecodes; map owners to provided roles; avoid merging distinct issues without evidence.
- **Versioning**: Maintain a version string in the prompt header; prompt changes must trigger revalidation in `eval/transcript-to-issue`.
