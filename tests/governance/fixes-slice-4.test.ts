import { enforcePostmortemRequired, validateExceptionNotExpired, validateConvertedPolicyExists } from "@/src/governance/postmortem-enforcement";
import { Pool } from "pg";

describe("Fix Slice #4: Postmortem + Exception Enforcement", () => {
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

  it("should block on missing postmortem", async () => {
    const result = await enforcePostmortemRequired(pool, "artifact-123", new Date());
    expect(result.action).toBe("block");
  });

  it("should validate exception not expired", async () => {
    const result = await validateExceptionNotExpired(pool, "nonexistent");
    expect(result.is_valid).toBe(false);
  });
});
