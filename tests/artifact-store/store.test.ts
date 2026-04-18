import { DefaultArtifactStore } from "../../src/artifact-store";
import { MemoryStorageBackend } from "../../src/artifact-store/memory-backend";
import type { TranscriptArtifact } from "../../schemas";

describe("ArtifactStore", () => {
  let store: DefaultArtifactStore;

  beforeEach(() => {
    const backend = new MemoryStorageBackend();
    store = new DefaultArtifactStore(backend);
  });

  it("should register a valid artifact", async () => {
    const transcript: TranscriptArtifact = {
      artifact_kind: "transcript_artifact",
      artifact_id: "a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5",
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/transcript_artifact.schema.json",
      trace: { trace_id: "trace-123", created_at: new Date().toISOString() },
      content: "Meeting transcript here",
      metadata: {
        speaker_labels: ["Alice", "Bob"],
        duration_minutes: 60,
        language: "en",
        source_file: "meeting.txt",
      },
      content_hash: "sha256:abc123",
    };

    const result = await store.register(transcript);

    expect(result.status).toBe("accepted");
    expect(result.artifactId).toBe(transcript.artifact_id);
    expect(result.contentHash).toMatch(/^sha256:/);
  });

  it("should retrieve a registered artifact", async () => {
    const transcript: TranscriptArtifact = {
      artifact_kind: "transcript_artifact",
      artifact_id: "test-123",
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/transcript_artifact.schema.json",
      trace: { trace_id: "trace-abc", created_at: new Date().toISOString() },
      content: "Test transcript",
      metadata: {
        speaker_labels: ["Speaker1"],
        duration_minutes: 30,
        language: "en",
        source_file: "test.txt",
      },
      content_hash: "sha256:xyz789",
    };

    await store.register(transcript);
    const retrieved = await store.retrieve("test-123");

    expect(retrieved).toBeDefined();
    expect(retrieved?.artifactId).toBe("test-123");
    expect(retrieved?.artifact_kind).toBe("transcript_artifact");
  });

  it("should reject invalid artifacts", async () => {
    const invalid = {
      artifact_kind: "transcript_artifact",
      // Missing required artifact_id
      content: "Invalid artifact",
    };

    const result = await store.register(invalid);

    expect(result.status).toBe("rejected");
    expect(result.errors).toBeDefined();
    expect(result.errors?.length).toBeGreaterThan(0);
  });

  it("should query artifacts by kind", async () => {
    const transcript: TranscriptArtifact = {
      artifact_kind: "transcript_artifact",
      artifact_id: "query-test-1",
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/transcript_artifact.schema.json",
      trace: { trace_id: "trace-query", created_at: new Date().toISOString() },
      content: "Test",
      metadata: {
        speaker_labels: [],
        duration_minutes: 10,
        language: "en",
        source_file: "test.txt",
      },
      content_hash: "sha256:test",
    };

    await store.register(transcript);
    const results = await store.query({ artifactKind: "transcript_artifact" });

    expect(results.length).toBeGreaterThan(0);
    expect(results[0].artifact_kind).toBe("transcript_artifact");
  });

  it("should get artifact lineage", async () => {
    const transcript: TranscriptArtifact = {
      artifact_kind: "transcript_artifact",
      artifact_id: "lineage-test",
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/transcript_artifact.schema.json",
      trace: { trace_id: "trace-lineage", created_at: new Date().toISOString() },
      content: "Test",
      metadata: {
        speaker_labels: [],
        duration_minutes: 10,
        language: "en",
        source_file: "test.txt",
      },
      content_hash: "sha256:test",
    };

    await store.register(transcript);
    const lineage = await store.getLineage("lineage-test");

    expect(lineage.artifactId).toBe("lineage-test");
    expect(lineage.chain).toContain("lineage-test");
  });

  it("should check if artifact exists", async () => {
    const transcript: TranscriptArtifact = {
      artifact_kind: "transcript_artifact",
      artifact_id: "exists-test",
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/transcript_artifact.schema.json",
      trace: { trace_id: "trace-exists", created_at: new Date().toISOString() },
      content: "Test",
      metadata: {
        speaker_labels: [],
        duration_minutes: 10,
        language: "en",
        source_file: "test.txt",
      },
      content_hash: "sha256:test",
    };

    await store.register(transcript);
    const exists = await store.exists("exists-test");
    const notExists = await store.exists("nonexistent");

    expect(exists).toBe(true);
    expect(notExists).toBe(false);
  });
});
