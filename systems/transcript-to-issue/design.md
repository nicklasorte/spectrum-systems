# Transcript-to-Issue Engine — Design (SYS-002)

## Purpose
Convert meeting transcripts into structured, prioritized issues ready for backlog ingestion with complete provenance.

## Problem Statement
Meeting outcomes dissipate because action items and open questions stay embedded in transcripts, delaying follow-up, ownership, and downstream analyses.

## Inputs
- Meeting transcripts with speaker turns and timestamps.
- Participant metadata and roles.
- Meeting objectives and agenda context.
- Existing issues and categories for linkage.

## Schemas Used
- `schemas/issue-schema.json` for structured issues, status, and categorization.
- `schemas/provenance-schema.json` for lineage.
- `schemas/assumption-schema.json` when issues reference assumptions.

## Processing Pipeline
1. Segment transcripts into utterances with speaker and timestamp metadata.
2. Extract candidate issues, questions, and action items mapped to `issue-schema`.
3. Classify issues by category, priority, and owner; link to assumptions where present.
4. Detect dependencies and relate to existing backlog entries.
5. Validate schema compliance, provenance completeness, and confidence thresholds.
6. Publish issues to backlog with traceability and notify owners; emit a run manifest.
7. Route low-confidence items to human review for confirmation.

## Example Input
```json
{
  "meeting_id": "MTG-2203",
  "utterance": "We still need an interference margin sensitivity run for dense urban at 28 GHz before we can sign off.",
  "speaker": "Lead Engineer",
  "timestamp": "00:18:42"
}
```

## Example Output
```json
{
  "issue_id": "ISS-2203-07",
  "title": "Run interference margin sensitivity for dense urban at 28 GHz",
  "category": "analysis_requirement",
  "priority": "high",
  "owner": "Modeling Team",
  "status": "open",
  "dependencies": [],
  "source": {
    "meeting_id": "MTG-2203",
    "timestamp": "00:18:42",
    "speaker": "Lead Engineer"
  },
  "related_assumptions": ["ASM-045"]
}
```

## Human Review Points
- Confirm newly created issues before backlog insertion.
- Assign owners for cross-team dependencies.
- Resolve low-confidence or ambiguous utterances.

## Evaluation Criteria
- Recall and precision of extracted issues against labeled transcripts.
- Correct categorization, priority, and owner mapping.
- Completeness of provenance fields and dependency links.
- Deterministic behavior given identical inputs and prompts/manifests.

## Failure Modes
- Missing critical issues or merging distinct topics.
- Incorrect owner or category assignments that misroute work.
- Incomplete provenance preventing audit trails.
- Variability across runs leading to inconsistent backlogs.

## Implementation Notes
Implementation belongs in a separate repository. Interfaces, prompts, and evaluation harnesses in this repo must remain the single source of truth.
