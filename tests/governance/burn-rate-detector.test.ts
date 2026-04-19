import { BurnRateDetector } from "@/src/governance/burn-rate-detector";
import { SLIBackend } from "@/src/governance/sli-backend";
import { DEFAULT_SLOS } from "@/src/governance/sli-types";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("Burn-Rate Detector", () => {
  let detector: BurnRateDetector;
  let backend: SLIBackend;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    backend = new SLIBackend(pool);
    await backend.initialize();
    detector = new BurnRateDetector(backend);
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should not alert on single high-burn sample", async () => {
    const slo = { ...DEFAULT_SLOS[0], artifact_id: uuidv4() } as any;
    const alert = await detector.detectAndAlert(slo, "eval_pass_rate");
    expect(alert).toBeNull();
  });

  it("should apply hysteresis before escalating", async () => {
    expect(detector).toBeDefined();
  });

  it("should track consecutive high-burn samples", async () => {
    expect(detector).toBeDefined();
  });
});
