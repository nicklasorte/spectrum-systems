# MVP-2: Context Bundle Assembly

## Overview

MVP-2 is the second step in the Spectrum Systems pipeline. It takes a `transcript_artifact` (from MVP-1) and assembles it into a `context_bundle` — the standard, deterministic input for all downstream LLM steps.

## What It Does

1. **Validates** the transcript artifact (fail-closed on null/invalid input)
2. **Builds deterministic manifest** (hash computed from stable inputs only — no timestamps)
3. **Extracts speaker data** from transcript metadata
4. **Assembles context bundle** with transcript content + task description + instructions
5. **Registers bundle** in artifact store
6. **Emits execution record** for distributed tracing

## Key Property: Deterministic & Reproducible

MVP-2 is **fully deterministic**. The same `transcript_artifact` always produces the same `context_bundle` with the same `content_hash` and `manifest_hash`.

Hash inputs exclude wall-clock timestamps and random IDs, ensuring:
- **Replay**: Re-run the pipeline with the same transcript, get same hashes
- **Verification**: Assert that assembly was done correctly
- **Reproducibility**: Identical behavior across runs

## Input

`transcript_artifact` (full object from MVP-1) containing:
- `artifact_id` — unique identifier
- `content_hash` — SHA-256 hash of transcript content
- `metadata.speaker_labels` — list of speaker names
- `content` — raw transcript text

## Output

`context_bundle` containing:

```json
{
  "artifact_kind": "context_bundle",
  "artifact_id": "uuid",
  "created_at": "ISO 8601 timestamp",
  "schema_ref": "artifacts/context_bundle.schema.json",
  "trace": {
    "trace_id": "uuid for distributed tracing",
    "created_at": "ISO 8601 timestamp"
  },
  "input_artifacts": ["transcript_artifact_id"],
  "context": {
    "transcript_id": "string",
    "speakers": ["Alice", "Bob"],
    "transcript_content": "full raw transcript text",
    "task_description": "what this bundle is for",
    "instructions": "how downstream steps should process it"
  },
  "assembly_manifest": {
    "input_artifact_ids": ["transcript_artifact_id"],
    "assembly_version": "1.0",
    "assembly_timestamp": "ISO 8601",
    "manifest_hash": "sha256:..."
  },
  "content_hash": "sha256:..."
}
```

## Usage

```typescript
import { assembleContextBundle } from "./context-bundle-assembler";

const result = await assembleContextBundle(transcriptArtifact, {
  task_description: "Extract spectrum findings",
  instructions: "Use structured JSON output",
});

if (result.success) {
  console.log("Bundle ID:", result.context_bundle?.artifact_id);
  console.log("Content Hash:", result.context_bundle?.content_hash);
  console.log("Execution Record:", result.execution_record);
} else {
  console.error("Error:", result.error);
  console.error("Codes:", result.error_codes);
}
```

## Testing

```bash
npm test -- mvp-2
```

Tests cover:
- Successful assembly
- Missing transcript artifact (fail-closed)
- Reproducible manifest hash (run twice → same hash)
- Reproducible content hash (run twice → same hash)
- Speaker data preservation
- Transcript content preservation
- Default task/instructions
- Custom task/instructions
- Execution record on success
- Execution record on failure
- Trace context linkage
- Input artifact reference in bundle
- Artifact missing artifact_id (fail-closed)

## Dependencies

- PRE-1: Core Artifact Schemas
- PRE-2: Artifact Store & Provenance
- PRE-3: PQX Step Harness
- MVP-1: Transcript Ingestion

## Integration

- **Input from**: MVP-1 (Transcript Ingestion)
- **Output to**: MVP-3 (Ingestion Eval Gate), MVPs 4–6 (LLM steps)
