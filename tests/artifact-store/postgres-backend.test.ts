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

  it("should write and read audit entries", async () => {
    const artifactId = uuidv4();
    const artifact = {
      artifact_id: artifactId,
      artifact_kind: "test",
      created_at: new Date().toISOString(),
      content_hash: "sha256:test",
    };

    await backend.store(artifact);
    await backend.writeAuditEntry(
      artifactId,
      "eval_completed",
      "pass",
      ["eval_passed"],
      "test-system"
    );

    const entries = await backend.readAuditEntries(artifactId);
    expect(entries.length).toBeGreaterThan(0);
    expect(entries[0].outcome).toBe("pass");
  });

  it("should track exception records with expiry", async () => {
    const artifactId = uuidv4();
    await backend.writeExceptionRecord(
      artifactId,
      "reviewer-123",
      "Testing exception tracking",
      30
    );

    const backlog = await backend.readExceptionBacklog();
    expect(backlog.length).toBeGreaterThan(0);

    const count = await backend.readExceptionCount();
    expect(count).toBeGreaterThan(0);
  });

  it("should enforce audit trail on all operations", async () => {
    const artifact = {
      artifact_id: uuidv4(),
      artifact_kind: "audit_test",
      created_at: new Date().toISOString(),
      content_hash: "sha256:audit",
    };

    await backend.store(artifact);
    await backend.writeAuditEntry(
      artifact.artifact_id,
      "verification",
      "pass",
      ["verified"],
      "system"
    );

    const entries = await backend.readAuditEntries();
    expect(entries.length).toBeGreaterThan(0);
  });
});
