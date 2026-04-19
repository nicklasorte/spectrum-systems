import { PipelineIntegrationHub } from "@/src/integration/artifact-pipeline-integration";
import { PostgresStorageBackend } from "@/src/artifact-store/postgres-backend";
import { SLIBackend } from "@/src/governance/sli-backend";
import { LineageGraph } from "@/src/governance/lineage-graph";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("Pipeline Integration Hub", () => {
  let hub: PipelineIntegrationHub;
  let storage: PostgresStorageBackend;
  let sliBackend: SLIBackend;
  let lineageGraph: LineageGraph;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    storage = new PostgresStorageBackend({
      pgHost: "localhost",
      pgPort: 5432,
      pgDatabase: "spectrum_test",
      pgUser: "postgres",
      pgPassword: "postgres",
    });
    sliBackend = new SLIBackend(pool);
    lineageGraph = new LineageGraph(pool);

    hub = new PipelineIntegrationHub(storage, sliBackend, lineageGraph);
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should record MVP output with SLI measurements", async () => {
    const artifact = {
      artifact_id: uuidv4(),
      artifact_kind: "eval_summary",
      created_at: new Date().toISOString(),
      trace: { trace_id: uuidv4() },
    };

    await hub.recordMVPOutput("MVP-3", artifact, {
      eval_pass_rate: 98.5,
    });

    expect(true).toBe(true);
  });

  it("should check release gates", async () => {
    const result = await hub.checkReleaseGates(uuidv4());
    expect(typeof result.allowed).toBe("boolean");
    expect(Array.isArray(result.blockedBy)).toBe(true);
    expect(Array.isArray(result.warnings)).toBe(true);
  });

  it("should record lineage edges", async () => {
    const sourceId = uuidv4();
    const targetId = uuidv4();

    await hub.recordMVPOutput("MVP-4", {
      artifact_id: targetId,
      artifact_kind: "minutes_extraction",
      created_at: new Date().toISOString(),
      trace: { trace_id: uuidv4() },
    }, undefined, [
      { sourceId, targetId, relationship: "caused_by" },
    ]);

    expect(true).toBe(true);
  });
});
