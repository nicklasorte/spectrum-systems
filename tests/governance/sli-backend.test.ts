import { SLIBackend } from "@/src/governance/sli-backend";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("SLI Backend", () => {
  let backend: SLIBackend;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    backend = new SLIBackend(pool);
    await backend.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should record SLI measurement", async () => {
    await backend.recordMeasurement("eval_pass_rate", 99.5, uuidv4(), { issue_type: "finding" });
    const trend = await backend.getMeasurementTrend("eval_pass_rate", 1);
    expect(trend.length).toBeGreaterThan(0);
  });

  it("should calculate burn rate", async () => {
    const burnRate = await backend.calculateBurnRate("eval_pass_rate", 24);
    expect(typeof burnRate).toBe("number");
  });

  it("should retrieve SLO definition", async () => {
    const slo = await backend.getSLODefinition("eval_reliability");
    expect(slo).toBeDefined();
  });

  it("should calculate budget burn", async () => {
    const slo = await backend.getSLODefinition("eval_reliability");
    if (slo) {
      const burn = await backend.calculateBudgetBurn(slo.artifact_id);
      expect(burn.budget_remaining).toBeLessThanOrEqual(100);
    }
  });

  it("should record and retrieve burn rate alerts", async () => {
    const slo = await backend.getSLODefinition("eval_reliability");
    if (slo) {
      await backend.recordBurnRateAlert(
        slo.artifact_id,
        "eval_pass_rate",
        5.0,
        0.5,
        "warn",
        24,
        "Test alert"
      );

      const alerts = await backend.getActiveAlerts(1);
      expect(alerts.length).toBeGreaterThan(0);
    }
  });
});
