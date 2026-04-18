# MVP-5: Issue & Action Item Extraction

## Overview

MVP-5 extracts spectrum-relevant issues and action items from the transcript and meeting minutes. Each issue is traceable to its source in the transcript.

## Purpose (from Design Doc)

> "Extracts and structures all spectrum-relevant issues and action items into a governed registry artifact. Each issue is traceable to its source transcript turn."

## CRITICAL Requirement: Source Traceability

**Every issue must have `source_turn_ref`** — a direct quote from the transcript identifying where it came from.

This enables:
- Full traceability from issue back to source
- Verification that issues are real (not hallucinated)
- Paper generation can cite specific turns

## Issue Structure

```json
{
  "issue_id": "ISSUE-001",
  "type": "finding" | "action_item" | "risk",
  "description": "Full description",
  "priority": "high" | "medium" | "low",
  "assignee": "name (optional)",
  "status": "open" | "closed",
  "source_turn_ref": "Direct quote from transcript"
}
```

## Model: Claude Haiku

Chosen for structured extraction with source traceability (not heavy reasoning).

## Output Artifact

**issue_registry_artifact**:

```json
{
  "artifact_kind": "issue_registry_artifact",
  "artifact_id": "uuid",
  "created_at": "ISO 8601",
  "schema_ref": "artifacts/issue_registry_artifact.schema.json",
  "trace": { "trace_id", "created_at" },
  "source_transcript_id": "uuid",
  "source_context_bundle_id": "uuid",
  "source_minutes_id": "uuid",
  "issues": [
    { ... issue objects ... }
  ],
  "extraction_model": "claude-3-5-haiku-20241022",
  "content_hash": "sha256:..."
}
```

## Usage

```typescript
import { extractIssues } from "@/src/mvp-5/issue-extraction-agent";

const result = await extractIssues(contextBundle, minutesArtifact);

if (result.success) {
  console.log("Issues:", result.issue_registry_artifact?.issues);
  for (const issue of result.issue_registry_artifact?.issues) {
    console.log(`${issue.issue_id}: ${issue.description}`);
    console.log(`  Source: ${issue.source_turn_ref}`);
  }
} else {
  console.error("Extraction failed:", result.error);
}
```

## Testing

Tests cover:

- ✅ Successful extraction
- ✅ Issues array populated
- ✅ All issues have source_turn_ref (CRITICAL)
- ✅ Required fields present
- ✅ Diverse issue types
- ✅ Execution record on success/failure
- ✅ Trace context linked
- ✅ Empty issue list handled gracefully

## Integration

- **Input from**: MVP-2 (context_bundle), MVP-4 (meeting_minutes_artifact)
- **Output to**: MVP-6 (Extraction Eval Gate) and MVP-7 (Structured Issue Set)

## Dependencies

- MVP-2: Context Bundle Assembly ✅
- MVP-4: Meeting Minutes Extraction ✅
