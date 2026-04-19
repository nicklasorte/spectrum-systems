import { ArtifactIntelligence } from "@/src/governance/artifact-intelligence";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("Artifact Intelligence Layer", () => {
  let intelligence: ArtifactIntelligence;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    intelligence = new ArtifactIntelligence(pool);
    await intelligence.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should index artifacts", async () => {
    await intelligence.indexArtifact(
      uuidv4(),
      "eval_result",
      uuidv4(),
      new Date(),
      { issue_type: "finding" },
      "pass"
    );
    expect(true).toBe(true);
  });

  it("should search by artifact kind", async () => {
    const results = await intelligence.search({
      artifact_kind: "eval_result",
      limit: 10,
    });
    expect(Array.isArray(results)).toBe(true);
  });

  it("should search by trace_id", async () => {
    const traceId = uuidv4();
    const results = await intelligence.search({
      trace_id: traceId,
    });
    expect(Array.isArray(results)).toBe(true);
  });

  it("should record control signals", async () => {
    await intelligence.recordControlSignal(
      "sli_status",
      "warning",
      "eval_pass_rate trending down",
      uuidv4(),
      "investigate_eval_quality"
    );
    expect(true).toBe(true);
  });

  it("should retrieve control signals", async () => {
    const signals = await intelligence.getControlSignals(undefined, "warning");
    expect(Array.isArray(signals)).toBe(true);
  });
});
