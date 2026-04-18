import {
  createProvenance,
  validateProvenanceChain,
} from "../../src/artifact-store/provenance";
import type { StoredArtifact } from "../../src/artifact-store";

describe("Provenance", () => {
  it("should create valid provenance", () => {
    const prov = createProvenance({
      component: "MVP-1",
      version: "1.0",
      inputArtifactIds: ["input-1", "input-2"],
      executionFingerprint: "sha256:abc123",
      traceId: "trace-xyz",
    });

    expect(prov.producedBy.component).toBe("MVP-1");
    expect(prov.inputArtifactIds).toHaveLength(2);
    expect(prov.traceId).toBe("trace-xyz");
  });

  it("should create provenance with parent trace", () => {
    const prov = createProvenance({
      component: "MVP-2",
      version: "2.0",
      inputArtifactIds: ["input-1"],
      executionFingerprint: "sha256:def456",
      traceId: "trace-abc",
      parentTraceId: "trace-xyz",
    });

    expect(prov.parentTraceId).toBe("trace-xyz");
  });

  it("should validate provenance chain", () => {
    const artifact: StoredArtifact = {
      payload: {},
      artifactId: "test",
      schemaRef: "test.schema.json",
      artifact_kind: "test_artifact",
      createdAt: new Date().toISOString(),
      registeredAt: new Date().toISOString(),
      contentHash: "sha256:test",
      provenance: {
        producedBy: { component: "Test", version: "1" },
        inputArtifactIds: ["input-1"],
        executionFingerprint: "sha256:abc",
        traceId: "trace-1",
      },
      version: 1,
      isLatest: true,
    };

    const result = validateProvenanceChain(artifact);
    expect(result.valid).toBe(true);
  });

  it("should detect missing trace_id in provenance", () => {
    const artifact: StoredArtifact = {
      payload: {},
      artifactId: "test",
      schemaRef: "test.schema.json",
      artifact_kind: "test_artifact",
      createdAt: new Date().toISOString(),
      registeredAt: new Date().toISOString(),
      contentHash: "sha256:test",
      provenance: {
        producedBy: { component: "Test", version: "1" },
        inputArtifactIds: ["input-1"],
        executionFingerprint: "sha256:abc",
        traceId: "",
      },
      version: 1,
      isLatest: true,
    };

    const result = validateProvenanceChain(artifact);
    expect(result.valid).toBe(false);
    expect(result.issues).toBeDefined();
  });

  it("should detect missing input artifacts", () => {
    const artifact: StoredArtifact = {
      payload: {},
      artifactId: "test",
      schemaRef: "test.schema.json",
      artifact_kind: "test_artifact",
      createdAt: new Date().toISOString(),
      registeredAt: new Date().toISOString(),
      contentHash: "sha256:test",
      provenance: {
        producedBy: { component: "Test", version: "1" },
        inputArtifactIds: [],
        executionFingerprint: "sha256:abc",
        traceId: "trace-1",
      },
      version: 1,
      isLatest: true,
    };

    const result = validateProvenanceChain(artifact);
    expect(result.valid).toBe(false);
    expect(result.issues).toBeDefined();
  });
});
