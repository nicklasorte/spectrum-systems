import {
  ArtifactStore,
  StoredArtifact,
  RegistrationResult,
  ArtifactQuery,
  StorageBackend,
  LineageInfo,
  ProvenanceInfo,
} from "./types";
import { validateBeforeStore, computeContentHash, validateProvenance } from "./validators";
import { createProvenance, extractLineageChain, validateProvenanceChain } from "./provenance";

export class DefaultArtifactStore implements ArtifactStore {
  private backend: StorageBackend;
  private indexByKind: Map<string, Set<string>> = new Map(); // artifact_kind → artifact_ids
  private indexByTrace: Map<string, Set<string>> = new Map(); // trace_id → artifact_ids

  constructor(backend: StorageBackend) {
    this.backend = backend;
  }

  async register(artifact: unknown): Promise<RegistrationResult> {
    // Validate artifact before storing
    const validation = validateBeforeStore(artifact);
    if (!validation.valid) {
      return {
        artifactId: "",
        schemaRef: "",
        registeredAt: new Date().toISOString(),
        contentHash: "",
        status: "rejected",
        errors: validation.errors,
      };
    }

    const artifact_obj = artifact as Record<string, unknown>;
    const artifactId = artifact_obj.artifact_id as string;
    const artifact_kind = artifact_obj.artifact_kind as string;
    const schemaRef =
      (artifact_obj.schema_ref as string) || `artifacts/${artifact_kind}.schema.json`;
    const contentHash = computeContentHash(artifact);
    const registeredAt = new Date().toISOString();

    // Build stored artifact
    const stored: StoredArtifact = {
      payload: artifact_obj,
      artifactId,
      schemaRef,
      artifact_kind,
      createdAt: (artifact_obj.created_at as string) || registeredAt,
      registeredAt,
      contentHash,
      provenance: this.extractProvenance(artifact_obj),
      version: 1,
      isLatest: true,
    };

    // Store the artifact
    const key = `artifact:${artifactId}`;
    await this.backend.store(key, stored);

    // Update indexes
    this.updateIndexes(artifact_kind, (artifact_obj.trace as any)?.trace_id, artifactId);

    return {
      artifactId,
      schemaRef,
      registeredAt,
      contentHash,
      status: "accepted",
    };
  }

  async retrieve(artifactId: string): Promise<StoredArtifact | null> {
    const key = `artifact:${artifactId}`;
    const stored = await this.backend.retrieve(key);
    return (stored as StoredArtifact) || null;
  }

  async query(filter: ArtifactQuery): Promise<StoredArtifact[]> {
    const results: StoredArtifact[] = [];
    const keys = await this.backend.list("artifact:");

    for (const key of keys) {
      const artifact = (await this.backend.retrieve(key)) as StoredArtifact;
      if (!artifact) continue;

      // Apply filters
      if (filter.artifactKind && artifact.artifact_kind !== filter.artifactKind) continue;
      if (filter.traceId && artifact.provenance.traceId !== filter.traceId) continue;
      if (
        filter.producedBy &&
        artifact.provenance.producedBy.component !== filter.producedBy
      )
        continue;

      const createdTime = new Date(artifact.createdAt).getTime();
      if (filter.createdAfter && createdTime < new Date(filter.createdAfter).getTime())
        continue;
      if (filter.createdBefore && createdTime > new Date(filter.createdBefore).getTime())
        continue;

      results.push(artifact);
    }

    // Apply limit and offset
    const limit = filter.limit || 100;
    const offset = filter.offset || 0;
    return results
      .sort(
        (a, b) =>
          new Date(b.registeredAt).getTime() - new Date(a.registeredAt).getTime()
      )
      .slice(offset, offset + limit);
  }

  async updateMetadata(
    artifactId: string,
    metadata: Record<string, unknown>
  ): Promise<void> {
    const artifact = await this.retrieve(artifactId);
    if (!artifact) throw new Error(`Artifact not found: ${artifactId}`);

    // Only update metadata, not payload (immutable)
    artifact.provenance = { ...artifact.provenance, ...metadata };
    const key = `artifact:${artifactId}`;
    await this.backend.store(key, artifact);
  }

  async exists(artifactId: string): Promise<boolean> {
    return this.backend.exists(`artifact:${artifactId}`);
  }

  async getLineage(artifactId: string): Promise<LineageInfo> {
    const artifact = await this.retrieve(artifactId);
    if (!artifact) {
      return { artifactId, inputs: [], outputs: [], chain: [] };
    }

    return {
      artifactId,
      inputs: artifact.provenance.inputArtifactIds,
      outputs: [], // TODO: query for artifacts that reference this one
      chain: extractLineageChain(artifact),
    };
  }

  private extractProvenance(artifact: Record<string, unknown>): ProvenanceInfo {
    const trace = artifact.trace as any;
    const provenance = artifact.provenance as any;

    return {
      producedBy: provenance?.producedBy || { component: "unknown", version: "0" },
      inputArtifactIds: provenance?.inputArtifactIds || [],
      executionFingerprint: provenance?.executionFingerprint || "",
      traceId: trace?.trace_id || "",
      parentTraceId: trace?.parent_trace_id,
    };
  }

  private updateIndexes(
    artifact_kind: string,
    traceId: string | undefined,
    artifactId: string
  ): void {
    // Index by kind
    if (!this.indexByKind.has(artifact_kind)) {
      this.indexByKind.set(artifact_kind, new Set());
    }
    this.indexByKind.get(artifact_kind)!.add(artifactId);

    // Index by trace
    if (traceId) {
      if (!this.indexByTrace.has(traceId)) {
        this.indexByTrace.set(traceId, new Set());
      }
      this.indexByTrace.get(traceId)!.add(artifactId);
    }
  }
}

// Export factory function
export function createArtifactStore(backend: StorageBackend): ArtifactStore {
  return new DefaultArtifactStore(backend);
}

// Export all types
export * from "./types";
export { MemoryStorageBackend } from "./memory-backend";
export { validateBeforeStore, computeContentHash } from "./validators";
export { createProvenance, extractLineageChain, validateProvenanceChain } from "./provenance";
