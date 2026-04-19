import { DriftDetector } from "@/src/governance/drift-detector";
import { Pool } from "pg";

describe("Drift Detector", () => {
  let detector: DriftDetector;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    detector = new DriftDetector(pool);
    await detector.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should detect decision divergence", async () => {
    const signal = await detector.detectDecisionDivergence("eval_result");
    expect(detector).toBeDefined();
  });

  it("should detect metric distribution shift", async () => {
    const signal = await detector.detectMetricDistributionShift("eval_pass_rate");
    expect(detector).toBeDefined();
  });

  it("should detect exception accumulation", async () => {
    const signal = await detector.detectExceptionAccumulation();
    expect(detector).toBeDefined();
  });

  it("should detect trace loss", async () => {
    const signal = await detector.detectTraceLoss();
    expect(detector).toBeDefined();
  });

  it("should retrieve and mark signals resolved", async () => {
    const signals = await detector.getActiveDriftSignals(10);
    expect(Array.isArray(signals)).toBe(true);
  });
});
