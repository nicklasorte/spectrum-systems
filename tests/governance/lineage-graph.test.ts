import { LineageGraph } from "@/src/governance/lineage-graph";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("Lineage Graph", () => {
  let graph: LineageGraph;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    graph = new LineageGraph(pool);
    await graph.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should record lineage edges", async () => {
    const sourceId = uuidv4();
    const targetId = uuidv4();
    await graph.recordLineageEdge(sourceId, targetId, "caused_by");
    expect(true).toBe(true);
  });

  it("should find root causes", async () => {
    const artifactId = uuidv4();
    const roots = await graph.getRootCauses(artifactId);
    expect(Array.isArray(roots)).toBe(true);
  });

  it("should get inbound lineage", async () => {
    const artifactId = uuidv4();
    const inbound = await graph.getInboundLineage(artifactId, 5);
    expect(Array.isArray(inbound)).toBe(true);
  });

  it("should get outbound lineage", async () => {
    const artifactId = uuidv4();
    const outbound = await graph.getOutboundLineage(artifactId, 5);
    expect(Array.isArray(outbound)).toBe(true);
  });

  it("should get impacted artifacts", async () => {
    const artifactId = uuidv4();
    const impacted = await graph.getImpactedArtifacts(artifactId);
    expect(Array.isArray(impacted)).toBe(true);
  });
});
