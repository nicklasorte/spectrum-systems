import { createImmutablePolicyVersion, getIncidentTrendForPolicy } from "@/src/governance/policy-safety";
import { Pool } from "pg";

describe("Fix Slice #5: Policy Safety + Auto-Rollback", () => {
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should create immutable policy versions", async () => {
    const policyId = await createImmutablePolicyVersion(pool, "test-policy", "allow all", "owner");
    expect(policyId).toBeDefined();
  });

  it("should track incident trend", async () => {
    const trend = await getIncidentTrendForPolicy(pool, "policy-123", 7);
    expect(["increasing", "stable", "decreasing"]).toContain(trend.trend);
  });
});
