import { SLOBaselineTuner } from "@/src/governance/slo-baseline-tuner";
import { Pool } from "pg";

describe("SLO Baseline Tuner", () => {
  let tuner: SLOBaselineTuner;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    tuner = new SLOBaselineTuner(pool);
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should analyze SLI percentiles", async () => {
    const analysis = await tuner.analyzeSLIPercentiles("eval_pass_rate", 7);
    expect(analysis.p50).toBeLessThanOrEqual(analysis.p95);
  });

  it("should recommend SLO targets", async () => {
    const recommendations = await tuner.recommendSLOTargets(7);
    expect(recommendations.length).toBeGreaterThan(0);
    expect(recommendations[0].confidence).toMatch(/low|medium|high/);
  });

  it("should provide reasoning for recommendations", async () => {
    const recommendations = await tuner.recommendSLOTargets(7);
    for (const rec of recommendations) {
      expect(rec.reasoning).toBeTruthy();
      expect(rec.reasoning.length).toBeGreaterThan(0);
    }
  });
});
