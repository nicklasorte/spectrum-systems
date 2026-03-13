# Transcript-to-Issue Engine — Interface (SYS-002)

## Purpose
Deterministically extract issues, actions, and questions from meeting transcripts with full provenance and backlog-ready structure.

## Inputs
- Meeting transcripts with speaker names/roles and timestamps.
- Meeting context (objective, agenda, scenario) and participant metadata.
- Existing backlog or issue registry for linkage/deduplication.
- Prompt and rule versions referenced in `prompts/transcript-to-issue.md`.

## Schemas Used
- `schemas/issue-schema.json`
- `schemas/provenance-schema.json`
- Optional: `schemas/assumption-schema.json` when issues reference assumptions.

## Outputs
- Structured issue records (category, priority, owner, status, dependencies) with provenance.
- Linkages to source transcript segments (meeting ID, timestamp, speaker).
- Run manifest capturing inputs, prompt/rule versions, model settings, and schema versions.

## Validation Rules
- Speaker and timestamp metadata are required for every extracted issue.
- Issue categories, priorities, and statuses must match enumerations in `schemas/issue-schema.json`.
- Provenance and run manifest references are mandatory.
- Low-confidence or ambiguous items must be flagged for human review rather than silently emitted.

## Evaluation Method
- Use `eval/transcript-to-issue` to measure precision/recall on labeled transcripts, provenance completeness, and deterministic outputs.
- Blocking failures: missing speaker/timestamp, schema violations, unstable outputs with identical manifests.

## Versioning
- Interface changes require a version bump recorded in run manifests and `docs/system-status-registry.md`; rerun evaluation suites after any prompt/rule change.
