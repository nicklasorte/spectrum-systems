# MVP-4: Meeting Minutes Extraction

## Overview

MVP-4 is the first AI-driven step in the Spectrum Systems pipeline. It uses Claude Haiku to extract structured meeting minutes from the context bundle (which contains the transcript).

## Purpose (from Design Doc)

> "Uses an LLM agent (via PQX) to extract structured meeting minutes from the transcript. This is the first AI-driven step. Output must conform to schema — no free-form text escapes."

## Key Requirement

**Output must conform to schema.** If schema validation fails, execution is rejected (fail-closed).

## What Gets Extracted

- **agenda_items**: List of discussion topics
- **decisions**: Decisions made with rationale
- **action_items**: Tasks assigned (with owner, due date)
- **attendees**: People mentioned

## Model: Claude Haiku

Chosen for structured extraction with low complexity (not heavy reasoning needed).

## Output Artifact

**meeting_minutes_artifact**:
```json
{
  "artifact_kind": "meeting_minutes_artifact",
  "artifact_id": "uuid",
  "created_at": "ISO 8601",
  "schema_ref": "artifacts/meeting_minutes_artifact.schema.json",
  "trace": { "trace_id", "created_at" },
  "source_transcript_id": "uuid",
  "source_context_bundle_id": "uuid",
  "agenda_items": ["item1", "item2"],
  "decisions": [
    { "decision": "text", "rationale": "text" }
  ],
  "action_items": [
    { "item": "text", "owner": "name", "due_date": "YYYY-MM-DD" }
  ],
  "attendees": ["name1", "name2"],
  "extraction_model": "claude-3-5-haiku-20241022",
  "content_hash": "sha256:..."
}
```

## Usage

```typescript
import { extractMeetingMinutes } from "@/src/mvp-4/minutes-extraction-agent";

const result = await extractMeetingMinutes(contextBundle);

if (result.success) {
  console.log("Minutes:", result.meeting_minutes_artifact);
  console.log("Agenda:", result.meeting_minutes_artifact?.agenda_items);
  console.log("Decisions:", result.meeting_minutes_artifact?.decisions);
} else {
  console.error("Extraction failed:", result.error);
}
```

## Testing

Tests cover:

- ✅ Successful extraction
- ✅ Agenda items extracted
- ✅ Decisions with rationale extracted
- ✅ Action items with owner extracted
- ✅ Attendees extracted
- ✅ Execution record on success
- ✅ Execution record on failure
- ✅ Trace context linked
- ✅ Fail-closed on invalid JSON

## Integration

- **Input from**: MVP-2 (context_bundle) — after MVP-3 allows it
- **Output to**: MVP-5 (Issue Extraction) and MVP-6 (Extraction Eval Gate)

## Dependencies

- MVP-2: Context Bundle Assembly ✅
- MVP-3: Ingestion Eval Gate ✅
