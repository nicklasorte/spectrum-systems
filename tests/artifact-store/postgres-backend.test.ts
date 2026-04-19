import { PostgresStorageBackend } from "@/src/artifact-store/postgres-backend";
import { v4 as uuidv4 } from "uuid";

describe("PostgreSQL Artifact Store Backend", () => {
  let backend: PostgresStorageBackend;

  beforeAll(async () => {
    backend = new PostgresStorageBackend({
      pgHost: "localhost",
      pgPort: 5432,
      pgDatabase: "spectrum_test",
      pgUser: "postgres",
      pgPassword: "postgres",
      s3Bucket: "spectrum-artifacts-test",
      s3Region: "us-east-1",
    });

    await backend.initialize();
  });

  afterAll(async () => {
    await backend.close();
  });

  it("should store and retrieve artifact", async () => {
    const artifact = {
      artifact_id: uuidv4(),
      artifact_kind: "test_artifact",
      created_at: new Date().toISOString(),
      schema_ref: "test.schema.json",
      trace: { trace_id: uuidv4(), created_at: new Date().toISOString() },
      content_hash: "sha256:test",
      payload: { test: "data" },
    };

    await backend.store(artifact);
    const retrieved = await backend.retrieve(artifact.artifact_id);

    expect(retrieved).toBeDefined();
    expect(retrieved.artifact_kind).toBe("test_artifact");
  });

  it("should log decision to audit log", async () => {
    const artifactId = uuidv4();
    const artifact = {
      artifact_id: artifactId,
      artifact_kind: "test",
      created_at: new Date().toISOString(),
      content_hash: "sha256:test",
    };

    await backend.store(artifact);
    await backend.logDecision(artifactId, "allow", ["passed_evals"], "test-system");

    const log = await backend.getAuditLog(artifactId);
    expect(log.length).toBeGreaterThan(0);
    expect(log[0].decision_outcome).toBe("allow");
  });

  it("should track overrides with expiry", async () => {
    const artifactId = uuidv4();
    await backend.recordOverride(
      artifactId,
      "reviewer-123",
      "Manual override for testing",
      30
    );

    const backlog = await backend.getOverrideBacklog();
    expect(backlog.length).toBeGreaterThan(0);

    const count = await backend.getOverrideCount();
    expect(count).toBeGreaterThan(0);
  });

  it("should enforce audit log on all operations", async () => {
    const artifact = {
      artifact_id: uuidv4(),
      artifact_kind: "audit_test",
      created_at: new Date().toISOString(),
      content_hash: "sha256:audit",
    };

    await backend.store(artifact);
    await backend.logDecision(
      artifact.artifact_id,
      "warn",
      ["threshold_exceeded"],
      "system"
    );

    const log = await backend.getAuditLog();
    expect(log.length).toBeGreaterThan(0);
  });
});
