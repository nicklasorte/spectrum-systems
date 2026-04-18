# MVP-1: Transcript Ingestion & Normalization

## Overview

MVP-1 is the first step in the Spectrum Systems pipeline. It takes a raw meeting transcript and normalizes it into a schema-validated `transcript_artifact`.

## What It Does

1. **Parses** raw transcript into speaker turns
2. **Validates** that content meets minimum quality thresholds (non-empty, reasonable length)
3. **Extracts** speaker labels and metadata
4. **Normalizes** the transcript (consistent speaker names, removes empty lines)
5. **Emits** `transcript_artifact` to the artifact store
6. **Logs** execution trace for distributed tracing

## Input Format

Raw transcript file with format:

```
Speaker1: Text of first turn.
Speaker2: Text of second turn.
Speaker1: Text of third turn.
```

Optional: Include timestamps

```
Alice: [00:00:00] Good morning.
Bob: [00:01:30] Hi Alice.
```

## Output Artifact

```json
{
  "artifact_kind": "transcript_artifact",
  "artifact_id": "uuid",
  "created_at": "2026-04-18T...",
  "schema_ref": "artifacts/transcript_artifact.schema.json",
  "trace": {
    "trace_id": "uuid",
    "created_at": "2026-04-18T..."
  },
  "content": "raw transcript text",
  "metadata": {
    "speaker_labels": ["Alice", "Bob"],
    "turn_count": 10,
    "duration_minutes": 30,
    "language": "en",
    "source_file": "meeting.txt",
    "file_size_bytes": 1024,
    "processed_at": "2026-04-18T..."
  },
  "content_hash": "sha256:abc123..."
}
```

## Fail-Closed Validation

MVP-1 fails-closed on:
- Empty transcript (no speaker turns)
- Too-short content (< 50 characters)
- No valid speaker labels
- Artifact store registration failure

Any of these conditions blocks execution and emits a `pqx_execution_record` with `execution_status: "failed"`.

## Testing

```bash
npm test -- --testPathPattern=mvp-1
```

## Integration

MVP-1 output feeds into:
- **MVP-2**: Context Bundle Assembly

## Example Usage

```typescript
import { ingestTranscript } from "./transcript-ingestor";

const result = await ingestTranscript({
  raw_text: "Alice: Hello. Bob: Hi there.",
  source_file: "meeting.txt",
  duration_minutes: 30,
  language: "en",
});

if (result.success) {
  console.log("Artifact ID:", result.transcript_artifact.artifact_id);
  console.log("Speakers:", result.transcript_artifact.metadata.speaker_labels);
} else {
  console.error("Ingestion failed:", result.error);
}
```

## Architecture Notes

- **No LLM**: Parsing is fully deterministic
- **Fail-Closed**: Invalid input produces explicit failure, not silent skip
- **Traceable**: Every artifact linked via `trace.trace_id`
- **Reproducible**: Same input always produces same `content_hash`

## Dependencies

- PRE-1: Core Artifact Schemas
- PRE-2: Artifact Store & Provenance
