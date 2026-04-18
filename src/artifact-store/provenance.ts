import { ProvenanceInfo, StoredArtifact } from "./types";

/**
 * Create a provenance record
 */
export function createProvenance(options: {
  component: string;
  version: string;
  inputArtifactIds: string[];
  executionFingerprint: string;
  traceId: string;
  parentTraceId?: string;
}): ProvenanceInfo {
  return {
    producedBy: {
      component: options.component,
      version: options.version,
    },
    inputArtifactIds: options.inputArtifactIds,
    executionFingerprint: options.executionFingerprint,
    traceId: options.traceId,
    parentTraceId: options.parentTraceId,
  };
}

/**
 * Build lineage chain from a stored artifact
 * In full implementation, would traverse backward through inputArtifactIds
 */
export function extractLineageChain(
  artifact: StoredArtifact,
  _allArtifacts?: StoredArtifact[]
): string[] {
  // For now, return just this artifact
  // Full implementation would recursively fetch input artifacts and build the chain
  return [artifact.artifactId];
}

/**
 * Validate provenance consistency
 */
export function validateProvenanceChain(
  artifact: StoredArtifact,
  _parentArtifact?: StoredArtifact
): { valid: boolean; issues?: string[] } {
  const issues: string[] = [];

  // Check that input artifacts are actually referenced
  if (artifact.provenance.inputArtifactIds.length === 0) {
    issues.push("No input artifacts recorded in provenance");
  }

  // Check trace consistency (future: would validate trace_id chain)
  if (!artifact.provenance.traceId) {
    issues.push("Missing trace_id in provenance");
  }

  return {
    valid: issues.length === 0,
    issues: issues.length > 0 ? issues : undefined,
  };
}
