# Persistent Artifact Store

PostgreSQL backend for durable artifact storage.

## Tables

- `artifacts`: All pipeline artifacts with metadata (immutable)
- `audit_entries`: Event log for all artifact operations
- `exception_records`: Tracked exception records with expiry dates

## Usage

```typescript
import { createPostgresBackend } from './postgres-factory';

const backend = createPostgresBackend();
await backend.initialize();

// Store artifact
await backend.store(artifact);

// Retrieve artifact
const artifact = await backend.retrieve(artifactId);

// Write audit entry
await backend.writeAuditEntry(
  artifactId,
  "eval_completed",
  "pass",
  ["eval_passed"],
  "system"
);

// Read audit entries
const entries = await backend.readAuditEntries(artifactId);

// Track exception records
await backend.writeExceptionRecord(
  artifactId,
  "reviewer-123",
  "Exception tracking reason",
  30  // expiry days
);

// Query exception records
const backlog = await backend.readExceptionBacklog();
const count = await backend.readExceptionCount();
```

## Configuration

Via environment variables:

```bash
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=spectrum_systems
PG_USER=postgres
PG_PASSWORD=postgres
```

## Design

- **Immutable artifacts**: All artifacts stored as-is, never modified
- **Audit trail**: Every operation logged in audit_entries
- **Exception tracking**: Exceptional conditions recorded with expiry
- **Index-optimized**: Efficient queries by artifact kind, trace ID, creation date
