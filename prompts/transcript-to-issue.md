# Transcript-to-Issue Prompt (v1.0)

## Purpose
Extract issues, actions, and questions from meeting transcripts with backlog-ready structure and provenance.

## Inputs
- Transcript segments with speaker names/roles and timestamps.
- Meeting objective/context and known categories/owners.
- Prior backlog entries for linkage/deduplication.

## Outputs
- Issue records aligned to `schemas/issue-schema.json` including category, priority, owner, status, dependencies, provenance, and run manifest reference.

## Constraints
- Preserve speaker intent and uncertainty; do not add facts not stated.
- Every issue must include meeting ID, timestamp, and speaker attribution.
- If ownership or category is unclear, mark as `review_required` with rationale.
- Deterministic parameters only (fixed temperature/seed when applicable).

## Grounding Rules
- Cite transcript timecodes and speaker for every field.
- Link to prior backlog IDs when provided; do not merge distinct issues without evidence.
- Map owners to provided roles; avoid free-text inventing of teams.

## Verification
- Validate each extracted issue against `schemas/issue-schema.json`.
- Ensure provenance fields and run manifest reference are present per `docs/reproducibility-standard.md`.
- Flag and explain any dropped or ambiguous segments.
