// Artifact storage and retrieval contract
export interface ArtifactStore {
  // Register a new artifact
  register(artifact: unknown): Promise<RegistrationResult>;

  // Retrieve an artifact by ID
  retrieve(artifactId: string): Promise<StoredArtifact | null>;

  // Query artifacts by kind, created_at range, trace_id, etc.
  query(filter: ArtifactQuery): Promise<StoredArtifact[]>;

  // Update artifact metadata (not payload - immutable)
  updateMetadata(artifactId: string, metadata: Record<string, unknown>): Promise<void>;

  // Check if artifact exists
  exists(artifactId: string): Promise<boolean>;

  // Get artifact lineage (what artifacts produced this one)
  getLineage(artifactId: string): Promise<LineageInfo>;
}

// What gets returned when you register an artifact
export interface RegistrationResult {
  artifactId: string;
  schemaRef: string;
  registeredAt: string; // ISO datetime
  contentHash: string; // SHA256 prefixed
  status: "accepted" | "rejected";
  errors?: ValidationError[];
}

// An artifact as stored (includes metadata about storage)
export interface StoredArtifact {
  // Original artifact payload
  payload: Record<string, unknown>;

  // Storage metadata
  artifactId: string;
  schemaRef: string;
  artifact_kind: string;
  createdAt: string; // ISO datetime
  registeredAt: string; // When it was stored
  contentHash: string; // SHA256 of content

  // Provenance
  provenance: ProvenanceInfo;

  // Version tracking
  version: number;
  isLatest: boolean;
}

// Provenance: what produced this artifact and why
export interface ProvenanceInfo {
  producedBy: {
    component: string; // e.g., "MVP-1: Transcript Ingestion"
    version: string;
  };
  inputArtifactIds: string[]; // Which artifacts were inputs
  executionFingerprint: string; // SHA256 of execution context
  traceId: string; // Correlation ID
  parentTraceId?: string;
}

// Query filter for finding artifacts
export interface ArtifactQuery {
  artifactKind?: string; // e.g., "transcript_artifact"
  traceId?: string;
  producedBy?: string;
  createdAfter?: string; // ISO datetime
  createdBefore?: string;
  limit?: number;
  offset?: number;
}

// Lineage: how artifacts depend on each other
export interface LineageInfo {
  artifactId: string;
  inputs: string[]; // Direct inputs (from provenance.inputArtifactIds)
  outputs: string[]; // Artifacts produced from this one
  chain: string[]; // Full lineage chain (root → this artifact)
}

// Storage backend abstraction
export interface StorageBackend {
  // Low-level storage operations
  store(key: string, value: unknown): Promise<void>;
  retrieve(key: string): Promise<unknown | null>;
  exists(key: string): Promise<boolean>;
  list(prefix?: string): Promise<string[]>;
  delete(key: string): Promise<void>;
}

// Validation error from artifact check
export interface ValidationError {
  field: string;
  message: string;
  code: string; // e.g., "schema_violation", "missing_required_field"
}
