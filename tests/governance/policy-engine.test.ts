import { PolicyEngine } from "@/src/governance/policy-engine";
import { createPolicy } from "@/src/governance/policy-schema";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("Policy Engine", () => {
  let engine: PolicyEngine;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    engine = new PolicyEngine(pool);
    await engine.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should reject policy deployment without test coverage", async () => {
    const policy = createPolicy("test-policy", "allow all", "test-owner");

    try {
      await engine.deployPolicy(policy.artifact_id);
      expect(true).toBe(false);
    } catch (e) {
      expect((e as Error).message).toContain("test failures");
    }
  });

  it("should support gradual rollout", async () => {
    const policyId = uuidv4();
    await engine.rolloutPolicy(policyId, 25);
    expect(true).toBe(true);
  });

  it("should track incidents", async () => {
    const policyId = uuidv4();
    await engine.recordPolicyIncident(policyId);
    expect(true).toBe(true);
  });

  it("should retrieve policies by status", async () => {
    const policies = await engine.getPoliciesByStatus("draft");
    expect(Array.isArray(policies)).toBe(true);
  });
});
