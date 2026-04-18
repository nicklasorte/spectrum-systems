# Artifact Store & Provenance Layer

The artifact store is the central repository for all artifacts in Spectrum Systems. It implements:

## Core Responsibilities

1. **Artifact Registration** — Accept, validate, and store artifacts
2. **Artifact Retrieval** — Fetch artifacts by ID, kind, trace, or date range
3. **Provenance Tracking** — Record what produced each artifact and why
4. **Lineage** — Build dependency chains between artifacts
5. **Immutability** — Artifacts are never mutated, only versioned

## Usage

```typescript
import { DefaultArtifactStore, MemoryStorageBackend } from './artifact-store';

// Create store with in-memory backend (for testing)
const backend = new MemoryStorageBackend();
const store = new DefaultArtifactStore(backend);

// Register an artifact
const result = await store.register(transcript_artifact);

// Retrieve it
const artifact = await store.retrieve(result.artifactId);

// Query by kind
const transcripts = await store.query({ artifactKind: 'transcript_artifact' });

// Get lineage
const lineage = await store.getLineage(result.artifactId);
```

## Storage Backends

Currently implemented:
- `MemoryStorageBackend` — In-memory (for testing and development)

Future backends:
- `PostgresBackend` — PostgreSQL with JSON storage
- `S3Backend` — AWS S3 with metadata in DynamoDB
- `FilesystemBackend` — Local files with index metadata

## Provenance

Every artifact records:
- `producedBy` — Component name and version that created it
- `inputArtifactIds` — Which artifacts were inputs
- `executionFingerprint` — Hash of execution context
- `traceId` — Correlation ID for the request
- `parentTraceId` — Parent request (for multi-step flows)

## Design Principles

✅ **Fail-Closed** — Invalid artifacts rejected at registration time  
✅ **Immutable** — Artifacts never change, only new versions created  
✅ **Traceable** — Every artifact links back to what produced it  
✅ **Auditable** — Full lineage chain queryable  
✅ **Validated** — All artifacts match their schemas

## Next Steps

After PRE-2:
- PRE-3: Integrate with PQX step harness
- Step 1.2: Wire dashboard API to artifact store queries
